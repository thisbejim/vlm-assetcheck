"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .model import ScanOptions
from .report import render
from .scan import scan_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="assetcheck",
        description=(
            "Check local media references in a multimodal JSONL manifest without fetching "
            "or uploading data."
        ),
    )
    parser.add_argument("manifest", help="JSONL manifest path, or '-' for stdin")
    parser.add_argument("--root", type=Path, help="root used to resolve relative media paths")
    parser.add_argument("--format", choices=["text", "json", "markdown", "sarif"], default="text")
    parser.add_argument("--output", type=Path, help="write the report to a file instead of stdout")
    parser.add_argument("--max-bytes", type=int, default=100 * 1024 * 1024, metavar="N")
    parser.add_argument("--max-pixels", type=int, default=100_000_000, metavar="N")
    parser.add_argument("--allow-absolute", action="store_true", help="allow absolute local paths")
    parser.add_argument("--allow-symlinks", action="store_true", help="allow symlinked media")
    parser.add_argument(
        "--fail-on-warn", action="store_true", help="return exit code 1 when warnings exist"
    )
    parser.add_argument(
        "--check-placeholders",
        action="store_true",
        help="compare <image> tokens with image references",
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the assetcheck CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.max_bytes <= 0 or args.max_pixels <= 0:
        parser.error("--max-bytes and --max-pixels must be positive")
    options = ScanOptions(
        root=args.root,
        max_bytes=args.max_bytes,
        max_pixels=args.max_pixels,
        allow_absolute=args.allow_absolute,
        allow_symlinks=args.allow_symlinks,
        fail_on_warn=args.fail_on_warn,
        check_placeholders=args.check_placeholders,
    )
    try:
        result = scan_manifest(args.manifest, options)
        report = render(result, args.format)
        if args.output:
            args.output.write_text(report, encoding="utf-8")
        else:
            sys.stdout.write(report)
        return result.exit_code
    except (OSError, ValueError) as exc:
        print(f"assetcheck: {exc}", file=sys.stderr)
        return 2
