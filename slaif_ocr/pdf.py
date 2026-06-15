from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PdfExtractionResult:
    page_count: int
    text: str
    text_native: bool
    source: str | None
    warnings: list[str]


def extract_pdf_document(path: Path) -> PdfExtractionResult:
    warnings: list[str] = []

    fitz = _load_fitz()
    if fitz is None:
        warnings.append("PyMuPDF is not installed.")
        return PdfExtractionResult(page_count=0, text="", text_native=False, source=None, warnings=warnings)

    try:
        with fitz.open(path) as doc:
            chunks: list[str] = []
            for page in doc:
                chunks.append(page.get_text())
            text = "\n".join(chunks).strip()
            if not text:
                warnings.append("No embedded PDF text found; treat as scanned PDF.")
            return PdfExtractionResult(
                page_count=doc.page_count,
                text=text,
                text_native=bool(text),
                source="pymupdf",
                warnings=warnings,
            )
    except Exception as exc:  # pragma: no cover - depends on optional engine and PDF contents
        warnings.append(f"PyMuPDF failed: {exc}")
        return PdfExtractionResult(page_count=0, text="", text_native=False, source=None, warnings=warnings)


def _load_fitz():
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError:
        return None
    return fitz
