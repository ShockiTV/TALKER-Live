/*
 * talker_audio.c — Native audio capture DLL for TALKER Expanded.
 *
 * Provides mic capture (PortAudio), energy-based VAD, Opus encoding,
 * and a poll-based API for LuaJIT FFI consumption.
 *
 * Architecture:
 *   PortAudio callback (OS thread) → Opus encode → SPSC ring buffer
 *   Lua game tick → ta_poll() drains ring buffer → sends over WS
 *
 * Thread safety: The ring buffer is the ONLY shared structure.
 * It uses atomic load/store on read/write indices (SPSC — no mutex needed).
 */

#include <stdlib.h>
#include <string.h>
#include <math.h>

#include <portaudio.h>
#include <opus/opus.h>

/* ── Platform ────────────────────────────────────────────────────────────── */

#ifdef _WIN32
#  include <windows.h>   /* InterlockedExchange, MemoryBarrier */
#  define ATOMIC_LOAD(p)      (MemoryBarrier(), *(volatile long*)(p))
#  define ATOMIC_STORE(p, v)  (InterlockedExchange((volatile long*)(p), (long)(v)))
#else
#  define ATOMIC_LOAD(p)      __atomic_load_n((p), __ATOMIC_ACQUIRE)
#  define ATOMIC_STORE(p, v)  __atomic_store_n((p), (v), __ATOMIC_RELEASE)
#endif

/* ── Export macro ────────────────────────────────────────────────────────── */

#ifdef TALKER_AUDIO_EXPORTS
#  define TA_API __declspec(dllexport)
#else
#  define TA_API __declspec(dllimport)
#endif

/* ── Constants ───────────────────────────────────────────────────────────── */

#define SAMPLE_RATE       16000
#define CHANNELS          1
#define MAX_OPUS_PACKET   4000          /* generous upper bound per frame   */
#define RING_CAPACITY     256           /* slots (~5.1s at 20ms frames)     */

/* ── Ring buffer slot ────────────────────────────────────────────────────── */

typedef struct {
    int   len;                          /* opus bytes in data[], or 0       */
    unsigned char data[MAX_OPUS_PACKET];
} RingSlot;

/* ── Ring buffer (SPSC, lock-free) ───────────────────────────────────────── */

typedef struct {
    RingSlot slots[RING_CAPACITY];
    long     write_idx;                 /* only producer writes             */
    long     read_idx;                  /* only consumer writes             */
} RingBuf;

static void ring_init(RingBuf *rb) {
    memset(rb, 0, sizeof(*rb));
}

/* Producer: try to push.  Returns 1 on success, 0 if full (drop oldest). */
static int ring_push(RingBuf *rb, const unsigned char *data, int len) {
    long w = ATOMIC_LOAD(&rb->write_idx);
    long r = ATOMIC_LOAD(&rb->read_idx);
    long next_w = (w + 1) % RING_CAPACITY;

    if (next_w == r) {
        /* Full — advance read to drop oldest (overwrite policy). */
        ATOMIC_STORE(&rb->read_idx, (r + 1) % RING_CAPACITY);
    }

    RingSlot *slot = &rb->slots[w];
    if (len > MAX_OPUS_PACKET) len = MAX_OPUS_PACKET;
    memcpy(slot->data, data, len);
    slot->len = len;

    ATOMIC_STORE(&rb->write_idx, next_w);
    return 1;
}

/* Consumer: try to pop one frame.  Returns bytes copied, or 0 if empty. */
static int ring_pop(RingBuf *rb, unsigned char *out, int out_len) {
    long r = ATOMIC_LOAD(&rb->read_idx);
    long w = ATOMIC_LOAD(&rb->write_idx);
    if (r == w) return 0;              /* empty */

    RingSlot *slot = &rb->slots[r];
    int n = slot->len;
    if (n > out_len) n = out_len;
    memcpy(out, slot->data, n);

    ATOMIC_STORE(&rb->read_idx, (r + 1) % RING_CAPACITY);
    return n;
}

