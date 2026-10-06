"""Tiny lossless RGB PNG encoder, avoids adding Pillow to the Isaac runtime."""
from __future__ import annotations
import struct
import zlib
from .core import ProtocolError


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def encode_rgb_bytes(width: int, height: int, pixels: bytes) -> bytes:
    if not (1 <= width <= 4096 and 1 <= height <= 4096):
        raise ProtocolError("PNG dimensions out of range")
    if len(pixels) != width * height * 3:
        raise ProtocolError("Expected tightly packed 8-bit RGB data")
    stride = width * 3
    scanlines = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(scanlines, level=3)) + _chunk(b"IEND", b"")


def encode_array(array) -> bytes:
    # numpy 来自 Isaac Sim；离线测试核心不需要 numpy。
    import numpy as np
    rgb = np.asarray(array)
    if rgb.ndim != 3 or rgb.shape[2] not in (3, 4) or rgb.dtype != np.uint8:
        raise ProtocolError(f"Expected uint8 HxWx3/4 image, got {rgb.shape}/{rgb.dtype}")
    rgb = np.ascontiguousarray(rgb[:, :, :3])
    return encode_rgb_bytes(rgb.shape[1], rgb.shape[0], rgb.tobytes())
