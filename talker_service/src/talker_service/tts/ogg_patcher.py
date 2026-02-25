"""
X-Ray OGG Vorbis comment patcher.

X-Ray engine stores spatial audio parameters inside the OGG Vorbis comment
packet as a 24-byte binary blob (NOT a standard text comment).  Files
without this blob get zero min/max distance — inaudible in 3D.

Comment format (24 bytes, little-endian):
    u32  version       (must be 3)
    f32  min_dist      (minimum hearing distance in metres)
    f32  max_dist      (maximum hearing distance in metres)
    f32  base_volume   (1.0 = full volume)
    u32  game_type     (bit-flags for the engine's sound categories)
    f32  max_ai_dist   (AI hearing distance in metres)

Game voice files typically use:
    version=3, min_dist=2.0, max_dist=50.0, volume=1.0,
    game_type=0x20004000, ai_dist=30.0

This module patches standard ffmpeg-produced OGG files by replacing the
Vorbis comment page with one carrying the X-Ray binary metadata.
"""

import struct
from typing import Optional
from loguru import logger

# ── OGG CRC-32 (Castagnoli variant used by the OGG framing spec) ──────────

_CRC_POLY = 0x04C11DB7

def _build_crc_table():
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            if r & 0x80000000:
                r = ((r << 1) ^ _CRC_POLY) & 0xFFFFFFFF
            else:
                r = (r << 1) & 0xFFFFFFFF
        table.append(r)
    return table

_CRC_TABLE = _build_crc_table()


def _ogg_crc(data: bytes) -> int:
    """Compute the OGG page CRC-32."""
    crc = 0
    for b in data:
        crc = ((crc << 8) ^ _CRC_TABLE[((crc >> 24) & 0xFF) ^ b]) & 0xFFFFFFFF
    return crc


# ── X-Ray comment blob ────────────────────────────────────────────────────

def build_xray_comment(
    min_dist: float = 2.0,
    max_dist: float = 50.0,
    base_volume: float = 1.0,
    game_type: int = 0x20004000,
    max_ai_dist: float = 30.0,
) -> bytes:
    """Build the 24-byte X-Ray binary OGG-comment blob."""
    return struct.pack('<IfffIf', 3, min_dist, max_dist, base_volume, game_type, max_ai_dist)


# ── OGG page parser / builder ─────────────────────────────────────────────

_OGGS = b'OggS'
_HEADER_SIZE = 27  # fixed portion before segment table


def _parse_pages(data: bytes) -> list[dict]:
    """Parse an OGG bitstream into a list of page dicts."""
    pages = []
    pos = 0
    while pos < len(data):
        if data[pos:pos + 4] != _OGGS:
            break
        version = data[pos + 4]
        header_type = data[pos + 5]
        granule = struct.unpack_from('<q', data, pos + 6)[0]
        serial = struct.unpack_from('<I', data, pos + 14)[0]
        seq_no = struct.unpack_from('<I', data, pos + 18)[0]
        crc = struct.unpack_from('<I', data, pos + 22)[0]
        n_segments = data[pos + 26]
        seg_table = data[pos + 27 : pos + 27 + n_segments]
        payload_len = sum(seg_table)
        payload_start = pos + 27 + n_segments
        payload = data[payload_start : payload_start + payload_len]
        pages.append({
            'version': version,
            'header_type': header_type,
            'granule': granule,
            'serial': serial,
            'seq_no': seq_no,
            'n_segments': n_segments,
            'seg_table': seg_table,
            'payload': payload,
            'raw': data[pos : payload_start + payload_len],
        })
        pos = payload_start + payload_len
    return pages


def _build_page(
    version: int,
    header_type: int,
    granule: int,
    serial: int,
    seq_no: int,
    payload: bytes,
) -> bytes:
    """Build a single OGG page with a single packet, computing CRC."""
    # Segment table: payloads up to 255 bytes per segment, then a 0-length
    # segment to terminate (for packets < 255*N bytes).
    segs = []
    remaining = len(payload)
    while remaining >= 255:
        segs.append(255)
        remaining -= 255
    segs.append(remaining)          # final segment (0..254), terminates packet

    return _build_page_raw(version, header_type, granule, serial, seq_no,
                           bytes(segs), payload)