static int ring_empty(RingBuf *rb) {
    return ATOMIC_LOAD(&rb->read_idx) == ATOMIC_LOAD(&rb->write_idx);
}

/* ── Stop reason codes ───────────────────────────────────────────────────── */

#define STOP_NONE    0
#define STOP_VAD    -1
#define STOP_MANUAL -2

/* ── Global state ────────────────────────────────────────────────────────── */

static int          g_initialized   = 0;
static int          g_capturing     = 0;
static int          g_stop_reason   = STOP_NONE; /* set when capture ends   */
static int          g_stop_emitted  = 0;         /* 1 once poll returned it */

/* PortAudio */
static PaStream    *g_stream        = NULL;

/* Opus */
static OpusEncoder *g_encoder       = NULL;
static int          g_opus_bitrate    = 24000;
static int          g_opus_frame_ms   = 20;
static int          g_opus_complexity = 5;

/* Ring buffer */
static RingBuf     *g_ring          = NULL;

/* VAD */
static int          g_vad_threshold  = 1000;    /* mean |sample| threshold */
static int          g_vad_silence_ms = 2000;    /* ms of silence to stop   */
static int          g_vad_silent_ms  = 0;       /* accumulator             */

/* Opus encode buffer (temp, used in callback) */
static short       *g_pcm_accum      = NULL;    /* accumulate samples      */
static int          g_pcm_accum_len   = 0;      /* current count           */
static int          g_pcm_frame_size  = 0;      /* samples per Opus frame  */

/* Device selection */
static int          g_device_index    = -1;     /* -1 = default            */

/* ── PortAudio callback ──────────────────────────────────────────────────── */

static int pa_callback(
    const void *input_buf,
    void       *output_buf,
    unsigned long frame_count,
    const PaStreamCallbackTimeInfo *time_info,
    PaStreamCallbackFlags flags,
    void *user_data)
{
    (void)output_buf;
    (void)time_info;
    (void)flags;
    (void)user_data;

    if (!input_buf || !g_capturing) return paComplete;

    const short *samples = (const short *)input_buf;
    int count = (int)frame_count;

    /* ── VAD: compute mean absolute amplitude ────────────────────────── */
    long long sum = 0;
    for (int i = 0; i < count; i++) {
        int v = samples[i];
        sum += (v < 0) ? -v : v;
    }
    int mean_amp = (count > 0) ? (int)(sum / count) : 0;

    /* Duration of this callback in ms */
    int chunk_ms = (count * 1000) / SAMPLE_RATE;

    if (mean_amp < g_vad_threshold) {
        g_vad_silent_ms += chunk_ms;
        if (g_vad_silent_ms >= g_vad_silence_ms) {
            /* VAD triggers auto-stop */
            g_capturing = 0;
            g_stop_reason = STOP_VAD;
            return paComplete;
        }
    } else {
        g_vad_silent_ms = 0;
    }

    /* ── Accumulate PCM and encode Opus frames ───────────────────────── */
    int pos = 0;
    while (pos < count) {
        int space = g_pcm_frame_size - g_pcm_accum_len;
        int avail = count - pos;
        int to_copy = (avail < space) ? avail : space;

        memcpy(g_pcm_accum + g_pcm_accum_len, samples + pos, to_copy * sizeof(short));
        g_pcm_accum_len += to_copy;
        pos += to_copy;

        if (g_pcm_accum_len >= g_pcm_frame_size) {
            /* Encode one Opus frame */
            unsigned char opus_buf[MAX_OPUS_PACKET];
            int encoded = opus_encode(g_encoder, g_pcm_accum, g_pcm_frame_size,
                                      opus_buf, MAX_OPUS_PACKET);
            if (encoded > 0) {
                ring_push(g_ring, opus_buf, encoded);
            }
            g_pcm_accum_len = 0;
        }
    }

    return paContinue;
}

/* ── API: Lifecycle ──────────────────────────────────────────────────────── */

