"""Public data structures used by :mod:`assetcheck`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Reference:
    """A media-like value discovered in one JSONL record."""

    line: int
    record_index: int
    pointer: str
    raw: str
    media_kind: str
    source: Literal["path", "url", "data_uri", "base64"]


@dataclass(frozen=True)
class Diagnostic:
    """A stable, machine-readable finding."""

    severity: Severity
    code: str
    message: str
    line: int | None = None
    pointer: str | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation."""

        result: dict[str, Any] = {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.pointer is not None:
            result["pointer"] = self.pointer
        if self.path is not None:
            result["path"] = self.path
        return result


@dataclass(frozen=True)
class ScanOptions:
    """Safety and reporting options for a manifest scan."""

    root: Path | str | None = None
    max_bytes: int = 100 * 1024 * 1024
    max_pixels: int = 100_000_000
    allow_absolute: bool = False
    allow_symlinks: bool = False
    fail_on_warn: bool = False
    check_placeholders: bool = False


@dataclass
class ScanResult:
    """All findings and summary data for one manifest."""

    manifest: str
    root: str
    records: int = 0
    references: int = 0
    unique_assets: int = 0
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(item.severity == "error" for item in self.diagnostics)

    @property
    def warnings(self) -> int:
        return sum(item.severity == "warning" for item in self.diagnostics)

    @property
    def infos(self) -> int:
        return sum(item.severity == "info" for item in self.diagnostics)

    @property
    def exit_code(self) -> int:
        return 1 if self.errors or self.warnings and self._fail_on_warn else 0

    _fail_on_warn: bool = field(default=False, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON report without embedding media contents."""

        return {
            "schema_version": 1,
            "manifest": self.manifest,
            "root": self.root,
            "summary": {
                "records": self.records,
                "references": self.references,
                "unique_assets": self.unique_assets,
                "errors": self.errors,
                "warnings": self.warnings,
                "infos": self.infos,
            },
            "diagnostics": [item.to_dict() for item in self.diagnostics],
        }
