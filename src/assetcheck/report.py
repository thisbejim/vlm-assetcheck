"""Human and machine-readable report renderers."""

from __future__ import annotations

import json
from typing import Any

from .model import ScanResult


def _summary(result: ScanResult) -> str:
    return (
        f"{result.records} records, {result.references} references, "
        f"{result.unique_assets} unique assets; "
        f"{result.errors} errors, {result.warnings} warnings, {result.infos} infos"
    )


def render_text(result: ScanResult) -> str:
    """Render concise CLI output."""

    lines = [f"assetcheck: {_summary(result)}"]
    for item in result.diagnostics:
        location = ""
        if item.line is not None:
            location += f"line {item.line}"
        if item.pointer:
            location += f" {item.pointer}"
        if item.path:
            location += f" [{item.path}]"
        if location:
            location += ": "
        lines.append(f"{item.severity.upper()} {item.code} {location}{item.message}")
    return "\n".join(lines) + "\n"


def render_markdown(result: ScanResult) -> str:
    """Render a report suitable for a CI artifact or issue."""

    lines = [
        "# assetcheck report",
        "",
        f"**Manifest:** `{result.manifest}`  ",
        f"**Root:** `{result.root}`  ",
        f"**Summary:** {_summary(result)}",
        "",
        "| Severity | Code | Location | Message |",
        "| --- | --- | --- | --- |",
    ]
    if not result.diagnostics:
        lines.append("| — | — | — | No findings |")
    for item in result.diagnostics:
        location = " ".join(
            filter(
                None,
                [f"line {item.line}" if item.line else "", item.pointer or "", item.path or ""],
            )
        )
        message = item.message.replace("|", "\\|")
        lines.append(f"| {item.severity} | `{item.code}` | `{location}` | {message} |")
    return "\n".join(lines) + "\n"


def render_sarif(result: ScanResult) -> str:
    """Render SARIF 2.1.0 with stable rule IDs."""

    rules: dict[str, dict[str, str]] = {}
    sarif_results: list[dict[str, Any]] = []
    for item in result.diagnostics:
        rules.setdefault(item.code, {"id": item.code, "name": item.code})
        location: dict[str, Any] = {}
        if item.line is not None:
            location["physicalLocation"] = {
                "artifactLocation": {"uri": item.path or result.manifest},
                "region": {"startLine": item.line},
            }
        entry: dict[str, Any] = {
            "ruleId": item.code,
            "level": "error"
            if item.severity == "error"
            else "warning"
            if item.severity == "warning"
            else "note",
            "message": {"text": item.message + (f" ({item.pointer})" if item.pointer else "")},
        }
        if location:
            entry["locations"] = [location]
        sarif_results.append(entry)
    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "assetcheck",
                        "version": "0.1.2",
                        "rules": list(rules.values()),
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def render(result: ScanResult, output_format: str) -> str:
    """Render a scan in one of the supported formats."""

    if output_format == "json":
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"
    if output_format == "markdown":
        return render_markdown(result)
    if output_format == "sarif":
        return render_sarif(result)
    return render_text(result)
