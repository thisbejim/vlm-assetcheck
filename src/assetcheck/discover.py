"""Conservative discovery of media references in common JSONL shapes."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any
from urllib.parse import urlparse

from .model import Reference

_IMAGE_KEYS = {
    "image",
    "images",
    "image_url",
    "image_urls",
    "image_path",
    "image_paths",
    "image_file",
    "image_files",
    "picture",
    "pictures",
    "photo",
    "photos",
    "visual",
    "visuals",
    "input_image",
}
_AUDIO_KEYS = {
    "audio",
    "audios",
    "audio_url",
    "audio_urls",
    "audio_path",
    "audio_paths",
    "input_audio",
}
_VIDEO_KEYS = {
    "video",
    "videos",
    "video_url",
    "video_urls",
    "video_path",
    "video_paths",
    "input_video",
}
_GENERIC_KEYS = {
    "media",
    "media_url",
    "media_urls",
    "media_path",
    "media_paths",
    "file_name",
    "file_names",
    "filename",
    "filenames",
    "inline_data",
    "inline_image",
    "inline_audio",
    "inline_video",
}
_WRAPPER_KEYS = {"url", "path", "file_name", "filename", "data", "base64", "bytes", "source"}
_PATH_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".avif",
    ".bmp",
    ".tif",
    ".tiff",
    ".wav",
    ".mp3",
    ".flac",
    ".ogg",
    ".m4a",
    ".mp4",
    ".mov",
    ".webm",
}
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/\s]+=*$")


def pointer_join(pointer: str, token: str | int) -> str:
    """Append a JSON Pointer token."""

    escaped = str(token).replace("~", "~0").replace("/", "~1")
    return f"{pointer}/{escaped}"


def _key_kind(key: str) -> str | None:
    normalized = key.casefold().replace("-", "_")
    if normalized in _IMAGE_KEYS or normalized.startswith("image_"):
        return "image"
    if normalized in _AUDIO_KEYS or normalized.startswith("audio_"):
        return "audio"
    if normalized in _VIDEO_KEYS or normalized.startswith("video_"):
        return "video"
    if normalized in _GENERIC_KEYS:
        return "unknown"
    return None


def _looks_like_base64(value: str) -> bool:
    compact = "".join(value.split())
    return len(compact) >= 8 and len(compact) % 4 == 0 and bool(_BASE64_RE.fullmatch(compact))


def _kind_from_mime(value: str) -> str:
    lowered = value.casefold()
    if lowered.startswith("image/"):
        return "image"
    if lowered.startswith("audio/"):
        return "audio"
    if lowered.startswith("video/"):
        return "video"
    return "unknown"


def _kind_from_type(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.casefold().replace("-", "_")
    if normalized in {"image", "image_url", "input_image"}:
        return "image"
    if normalized in {"audio", "input_audio"}:
        return "audio"
    if normalized in {"video", "input_video"}:
        return "video"
    return None


def _source_for(value: str, key: str | None, kind: str) -> tuple[str, str] | None:
    stripped = value.strip()
    if not stripped:
        return None
    parsed = urlparse(stripped)
    if stripped.casefold().startswith("data:"):
        return "data_uri", kind
    if (
        parsed.scheme
        and parsed.scheme.casefold() not in {"file"}
        and not re.match(r"^[A-Za-z]:[\\/]", stripped)
    ):
        return "url", kind
    if key in {"data", "base64", "bytes"} and _looks_like_base64(stripped):
        return "base64", kind
    if key in {"url"} and parsed.scheme:
        return "url", kind
    if (
        key
        in {
            "path",
            "file_name",
            "file_names",
            "filename",
            "filenames",
            "media",
            "media_url",
            "media_urls",
            "media_path",
            "media_paths",
        }
        or key is None
    ):
        return "path", kind
    if parsed.scheme == "file":
        return "path", kind
    if any(stripped.casefold().endswith(ext) for ext in _PATH_EXTENSIONS):
        return "path", kind
    # A generic media string is still useful to check as a path.
    if kind != "unknown" or key in {
        "media",
        "media_url",
        "media_urls",
        "media_path",
        "media_paths",
    }:
        return "path", kind
    return None


def _kind_from_value(value: str, kind: str) -> str:
    if kind != "unknown":
        return kind
    if value.casefold().startswith("data:"):
        mime = value[5:].split(";", 1)[0].casefold()
        if mime.startswith("image/"):
            return "image"
        if mime.startswith("audio/"):
            return "audio"
        if mime.startswith("video/"):
            return "video"
    lower = value.casefold().split("?", 1)[0]
    if lower.endswith(
        tuple({".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff"})
    ):
        return "image"
    if lower.endswith(tuple({".wav", ".mp3", ".flac", ".ogg", ".m4a"})):
        return "audio"
    if lower.endswith(tuple({".mp4", ".mov", ".webm"})):
        return "video"
    return "unknown"


def _extract(
    value: Any, kind: str, pointer: str, line: int, record_index: int, key: str | None
) -> list[Reference]:
    if isinstance(value, str):
        source_kind = _kind_from_value(value, kind)
        source = _source_for(value, key, source_kind)
        if source is None:
            return []
        return [
            Reference(
                line=line,
                record_index=record_index,
                pointer=pointer,
                raw=value,
                media_kind=source[1],
                source=source[0],  # type: ignore[arg-type]
            )
        ]
    if isinstance(value, list):
        refs: list[Reference] = []
        for index, item in enumerate(value):
            refs.extend(_extract(item, kind, pointer_join(pointer, index), line, record_index, key))
        return refs
    if isinstance(value, dict):
        refs = []
        nested_kind = kind
        for mime_key in ("mime_type", "media_type", "content_type"):
            mime_value = value.get(mime_key)
            if isinstance(mime_value, str):
                detected_kind = _kind_from_mime(mime_value)
                if detected_kind != "unknown":
                    nested_kind = detected_kind
                    break
        for child_key, child_value in value.items():
            child_kind = _key_kind(str(child_key))
            if child_key in _WRAPPER_KEYS or child_kind is not None:
                refs.extend(
                    _extract(
                        child_value,
                        nested_kind
                        if child_kind is None or child_kind == "unknown"
                        else child_kind,
                        pointer_join(pointer, str(child_key)),
                        line,
                        record_index,
                        str(child_key),
                    )
                )
        return refs
    return []


def discover_references(record: Any, *, line: int, record_index: int) -> list[Reference]:
    """Discover references without treating arbitrary text as a media path."""

    refs: list[Reference] = []

    def walk(value: Any, pointer: str, inherited_kind: str | None = None) -> None:
        if isinstance(value, dict):
            object_kind = _kind_from_type(value.get("type")) or inherited_kind
            for key, child in value.items():
                child_pointer = pointer_join(pointer, str(key))
                kind = _key_kind(str(key))
                if kind is None and str(key) in _WRAPPER_KEYS and object_kind is not None:
                    kind = object_kind
                if kind is not None:
                    refs.extend(_extract(child, kind, child_pointer, line, record_index, str(key)))
                else:
                    walk(child, child_pointer, object_kind)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, pointer_join(pointer, index), inherited_kind)

    walk(record, "")
    return refs


def is_remote_reference(value: str) -> bool:
    """Return whether a value is a non-file URL that assetcheck will not fetch."""

    parsed = urlparse(value.strip())
    stripped = value.strip()
    return bool(
        parsed.scheme
        and parsed.scheme.casefold() not in {"file", "data"}
        and not re.match(r"^[A-Za-z]:[\\/]", stripped)
    )


def decode_data_uri(value: str) -> tuple[bytes, str | None] | None:
    """Decode a base64 or percent-encoded data URI, returning bytes and MIME."""

    if not value.casefold().startswith("data:"):
        return None
    header, separator, payload = value[5:].partition(",")
    if not separator:
        raise ValueError("data URI has no comma separator")
    pieces = header.split(";")
    mime = pieces[0] or None
    if any(piece.casefold() == "base64" for piece in pieces[1:]):
        try:
            decoded = base64.b64decode("".join(payload.split()), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("invalid base64 payload") from exc
    else:
        from urllib.parse import unquote_to_bytes

        decoded = unquote_to_bytes(payload)
    return decoded, mime


def decode_base64(value: str) -> bytes:
    """Decode a bare base64 value with strict validation."""

    try:
        return base64.b64decode("".join(value.split()), validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid base64 payload") from exc
