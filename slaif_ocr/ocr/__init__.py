from __future__ import annotations

from .models import LocalOcrRun, OcrAdapterResult, OcrEvidence
from .registry import configured_local_adapters, parse_local_adapter_names, run_configured_local_adapters
from .tesseract import TesseractAdapter

__all__ = [
    "LocalOcrRun",
    "OcrAdapterResult",
    "OcrEvidence",
    "TesseractAdapter",
    "configured_local_adapters",
    "parse_local_adapter_names",
    "run_configured_local_adapters",
]
