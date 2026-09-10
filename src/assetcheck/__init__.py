"""Check the integrity of media references in multimodal JSONL manifests."""

from .model import Diagnostic, Reference, ScanOptions, ScanResult
from .scan import scan_manifest

__all__ = ["Diagnostic", "Reference", "ScanOptions", "ScanResult", "scan_manifest"]
__version__ = "0.1.2"
