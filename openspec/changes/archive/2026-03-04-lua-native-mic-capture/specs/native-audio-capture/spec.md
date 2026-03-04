# native-audio-capture

## Purpose

Defines the native C DLL (`talker_audio.dll`) that provides mic capture, energy-based VAD, Opus encoding, and device selection — loaded by LuaJIT FFI inside the STALKER game process. Exposes a poll-based API so the Lua game tick can drain encoded audio without thread-safety concerns.

## ADDED Requirements

### Requirement: DLL lifecycle management
The DLL SHALL expose `ta_open()` and `ta_close()` functions for global initialization and teardown. `ta_open()` SHALL initialize PortAudio and internal state. `ta_close()` SHALL stop any active capture, release PortAudio resources, and free all internal buffers.

#### Scenario: Normal lifecycle
- **WHEN** `ta_open()` is called
- **THEN** PortAudio is initialized and the DLL is ready to capture
- **AND** `ta_open()` returns `0` on success

#### Scenario: Repeated open is safe
- **WHEN** `ta_open()` is called while already open
- **THEN** it returns `0` without reinitializing (idempotent)

#### Scenario: Close releases all resources
- **WHEN** `ta_close()` is called after capture sessions
- **THEN** any active capture is stopped
- **AND** PortAudio is terminated
- **AND** internal ring buffer memory is freed

### Requirement: Capture start and stop
The DLL SHALL expose `ta_start()` and `ta_stop()` for starting and stopping audio capture. `ta_start()` SHALL open the selected (or default) capture device via PortAudio, start the internal capture thread, and begin filling the ring buffer with Opus-encoded frames.

#### Scenario: Start begins capture
- **WHEN** `ta_start()` is called after `ta_open()`
- **THEN** a PortAudio capture stream is opened on the selected device
- **AND** the internal capture callback begins writing Opus frames to the ring buffer
- **AND** `ta_start()` returns `0` on success

#### Scenario: Start while already capturing restarts
- **WHEN** `ta_start()` is called while capture is active
- **THEN** the current capture is stopped
- **AND** a new capture session begins (ring buffer is flushed)

#### Scenario: Stop ends capture
- **WHEN** `ta_stop()` is called while capture is active
- **THEN** the PortAudio stream is stopped
- **AND** remaining buffered frames are retained for `ta_poll()` to drain
- **AND** `ta_poll()` returns `-2` after all buffered frames are drained

#### Scenario: Stop while not capturing is safe
- **WHEN** `ta_stop()` is called while not capturing
- **THEN** `ta_stop()` returns `0` (no-op)

### Requirement: Capture state query
The DLL SHALL expose `ta_is_capturing()` that returns `1` if capture is active and `0` otherwise.

#### Scenario: Query during capture
- **WHEN** `ta_is_capturing()` is called while capture is active
- **THEN** it returns `1`

#### Scenario: Query after stop
- **WHEN** `ta_is_capturing()` is called after `ta_stop()` (and all frames drained)
- **THEN** it returns `0`

### Requirement: Poll-based chunk retrieval
The DLL SHALL expose `ta_poll(buf, buf_len)` as the sole mechanism for Lua to retrieve encoded audio. The function SHALL write one Opus frame into the provided buffer and return the number of bytes written, or a status code.

#### Scenario: Opus frame available
- **WHEN** `ta_poll(buf, buf_len)` is called
- **AND** the ring buffer contains at least one Opus frame
- **THEN** the frame is copied into `buf`
- **AND** the return value is the number of bytes written (> 0)

#### Scenario: No data ready
- **WHEN** `ta_poll(buf, buf_len)` is called
- **AND** the ring buffer is empty and capture is active
- **THEN** the return value is `0`

#### Scenario: VAD auto-stop signal
- **WHEN** `ta_poll(buf, buf_len)` is called
- **AND** VAD silence was detected (capture auto-stopped)
- **AND** all buffered frames have been drained
- **THEN** the return value is `-1`

#### Scenario: Manual stop signal
- **WHEN** `ta_poll(buf, buf_len)` is called
- **AND** `ta_stop()` was called
- **AND** all buffered frames have been drained
- **THEN** the return value is `-2`

#### Scenario: Frames drain before stop signal
- **WHEN** capture stops (VAD or manual)
- **AND** there are 5 buffered Opus frames
- **THEN** the next 5 calls to `ta_poll()` return those frames (> 0)
- **AND** the 6th call returns the stop signal (`-1` or `-2`)

### Requirement: Energy-based Voice Activity Detection
The DLL SHALL perform energy-based VAD on captured audio. When the mean absolute amplitude of audio samples falls below a configurable threshold for a configurable duration, the DLL SHALL auto-stop capture and signal via `ta_poll()` return code `-1`.

#### Scenario: Silence triggers auto-stop
- **WHEN** capture is active
- **AND** the audio energy remains below the VAD threshold for the configured silence duration
- **THEN** the PortAudio stream is stopped
- **AND** subsequent `ta_poll()` calls drain remaining frames then return `-1`

