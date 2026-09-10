from __future__ import annotations

import base64
import json
from pathlib import Path

from assetcheck.model import ScanOptions
from assetcheck.scan import scan_manifest

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
WAV_HEADER = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 16


def write_manifest(path: Path, rows: list[object]) -> None:
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def codes(result) -> set[str]:
    return {item.code for item in result.diagnostics}


def test_valid_openai_shape_data_uri_and_duplicate(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "cat.png").write_bytes(PNG_1X1)
    audio_uri = "data:audio/wav;base64," + base64.b64encode(WAV_HEADER).decode()
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"type": "image_url", "image_url": {"url": "assets/cat.png"}}],
                    }
                ]
            },
            {"image_path": "assets/cat.png", "audio": audio_uri},
        ],
    )

    result = scan_manifest(manifest)

    assert result.records == 2
    assert result.references == 3
    assert result.errors == 0
    assert result.unique_assets == 2
    assert "DUPLICATE_ASSET" in codes(result)


def test_missing_traversal_and_remote_are_actionable(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {"image": "missing.png"},
            {"image_path": "../outside.png"},
            {"image_url": "https://example.invalid/cat.png"},
        ],
    )

    result = scan_manifest(manifest)

    assert {"MISSING_FILE", "PATH_TRAVERSAL", "REMOTE_REFERENCE"} <= codes(result)
    assert result.errors == 2
    assert result.warnings == 1


def test_invalid_json_and_blank_lines_are_reported(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('\nnot-json\n{"image": "missing.png"}\n', encoding="utf-8")

    result = scan_manifest(manifest)

    assert result.records == 1
    assert {"BLANK_LINE", "INVALID_JSON", "MISSING_FILE"} <= codes(result)


def test_placeholder_check_and_fail_on_warning(tmp_path: Path) -> None:
    (tmp_path / "one.png").write_bytes(PNG_1X1)
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, [{"text": "look <image> and <image>", "image": "one.png"}])

    result = scan_manifest(manifest, ScanOptions(check_placeholders=True, fail_on_warn=True))

    assert "PLACEHOLDER_MISMATCH" in codes(result)
    assert result.exit_code == 1


def test_symlinks_are_rejected_by_default(tmp_path: Path) -> None:
    (tmp_path / "real.png").write_bytes(PNG_1X1)
    link = tmp_path / "link.png"
    link.symlink_to(tmp_path / "real.png")
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(manifest, [{"image": "link.png"}])

    result = scan_manifest(manifest)

    assert "SYMLINK_PATH" in codes(result)
    assert result.errors == 1


def test_provider_inline_shapes_and_bare_base64_are_discovered(tmp_path: Path) -> None:
    image_b64 = base64.b64encode(PNG_1X1).decode()
    audio_b64 = base64.b64encode(WAV_HEADER).decode()
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": image_b64},
            },
            {"input_audio": {"data": audio_b64, "format": "wav"}},
            {"inline_data": {"mime_type": "image/png", "data": image_b64}},
        ],
    )

    result = scan_manifest(manifest)

    assert result.references == 3
    assert result.errors == 0
    assert result.unique_assets == 2


def test_signature_kind_and_pixel_limits(tmp_path: Path) -> None:
    (tmp_path / "bad.bin").write_bytes(b"not a media container")
    (tmp_path / "photo.png").write_bytes(PNG_1X1)
    huge = bytearray(PNG_1X1)
    huge[16:20] = (20_000).to_bytes(4, "big")
    huge[20:24] = (20_000).to_bytes(4, "big")
    (tmp_path / "huge.png").write_bytes(huge)
    manifest = tmp_path / "manifest.jsonl"
    write_manifest(
        manifest,
        [
            {"image": "bad.bin"},
            {"audio": "photo.png"},
            {"image": "huge.png"},
            {"image": str(tmp_path / "photo.png")},
        ],
    )

    result = scan_manifest(manifest, ScanOptions(max_pixels=100))

    assert {"UNRECOGNIZED_MEDIA", "MEDIA_KIND_MISMATCH", "PIXEL_LIMIT", "ABSOLUTE_PATH"} <= codes(
        result
    )
