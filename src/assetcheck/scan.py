"""Manifest scanning and safety checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import unquote, urlparse

from .discover import decode_base64, decode_data_uri, discover_references, is_remote_reference
from .media import MediaInfo, inspect_media
from .model import Diagnostic, Reference, ScanOptions, ScanResult

_HEADER_BYTES = 1_048_576
_MEDIA_MIME_PREFIX = {"image": "image/", "audio": "audio/", "video": "video/"}
_IMAGE_TOKEN_RE = re.compile(r"<image>", re.IGNORECASE)


def _diag(
    severity: str,
    code: str,
    message: str,
    ref: Reference | None = None,
    *,
    line: int | None = None,
    pointer: str | None = None,
    path: str | None = None,
) -> Diagnostic:
    return Diagnostic(
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message,
        line=ref.line if ref else line,
        pointer=ref.pointer if ref else pointer,
        path=path,
    )


def _is_absolute(raw: str) -> bool:
    return Path(raw).is_absolute() or bool(re.match(r"^[A-Za-z]:[\\/]", raw))


def _has_traversal(raw: str) -> bool:
    return ".." in Path(raw.replace("\\", "/")).parts


def _path_from_reference(raw: str, root: Path) -> Path:
    parsed = urlparse(raw)
    if parsed.scheme.casefold() == "file":
        return Path(unquote(parsed.path))
    return Path(raw)


def _mime_matches(kind: str, mime: str | None) -> bool:
    if not mime or kind == "unknown":
        return True
    prefix = _MEDIA_MIME_PREFIX.get(kind)
    return prefix is None or mime.casefold().startswith(prefix)


def _extension_for(info: MediaInfo) -> set[str]:
    return {
        "png": {".png"},
        "jpeg": {".jpg", ".jpeg"},
        "gif": {".gif"},
        "webp": {".webp"},
        "wav": {".wav"},
        "mp3": {".mp3"},
        "flac": {".flac"},
        "ogg": {".ogg", ".oga"},
        "mp4": {".mp4", ".m4v", ".mov"},
        "webm": {".webm"},
    }.get(info.format, set())


def _check_media(
    ref: Reference,
    data: bytes,
    options: ScanOptions,
    *,
    display_path: str | None = None,
    declared_mime: str | None = None,
    digest: str | None = None,
) -> tuple[list[Diagnostic], MediaInfo, str]:
    diagnostics: list[Diagnostic] = []
    if not data:
        diagnostics.append(
            _diag("error", "EMPTY_MEDIA", "media value is empty", ref, path=display_path)
        )
        return diagnostics, MediaInfo("unknown", "unknown"), hashlib.sha256(data).hexdigest()
    info = inspect_media(data[:_HEADER_BYTES])
    content_digest = digest or hashlib.sha256(data).hexdigest()
    if info.kind == "unknown":
        severity = "error" if ref.media_kind != "unknown" else "warning"
        diagnostics.append(
            _diag(
                severity,
                "UNRECOGNIZED_MEDIA",
                "header does not match a supported image, audio, or video format",
                ref,
                path=display_path,
            )
        )
    elif ref.media_kind != "unknown" and info.kind != ref.media_kind:
        diagnostics.append(
            _diag(
                "error",
                "MEDIA_KIND_MISMATCH",
                f"reference is marked as {ref.media_kind} but bytes look like {info.kind}",
                ref,
                path=display_path,
            )
        )
    if declared_mime and info.mime and declared_mime.casefold() != info.mime.casefold():
        diagnostics.append(
            _diag(
                "warning",
                "MIME_MISMATCH",
                f"declared MIME {declared_mime!r} differs from detected {info.mime!r}",
                ref,
                path=display_path,
            )
        )
    if (
        ref.media_kind != "unknown"
        and declared_mime
        and not _mime_matches(ref.media_kind, declared_mime)
    ):
        diagnostics.append(
            _diag(
                "error",
                "DECLARED_KIND_MISMATCH",
                f"declared MIME {declared_mime!r} is not a {ref.media_kind} MIME type",
                ref,
                path=display_path,
            )
        )
    if info.width is not None and info.height is not None:
        if info.width == 0 or info.height == 0:
            diagnostics.append(
                _diag(
                    "error", "ZERO_DIMENSION", "media has a zero dimension", ref, path=display_path
                )
            )
        elif info.width * info.height > options.max_pixels:
            diagnostics.append(
                _diag(
                    "error",
                    "PIXEL_LIMIT",
                    f"media has {info.width * info.height:,} pixels, over the "
                    f"{options.max_pixels:,} limit",
                    ref,
                    path=display_path,
                )
            )
    return diagnostics, info, content_digest


def _read_file(path: Path, max_bytes: int) -> tuple[bytes, str | None, int | None]:
    """Read a bounded header and hash a regular file without loading it all."""

    file_stat = path.stat()
    if file_stat.st_size > max_bytes:
        return b"", None, file_stat.st_size
    digest = hashlib.sha256()
    header = bytearray()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                return b"", None, total
            digest.update(chunk)
            if len(header) < _HEADER_BYTES:
                header.extend(chunk[: _HEADER_BYTES - len(header)])
    return bytes(header), digest.hexdigest(), total


def _validate_path(
    ref: Reference, root: Path, options: ScanOptions
) -> tuple[list[Diagnostic], bytes | None, str | None]:
    diagnostics: list[Diagnostic] = []
    raw = ref.raw.strip()
    if "\x00" in raw:
        return [_diag("error", "NUL_IN_PATH", "path contains a NUL byte", ref)], None, None
    path_value = _path_from_reference(raw, root)
    if _is_absolute(str(path_value)) and not options.allow_absolute:
        diagnostics.append(
            _diag(
                "error",
                "ABSOLUTE_PATH",
                "absolute paths are disabled by default",
                ref,
                path=str(path_value),
            )
        )
        return diagnostics, None, None
    if _has_traversal(str(path_value)):
        diagnostics.append(
            _diag(
                "error", "PATH_TRAVERSAL", "path contains '..' traversal", ref, path=str(path_value)
            )
        )
        return diagnostics, None, None
    candidate = path_value if path_value.is_absolute() else root / path_value
    candidate_abs = Path(os.path.abspath(candidate))
    root_abs = Path(os.path.abspath(root))
    try:
        if (
            os.path.commonpath([str(candidate_abs), str(root_abs)]) != str(root_abs)
            and not options.allow_absolute
        ):
            diagnostics.append(
                _diag(
                    "error",
                    "PATH_ESCAPE",
                    "path resolves outside the configured root",
                    ref,
                    path=str(candidate_abs),
                )
            )
            return diagnostics, None, None
    except ValueError:
        diagnostics.append(
            _diag(
                "error",
                "PATH_ESCAPE",
                "path cannot be compared with the configured root",
                ref,
                path=str(candidate_abs),
            )
        )
        return diagnostics, None, None
    if not candidate_abs.exists():
        diagnostics.append(
            _diag(
                "error",
                "MISSING_FILE",
                "referenced file does not exist",
                ref,
                path=str(candidate_abs),
            )
        )
        return diagnostics, None, None
    if candidate_abs.is_symlink() or os.path.realpath(candidate_abs) != str(candidate_abs):
        if not options.allow_symlinks:
            diagnostics.append(
                _diag(
                    "error",
                    "SYMLINK_PATH",
                    "symlinked media is disabled by default",
                    ref,
                    path=str(candidate_abs),
                )
            )
            return diagnostics, None, None
    if not candidate_abs.is_file() or not stat.S_ISREG(candidate_abs.stat().st_mode):
        diagnostics.append(
            _diag(
                "error",
                "NOT_REGULAR_FILE",
                "reference is not a regular file",
                ref,
                path=str(candidate_abs),
            )
        )
        return diagnostics, None, None
    size = candidate_abs.stat().st_size
    if size == 0:
        diagnostics.append(
            _diag("error", "EMPTY_MEDIA", "referenced file is empty", ref, path=str(candidate_abs))
        )
        return diagnostics, None, None
    if size > options.max_bytes:
        diagnostics.append(
            _diag(
                "error",
                "BYTE_LIMIT",
                f"file is {size:,} bytes, over the {options.max_bytes:,} limit",
                ref,
                path=str(candidate_abs),
            )
        )
        return diagnostics, None, None
    try:
        data, digest, actual_size = _read_file(candidate_abs, options.max_bytes)
    except OSError as exc:
        diagnostics.append(
            _diag(
                "error", "READ_ERROR", f"could not read media: {exc}", ref, path=str(candidate_abs)
            )
        )
        return diagnostics, None, None
    if digest is None:
        if actual_size is not None and actual_size > options.max_bytes:
            diagnostics.append(
                _diag(
                    "error",
                    "BYTE_LIMIT",
                    f"file is {actual_size:,} bytes, over the {options.max_bytes:,} limit",
                    ref,
                    path=str(candidate_abs),
                )
            )
        return diagnostics, None, None
    ext = candidate_abs.suffix.casefold()
    info = inspect_media(data[:_HEADER_BYTES])
    allowed_exts = _extension_for(info)
    if allowed_exts and ext and ext not in allowed_exts:
        diagnostics.append(
            _diag(
                "warning",
                "EXTENSION_MISMATCH",
                f"extension {ext!r} does not match detected {info.format}",
                ref,
                path=str(candidate_abs),
            )
        )
    return diagnostics, data, digest


def _validate_reference(
    ref: Reference, root: Path, options: ScanOptions
) -> tuple[list[Diagnostic], bytes | None, str | None]:
    if ref.source == "url" or is_remote_reference(ref.raw):
        return (
            [
                _diag(
                    "warning",
                    "REMOTE_REFERENCE",
                    "remote URL was not fetched; provide a local file or data URI for byte checks",
                    ref,
                )
            ],
            None,
            None,
        )
    if ref.source == "data_uri":
        try:
            decoded = decode_data_uri(ref.raw)
            if decoded is None:
                raise ValueError("not a data URI")
            decoded_data, mime = decoded
        except ValueError as exc:
            return [_diag("error", "INVALID_DATA_URI", str(exc), ref)], None, None
        if len(decoded_data) > options.max_bytes:
            return (
                [
                    _diag(
                        "error",
                        "BYTE_LIMIT",
                        f"inline data is {len(decoded_data):,} bytes, over the "
                        f"{options.max_bytes:,} limit",
                        ref,
                    )
                ],
                None,
                None,
            )
        diagnostics, _, digest = _check_media(ref, decoded_data, options, declared_mime=mime)
        return diagnostics, decoded_data, digest
    if ref.source == "base64":
        try:
            base64_data = decode_base64(ref.raw)
        except ValueError as exc:
            return [_diag("error", "INVALID_BASE64", str(exc), ref)], None, None
        if len(base64_data) > options.max_bytes:
            return (
                [
                    _diag(
                        "error",
                        "BYTE_LIMIT",
                        f"inline data is {len(base64_data):,} bytes, over the "
                        f"{options.max_bytes:,} limit",
                        ref,
                    )
                ],
                None,
                None,
            )
        diagnostics, _, digest = _check_media(ref, base64_data, options)
        return diagnostics, base64_data, digest
    path_diagnostics, path_data, path_digest = _validate_path(ref, root, options)
    if path_data is None or path_digest is None:
        return path_diagnostics, path_data, path_digest
    media_diagnostics, _, _ = _check_media(
        ref,
        path_data,
        options,
        display_path=str(_path_from_reference(ref.raw, root)),
        digest=path_digest,
    )
    path_diagnostics.extend(media_diagnostics)
    return path_diagnostics, path_data, path_digest


def scan_manifest(
    manifest: str | Path, options: ScanOptions | None = None, *, stdin: TextIO | None = None
) -> ScanResult:
    """Scan a JSONL manifest and return deterministic findings."""

    chosen = options or ScanOptions()
    manifest_path = str(manifest)
    if manifest_path == "-":
        root = Path(chosen.root or Path.cwd()).resolve()
        handle: TextIO = stdin or sys.stdin
        should_close = False
    else:
        source_path = Path(manifest).expanduser()
        root = Path(chosen.root or source_path.parent).resolve()
        handle = source_path.open("r", encoding="utf-8")
        should_close = True
    result = ScanResult(manifest=manifest_path, root=str(root), _fail_on_warn=chosen.fail_on_warn)
    rows: list[tuple[int, Any]] = []
    references: list[Reference] = []
    try:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                result.diagnostics.append(
                    _diag(
                        "warning", "BLANK_LINE", "blank JSONL line", line=line_number, pointer="/"
                    )
                )
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                result.diagnostics.append(
                    _diag(
                        "error",
                        "INVALID_JSON",
                        f"invalid JSON: {exc.msg}",
                        line=line_number,
                        pointer="/",
                    )
                )
                continue
            rows.append((line_number, record))
            index = len(rows) - 1
            found = discover_references(record, line=line_number, record_index=index)
            references.extend(found)
    except OSError as exc:
        result.diagnostics.append(
            _diag("error", "MANIFEST_READ_ERROR", f"could not read manifest: {exc}")
        )
        return result
    finally:
        if should_close:
            handle.close()
    result.records = len(rows)
    result.references = len(references)
    seen_hashes: dict[str, Reference] = {}
    unique_hashes: set[str] = set()
    for ref in references:
        diagnostics, _, digest = _validate_reference(ref, root, chosen)
        result.diagnostics.extend(diagnostics)
        if digest:
            unique_hashes.add(digest)
            previous = seen_hashes.get(digest)
            if previous is not None and previous.pointer != ref.pointer:
                result.diagnostics.append(
                    _diag(
                        "info",
                        "DUPLICATE_ASSET",
                        f"same bytes as line {previous.line} {previous.pointer}",
                        ref,
                    )
                )
            else:
                seen_hashes[digest] = ref
    result.unique_assets = len(unique_hashes)
    if chosen.check_placeholders:
        refs_by_record: dict[int, int] = defaultdict(int)
        for ref in references:
            if ref.media_kind == "image":
                refs_by_record[ref.record_index] += 1
        for index, (record_line, record) in enumerate(rows):
            marker_count = len(_IMAGE_TOKEN_RE.findall(json.dumps(record, ensure_ascii=False)))
            if marker_count and marker_count != refs_by_record.get(index, 0):
                result.diagnostics.append(
                    _diag(
                        "warning",
                        "PLACEHOLDER_MISMATCH",
                        f"record has {marker_count} <image> token(s) but "
                        f"{refs_by_record.get(index, 0)} image reference(s)",
                        line=record_line,
                        pointer="/",
                    )
                )
    return result
