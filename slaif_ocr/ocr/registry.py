from __future__ import annotations

import os
from pathlib import Path

from .models import LocalOcrRun, OcrAdapter
from .tesseract import TesseractAdapter


def parse_local_adapter_names(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [name.strip().lower() for name in raw.split(",") if name.strip()]


def configured_local_adapters(raw: str | None = None) -> list[OcrAdapter]:
    adapter_names = parse_local_adapter_names(raw if raw is not None else os.getenv("OCR_LOCAL_ADAPTERS"))
    adapters: list[OcrAdapter] = []
    for name in adapter_names:
        adapter = _adapter_for_name(name)
        if adapter is not None:
            adapters.append(adapter)
    return adapters


def run_configured_local_adapters(path: Path, raw: str | None = None) -> LocalOcrRun:
    adapter_names = parse_local_adapter_names(raw if raw is not None else os.getenv("OCR_LOCAL_ADAPTERS"))
    engines: list[dict[str, object]] = []
    warnings: list[str] = []
    evidence = []

    for name in adapter_names:
        adapter = _adapter_for_name(name)
        if adapter is None:
            warnings.append(f"Unsupported OCR adapter: {name}")
            continue
        result = adapter.run(path)
        engines.append(result.to_engine_record())
        warnings.extend(result.warnings)
        evidence.extend(result.evidence)

    return LocalOcrRun(engines=engines, warnings=warnings, evidence=evidence)


def _adapter_for_name(name: str) -> OcrAdapter | None:
    if name == "tesseract":
        return TesseractAdapter()
    return None
