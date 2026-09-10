# assetcheck

`assetcheck` finds broken, unsafe, and unreadable media references in a multimodal JSONL manifest before a training job or evaluation upload. It is a small, dependency-free Python CLI: it reads local bytes, checks their headers, and never fetches URLs or sends data anywhere.

## Why this exists

Vision-language datasets often keep annotation JSONL and media in separate trees. A manifest can be valid JSON while a single typo, path escape, symlink, stale export, wrong MIME type, or oversized image fails much later in a hosted job. Framework loaders catch only the format they happen to support, and generic JSONL linters cannot prove that referenced bytes exist.

`assetcheck` is deliberately narrower: reference discovery plus local byte-level integrity. It does not run model inference, inspect image semantics, or rewrite your dataset.

## Quick start

Requires Python 3.10+.

```bash
python -m pip install vlm-assetcheck
assetcheck examples/manifest.jsonl --check-placeholders
```

The repository example is self-contained and uses a one-pixel PNG data URI, so it does not need a download. To check a manifest whose paths are relative to a dataset directory:

```bash
assetcheck annotations.jsonl --root ./dataset --format json --output assetcheck.json
```

A non-zero exit code means at least one error. Warnings (for example, a remote URL that was intentionally not fetched) do not fail a run unless `--fail-on-warn` is set.

## What it checks

- Common `image`, `image_url`, `image_path`, `audio`, `video`, `media`, and `file_name` fields, including lists and OpenAI-style `{"image_url": {"url": ...}}` objects.
- Local file existence, regular-file status, empty files, size limits, path traversal, absolute paths, and symlinks.
- PNG, JPEG, GIF, WebP, WAV, MP3, FLAC, Ogg, MP4, and WebM signatures, with image dimensions where available.
- Declared data-URI MIME types, bare base64 fields, media-kind mismatches, extension mismatches, and duplicate content by SHA-256.
- Optional `<image>` placeholder/reference count mismatches.

Remote `http`, `https`, `s3`, and similar references are reported but never fetched. Reports contain paths, hashes only through duplicate findings, and metadata—not base64 payloads or media contents.

## Reports and options

```text
assetcheck MANIFEST [--root DIR] [--format text|json|markdown|sarif]
                    [--output FILE] [--max-bytes N] [--max-pixels N]
                    [--allow-absolute] [--allow-symlinks]
                    [--fail-on-warn] [--check-placeholders]
```

Text is optimized for a terminal. JSON is stable for scripts, Markdown is convenient as a CI artifact, and SARIF can be uploaded to code-scanning interfaces. Use `-` as the manifest to read JSONL from stdin; set `--root` when stdin has no parent directory.

The default limits are 100 MiB per asset and 100 million pixels. Absolute paths and symlinks require an explicit opt-in because a manifest should not silently read outside its declared dataset root.

## Python API

```python
from assetcheck import ScanOptions, scan_manifest

result = scan_manifest("annotations.jsonl", ScanOptions(root="dataset"))
if result.errors:
    raise SystemExit(result.exit_code)
```

`ScanResult.to_dict()` is suitable for storing a JSON report. The scanner is deterministic and uses only the Python standard library.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest
ruff check .
mypy src
python -m build
```

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), the [product spec](docs/product-spec.md), and the [research notes](docs/research.md).

## License

MIT. See [LICENSE](LICENSE).
