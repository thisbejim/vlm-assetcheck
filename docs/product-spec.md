# Product spec: assetcheck 0.1

## User and job

The user is a VLM data or evaluation engineer with a JSONL annotation manifest and a local media tree. Before paying for a hosted upload or waiting for a training job, they need a deterministic answer to: “Can every media reference be safely opened from this checkout, and do the bytes match what the row says?”

## Problem boundary

In scope: discover common media-reference fields; resolve relative paths; reject unsafe paths; inspect bounded file/data-URI headers; report missing, empty, oversized, malformed, mismatched, remote, and duplicate assets with line and JSON Pointer locations.

Out of scope: semantic image quality, OCR, model inference, dataset rewriting, downloading remote media, complete provider-specific schema validation, and a hosted service.

## Product contract

- Python 3.10+, standard library only at runtime.
- Same input and options produce the same findings and exit status.
- No network access and no writes to referenced media.
- Text, JSON, Markdown, and SARIF reports share stable diagnostic codes.
- Exit 0 for no errors (or warnings without `--fail-on-warn`), 1 for findings, and 2 for invocation/read failures.

## Success criteria

1. A user can run one command against a JSONL file and identify the exact line, pointer, and path for every broken reference.
2. A clean, self-contained example works without credentials or network access.
3. CI catches path traversal, symlink, size, signature, data-URI, and placeholder regressions.
4. The tool stays useful when provider APIs or hosted upload behavior changes because it validates local evidence, not a remote endpoint.