#### Scenario: Speech resumes before timeout
- **WHEN** audio energy drops below threshold
- **AND** energy rises above threshold before the silence duration elapses
- **THEN** capture continues normally (no auto-stop)

### Requirement: VAD configuration
The DLL SHALL expose `ta_set_vad(energy_threshold, silence_ms)` to configure VAD parameters at runtime. Default values SHALL be `energy_threshold = 1000` and `silence_ms = 2000`.

#### Scenario: Custom VAD settings
- **WHEN** `ta_set_vad(500, 3000)` is called before `ta_start()`
- **THEN** VAD uses energy threshold 500 and silence timeout 3000ms

#### Scenario: Default VAD settings
- **WHEN** `ta_start()` is called without prior `ta_set_vad()`
- **THEN** VAD uses energy threshold 1000 and silence timeout 2000ms

### Requirement: Audio device enumeration
The DLL SHALL expose `ta_get_device_count()`, `ta_get_device_name(index, buf, buf_len)`, and `ta_get_default_device()` for listing available capture devices.

#### Scenario: Enumerate devices
- **WHEN** `ta_get_device_count()` is called
- **THEN** it returns the number of available input (capture) devices

#### Scenario: Get device name
- **WHEN** `ta_get_device_name(0, buf, 256)` is called
- **THEN** the name of device 0 is written to `buf` as a null-terminated UTF-8 string

#### Scenario: Get default device
- **WHEN** `ta_get_default_device()` is called
- **THEN** it returns the index of the system's default capture device

### Requirement: Device selection
The DLL SHALL expose `ta_set_device(index)` to select a specific capture device. If not called, the default device is used.

#### Scenario: Select specific device
- **WHEN** `ta_set_device(2)` is called before `ta_start()`
- **THEN** capture opens device index 2

#### Scenario: Invalid device index
- **WHEN** `ta_set_device(999)` is called
- **THEN** `ta_set_device()` returns a non-zero error code
- **AND** the previously selected device (or default) remains active

### Requirement: Opus encoder configuration
The DLL SHALL expose `ta_set_opus_bitrate(bps)`, `ta_set_opus_frame_ms(ms)`, and `ta_set_opus_complexity(complexity)` for tuning the Opus encoder. Defaults SHALL be `bitrate = 24000`, `frame_ms = 20`, `complexity = 5`.

#### Scenario: Custom Opus bitrate
- **WHEN** `ta_set_opus_bitrate(16000)` is called before `ta_start()`
- **THEN** the Opus encoder uses 16kbps

#### Scenario: Custom Opus frame duration
- **WHEN** `ta_set_opus_frame_ms(40)` is called before `ta_start()`
- **THEN** each Opus frame encodes 40ms of audio

#### Scenario: Default Opus settings
- **WHEN** `ta_start()` is called without Opus config
- **THEN** the encoder uses 24kbps, 20ms frames, complexity 5

### Requirement: Lock-free SPSC ring buffer
The DLL SHALL use a single-producer single-consumer (SPSC) lock-free ring buffer to transfer Opus frames from the PortAudio callback thread to the `ta_poll()` consumer. The buffer SHALL hold at least 4 seconds of audio (~200 frames at 20ms).

#### Scenario: Normal throughput
- **WHEN** the PortAudio callback produces frames at ~50fps (20ms each)
- **AND** Lua polls at ~20fps (50ms tick)
- **THEN** no frames are lost (consumer keeps up)

#### Scenario: Ring buffer overflow
- **WHEN** the game hitches for >4 seconds
- **AND** the ring buffer fills completely
- **THEN** the oldest frames are silently dropped
- **AND** the producer continues writing new frames

### Requirement: Graceful load failure
If `talker_audio.dll` cannot be loaded via `ffi.load()`, the Lua layer SHALL catch the error via `pcall` and disable mic features without crashing.

#### Scenario: DLL not present
- **WHEN** Lua calls `pcall(ffi.load, "talker_audio")`
- **AND** the DLL file does not exist
- **THEN** `pcall` returns `false`
- **AND** mic capture functions are not available
- **AND** the game continues normally

#### Scenario: DLL present and functional
- **WHEN** Lua calls `pcall(ffi.load, "talker_audio")`
- **AND** the DLL file exists and is valid
- **THEN** `pcall` returns `true` and the FFI library object
- **AND** all `ta_*` functions are available

### Requirement: Static CRT linkage
The DLL SHALL be linked with the static C runtime (`/MT` on MSVC) to avoid requiring the Visual C++ Redistributable on end-user machines.

#### Scenario: No runtime dependency
- **WHEN** a user loads `talker_audio.dll` on a clean Windows install
- **AND** the Visual C++ Redistributable is NOT installed
- **THEN** the DLL loads successfully

### Requirement: Audio capture parameters
The DLL SHALL capture audio at 16kHz sample rate, mono, 16-bit signed integer PCM — matching the current bridge capture format and Whisper's expected input.

#### Scenario: Capture format
- **WHEN** `ta_start()` opens a capture stream
- **THEN** PortAudio is configured for 16000 Hz, 1 channel, paInt16