#ifdef __cplusplus
extern "C" {
#endif

TA_API int ta_open(void) {
    if (g_initialized) return 0;       /* idempotent */

    PaError err = Pa_Initialize();
    if (err != paNoError) return -1;

    g_ring = (RingBuf *)calloc(1, sizeof(RingBuf));
    if (!g_ring) { Pa_Terminate(); return -1; }
    ring_init(g_ring);

    g_initialized   = 1;
    g_capturing     = 0;
    g_stop_reason   = STOP_NONE;
    g_stop_emitted  = 0;
    g_device_index  = -1;
    return 0;
}

TA_API void ta_close(void) {
    if (!g_initialized) return;

    if (g_capturing) {
        g_capturing = 0;
        if (g_stream) {
            Pa_StopStream(g_stream);
            Pa_CloseStream(g_stream);
            g_stream = NULL;
        }
    }

    if (g_encoder) {
        opus_encoder_destroy(g_encoder);
        g_encoder = NULL;
    }

    free(g_pcm_accum);
    g_pcm_accum = NULL;
    g_pcm_accum_len = 0;

    free(g_ring);
    g_ring = NULL;

    Pa_Terminate();
    g_initialized = 0;
}

/* ── API: Capture start / stop ───────────────────────────────────────────── */

TA_API int ta_start(void) {
    if (!g_initialized) return -1;

    /* If already capturing, restart */
    if (g_capturing && g_stream) {
        g_capturing = 0;
        Pa_StopStream(g_stream);
        Pa_CloseStream(g_stream);
        g_stream = NULL;
    }

    /* Clean up previous encoder */
    if (g_encoder) {
        opus_encoder_destroy(g_encoder);
        g_encoder = NULL;
    }

    /* Reset ring buffer */
    ring_init(g_ring);

    /* Reset state */
    g_stop_reason  = STOP_NONE;
    g_stop_emitted = 0;
    g_vad_silent_ms = 0;

    /* Opus frame size in samples */
    g_pcm_frame_size = (SAMPLE_RATE * g_opus_frame_ms) / 1000;

    /* Allocate PCM accumulator */
    free(g_pcm_accum);
    g_pcm_accum = (short *)calloc(g_pcm_frame_size, sizeof(short));
    if (!g_pcm_accum) return -1;
    g_pcm_accum_len = 0;

    /* Create Opus encoder */
    int opus_err;
    g_encoder = opus_encoder_create(SAMPLE_RATE, CHANNELS,
                                    OPUS_APPLICATION_VOIP, &opus_err);
    if (opus_err != OPUS_OK || !g_encoder) return -1;

    opus_encoder_ctl(g_encoder, OPUS_SET_BITRATE(g_opus_bitrate));
    opus_encoder_ctl(g_encoder, OPUS_SET_COMPLEXITY(g_opus_complexity));

    /* Open PortAudio stream */
    PaStreamParameters params;
    memset(&params, 0, sizeof(params));

    if (g_device_index >= 0) {
        params.device = g_device_index;
    } else {
        params.device = Pa_GetDefaultInputDevice();
    }
    if (params.device == paNoDevice) return -1;

    params.channelCount = CHANNELS;
    params.sampleFormat = paInt16;
    params.suggestedLatency =
        Pa_GetDeviceInfo(params.device)->defaultLowInputLatency;

    /* Request callbacks at Opus frame size for aligned encoding */
    PaError err = Pa_OpenStream(
        &g_stream,
        &params,    /* input  */
        NULL,       /* no output */
        SAMPLE_RATE,
        g_pcm_frame_size,  /* frames per buffer */
        paClipOff,
        pa_callback,
        NULL
    );
    if (err != paNoError) return -1;

    g_capturing = 1;

    err = Pa_StartStream(g_stream);
    if (err != paNoError) {
        g_capturing = 0;
        Pa_CloseStream(g_stream);
        g_stream = NULL;
        return -1;
    }

    return 0;
}

TA_API int ta_stop(void) {
    if (!g_initialized) return 0;
    if (!g_capturing)   return 0;      /* no-op */

    g_capturing = 0;
    g_stop_reason = STOP_MANUAL;

    if (g_stream) {
        Pa_StopStream(g_stream);
        Pa_CloseStream(g_stream);
        g_stream = NULL;
    }

    return 0;
}

TA_API int ta_is_capturing(void) {
    return g_capturing ? 1 : 0;
}

/* ── API: Poll ───────────────────────────────────────────────────────────── */

TA_API int ta_poll(unsigned char *buf, int buf_len) {
    if (!g_initialized || !g_ring) return 0;

    /* Try to drain one frame */
    int n = ring_pop(g_ring, buf, buf_len);
    if (n > 0) return n;

    /* Ring is empty — check for stop signal */
    if (g_stop_reason != STOP_NONE && !g_stop_emitted) {
        g_stop_emitted = 1;
        return g_stop_reason;     /* -1 (VAD) or -2 (manual) */
    }

    return 0;   /* nothing ready, still capturing (or already emitted stop) */
}

/* ── API: VAD configuration ──────────────────────────────────────────────── */

TA_API void ta_set_vad(int energy_threshold, int silence_ms) {
    g_vad_threshold  = energy_threshold;
    g_vad_silence_ms = silence_ms;
}

/* ── API: Device enumeration & selection ─────────────────────────────────── */

TA_API int ta_get_device_count(void) {
    if (!g_initialized) return 0;

    int num_devices = Pa_GetDeviceCount();
    int input_count = 0;
    for (int i = 0; i < num_devices; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (info && info->maxInputChannels > 0) {
            input_count++;
        }
    }
    return input_count;
}

/* Map logical input-device index → PortAudio device index */
static int map_input_device(int logical_idx) {
    int num_devices = Pa_GetDeviceCount();
    int count = 0;
    for (int i = 0; i < num_devices; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (info && info->maxInputChannels > 0) {
            if (count == logical_idx) return i;
            count++;
        }
    }
    return -1;  /* not found */
}

TA_API int ta_get_device_name(int index, char *buf, int buf_len) {
    if (!g_initialized || !buf || buf_len <= 0) return -1;

    int pa_idx = map_input_device(index);
    if (pa_idx < 0) { buf[0] = '\0'; return -1; }

    const PaDeviceInfo *info = Pa_GetDeviceInfo(pa_idx);
    if (!info || !info->name) { buf[0] = '\0'; return -1; }

    /* Safe copy */
    int len = (int)strlen(info->name);
    if (len >= buf_len) len = buf_len - 1;
    memcpy(buf, info->name, len);
    buf[len] = '\0';
    return 0;
}

TA_API int ta_get_default_device(void) {
    if (!g_initialized) return -1;

    PaDeviceIndex def = Pa_GetDefaultInputDevice();
    if (def == paNoDevice) return -1;

    /* Convert PA device index → logical input-device index */
    int num_devices = Pa_GetDeviceCount();
    int count = 0;
    for (int i = 0; i < num_devices; i++) {
        const PaDeviceInfo *info = Pa_GetDeviceInfo(i);
        if (info && info->maxInputChannels > 0) {
            if (i == (int)def) return count;
            count++;
        }
    }
    return -1;
}

TA_API int ta_set_device(int index) {
    if (!g_initialized) return -1;

    int pa_idx = map_input_device(index);
    if (pa_idx < 0) return -1;        /* invalid index */

    g_device_index = pa_idx;
    return 0;
}

/* ── API: Opus configuration ─────────────────────────────────────────────── */

TA_API void ta_set_opus_bitrate(int bps) {
    if (bps > 0) g_opus_bitrate = bps;
}

TA_API void ta_set_opus_frame_ms(int ms) {
    /* Opus supports 2.5, 5, 10, 20, 40, 60 ms — validate loosely */
    if (ms > 0 && ms <= 60) g_opus_frame_ms = ms;
}

TA_API void ta_set_opus_complexity(int complexity) {
    if (complexity >= 0 && complexity <= 10) g_opus_complexity = complexity;
}

#ifdef __cplusplus
}
#endif
