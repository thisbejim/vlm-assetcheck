"""Small, dependency-free media header recognizers.

The checker intentionally inspects headers only. It does not invoke image/video
decoders, decompress archives, or execute codecs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MediaInfo:
    format: str
    kind: str
    mime: str | None = None
    width: int | None = None
    height: int | None = None


def _jpeg_info(data: bytes) -> MediaInfo | None:
    if len(data) < 3 or data[:2] != b"\xff\xd8":
        return None
    index = 2
    while index + 3 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = int.from_bytes(data[index : index + 2], "big")
        if length < 2 or index + length > len(data):
            break
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(
            range(0xCD, 0xD0)
        ):
            if length >= 7:
                height = int.from_bytes(data[index + 3 : index + 5], "big")
                width = int.from_bytes(data[index + 5 : index + 7], "big")
                return MediaInfo("jpeg", "image", "image/jpeg", width, height)
        index += length
    return MediaInfo("jpeg", "image", "image/jpeg")


def inspect_media(data: bytes) -> MediaInfo:
    """Identify a media container from a bounded header sample."""

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        if len(data) >= 24:
            width = int.from_bytes(data[16:20], "big")
            height = int.from_bytes(data[20:24], "big")
            return MediaInfo("png", "image", "image/png", width, height)
        return MediaInfo("png", "image", "image/png")
    jpeg = _jpeg_info(data)
    if jpeg is not None:
        return jpeg
    if data.startswith((b"GIF87a", b"GIF89a")):
        if len(data) >= 10:
            width = int.from_bytes(data[6:8], "little")
            height = int.from_bytes(data[8:10], "little")
            return MediaInfo("gif", "image", "image/gif", width, height)
        return MediaInfo("gif", "image", "image/gif")
    if data.startswith(b"RIFF") and len(data) >= 12:
        riff_type = data[8:12]
        if riff_type == b"WEBP":
            if len(data) >= 30 and data[12:16] == b"VP8X":
                width = 1 + int.from_bytes(data[24:27], "little")
                height = 1 + int.from_bytes(data[27:30], "little")
                return MediaInfo("webp", "image", "image/webp", width, height)
            return MediaInfo("webp", "image", "image/webp")
        if riff_type == b"WAVE":
            return MediaInfo("wav", "audio", "audio/wav")
    if data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0):
        return MediaInfo("mp3", "audio", "audio/mpeg")
    if data.startswith(b"fLaC"):
        return MediaInfo("flac", "audio", "audio/flac")
    if data.startswith(b"OggS"):
        return MediaInfo("ogg", "audio", "audio/ogg")
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return MediaInfo("mp4", "video", "video/mp4")
    if data.startswith(b"\x1aE\xdf\xa3"):
        return MediaInfo("webm", "video", "video/webm")
    return MediaInfo("unknown", "unknown")