def _build_page_raw(
    version: int,
    header_type: int,
    granule: int,
    serial: int,
    seq_no: int,
    seg_table: bytes,
    payload: bytes,
) -> bytes:
    """Build a single OGG page with an explicit segment table, computing CRC."""
    n_segments = len(seg_table)

    # Build header with CRC = 0 first (for calculation)
    header = struct.pack(
        '<4sBBqIII B',
        _OGGS,
        version,
        header_type,
        granule,
        serial,
        seq_no,
        0,              # CRC placeholder
        n_segments,
    )
    page_no_crc = header + seg_table + payload
    crc = _ogg_crc(page_no_crc)

    # Re-pack with real CRC (offset 22..25)
    page = bytearray(page_no_crc)
    struct.pack_into('<I', page, 22, crc)
    return bytes(page)


# ── Vorbis comment packet builder ─────────────────────────────────────────

_VORBIS_COMMENT_TYPE = b'\x03vorbis'


def _build_vorbis_comment_packet(xray_blob: bytes) -> bytes:
    """Build a complete Vorbis comment packet with one X-Ray user-comment.

    Layout:
        [0x03] [vorbis]  – packet type marker
        [u32]  vendor_len
        [...]  vendor_string
        [u32]  num_comments = 1
        [u32]  comment_len
        [...]  comment_data  (the X-Ray 24-byte blob)
        [0x01] – framing bit
    """
    vendor = b'Xiph.Org libVorbis I 20050304'  # match game files
    parts = [
        _VORBIS_COMMENT_TYPE,
        struct.pack('<I', len(vendor)),
        vendor,
        struct.pack('<I', 1),               # 1 user comment
        struct.pack('<I', len(xray_blob)),
        xray_blob,
        b'\x01',                            # framing bit
    ]
    return b''.join(parts)


# ── Public API ─────────────────────────────────────────────────────────────

def patch_ogg_xray(
    ogg_data: bytes,
    min_dist: float = 2.0,
    max_dist: float = 50.0,
    base_volume: float = 1.0,
    game_type: int = 0x20004000,
    max_ai_dist: float = 30.0,
) -> Optional[bytes]:
    """Replace the Vorbis comment page in *ogg_data* with X-Ray metadata.

    Returns patched bytes, or ``None`` on failure.
    """
    pages = _parse_pages(ogg_data)
    if len(pages) < 3:
        logger.error("OGG has fewer than 3 pages — cannot patch comment")
        return None

    # Page 0 = identification header, Page 1 = comment header (+ possibly setup header)
    comment_page = pages[1]
    if _VORBIS_COMMENT_TYPE not in comment_page['payload']:
        logger.error("Page 1 does not contain a Vorbis comment packet")
        return None

    # The comment and setup headers may share the same page.  Parse the
    # segment table to find the boundary between the comment packet and
    # any subsequent data (the Vorbis setup header).
    seg_table = list(comment_page['seg_table'])
    comment_packet_len = 0
    seg_idx = 0
    for seg_idx, seg_len in enumerate(seg_table):
        comment_packet_len += seg_len
        if seg_len < 255:          # packet boundary
            seg_idx += 1
            break
    # Everything after the comment packet is the setup header (if present)
    setup_bytes = comment_page['payload'][comment_packet_len:]

    xray_blob = build_xray_comment(min_dist, max_dist, base_volume, game_type, max_ai_dist)
    new_comment_packet = _build_vorbis_comment_packet(xray_blob)

    # Combine new comment packet + preserved setup header as the page payload
    combined_payload = new_comment_packet + setup_bytes

    # Build segment table for the combined payload (two packets)
    combined_segs: list[int] = []
    # -- comment packet segments
    rem = len(new_comment_packet)
    while rem >= 255:
        combined_segs.append(255)
        rem -= 255
    combined_segs.append(rem)       # terminates comment packet
    # -- setup header segments (use original segment table entries)
    if setup_bytes:
        for s in seg_table[seg_idx:]:
            combined_segs.append(s)

    new_page = _build_page_raw(
        version=comment_page['version'],
        header_type=comment_page['header_type'],
        granule=comment_page['granule'],
        serial=comment_page['serial'],
        seq_no=comment_page['seq_no'],
        seg_table=bytes(combined_segs),
        payload=combined_payload,
    )

    # Reassemble: page 0 (raw) + new comment page + pages 2..N (raw)
    result = pages[0]['raw'] + new_page
    for p in pages[2:]:
        result += p['raw']

    return result
