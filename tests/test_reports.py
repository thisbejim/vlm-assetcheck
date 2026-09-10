from __future__ import annotations

import json
from pathlib import Path

from assetcheck.cli import main
from assetcheck.report import render
from assetcheck.scan import scan_manifest


def test_json_and_sarif_reports_are_machine_readable(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"image": "missing.png"}\n', encoding="utf-8")
    result = scan_manifest(manifest)

    payload = json.loads(render(result, "json"))
    sarif = json.loads(render(result, "sarif"))

    assert payload["summary"]["errors"] == 1
    assert payload["diagnostics"][0]["code"] == "MISSING_FILE"
    assert sarif["version"] == "2.1.0"
    assert sarif["runs"][0]["results"][0]["ruleId"] == "MISSING_FILE"


def test_cli_json_and_exit_code(tmp_path: Path, capsys) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"image": "missing.png"}\n', encoding="utf-8")

    exit_code = main([str(manifest), "--format", "json"])
    output = capsys.readouterr().out

    assert exit_code == 1
    assert json.loads(output)["summary"]["errors"] == 1
