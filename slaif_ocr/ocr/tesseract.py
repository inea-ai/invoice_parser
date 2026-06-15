from __future__ import annotations

import shutil
from pathlib import Path

from .models import OcrAdapterResult


class TesseractAdapter:
    name = "tesseract"

    def run(self, path: Path) -> OcrAdapterResult:
        warnings: list[str] = []
        pytesseract = _load_pytesseract()
        if pytesseract is None:
            warnings.append("pytesseract is not installed.")
            return OcrAdapterResult(
                engine=self.name,
                engine_version=None,
                available=False,
                warnings=warnings,
                evidence=[],
            )

        if shutil.which("tesseract") is None:
            warnings.append("tesseract is not installed or not on PATH.")
            return OcrAdapterResult(
                engine=self.name,
                engine_version=None,
                available=False,
                warnings=warnings,
                evidence=[],
            )

        engine_version = _tesseract_version(pytesseract)
        return OcrAdapterResult(
            engine=self.name,
            engine_version=engine_version,
            available=True,
            warnings=[],
            evidence=[],
        )


def _load_pytesseract():
    try:
        import pytesseract  # type: ignore
    except ModuleNotFoundError:
        return None
    return pytesseract


def _tesseract_version(pytesseract: object) -> str | None:
    try:
        version = getattr(pytesseract, "get_tesseract_version")()
    except Exception:  # pragma: no cover - defensive around optional engine
        return None
    return str(version)
