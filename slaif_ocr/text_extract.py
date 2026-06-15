from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TextExtractionResult:
    text: str
    source: str | None
    warnings: list[str]


def extract_text(path: Path) -> TextExtractionResult:
    warnings: list[str] = []

    result = _extract_with_pymupdf(path)
    if result.text:
        return result
    warnings.extend(result.warnings)

    result = _extract_with_pypdf(path)
    if result.text:
        return result
    warnings.extend(result.warnings)

    result = _extract_with_pdftotext(path)
    if result.text:
        return result
    warnings.extend(result.warnings)

    sidecar = path.with_suffix(".txt")
    if sidecar.exists():
        return TextExtractionResult(sidecar.read_text(encoding="utf-8", errors="replace"), "sidecar_txt", warnings)

    warnings.append(
        "No PDF text extractor produced text. Install pymupdf, pypdf, or poppler-utils; scanned PDFs still require OCR."
    )
    return TextExtractionResult("", None, warnings)


def _extract_with_pymupdf(path: Path) -> TextExtractionResult:
    try:
        import fitz  # type: ignore
    except ModuleNotFoundError:
        return TextExtractionResult("", None, ["PyMuPDF is not installed."])

    try:
        chunks: list[str] = []
        with fitz.open(path) as doc:
            for page in doc:
                chunks.append(page.get_text())
        return TextExtractionResult("\n".join(chunks).strip(), "pymupdf", [])
    except Exception as exc:  # pragma: no cover - depends on optional engine
        return TextExtractionResult("", None, [f"PyMuPDF failed: {exc}"])


def _extract_with_pypdf(path: Path) -> TextExtractionResult:
    try:
        from pypdf import PdfReader  # type: ignore
    except ModuleNotFoundError:
        return TextExtractionResult("", None, ["pypdf is not installed."])

    try:
        reader = PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return TextExtractionResult(text.strip(), "pypdf", [])
    except Exception as exc:  # pragma: no cover - depends on optional engine
        return TextExtractionResult("", None, [f"pypdf failed: {exc}"])


def _extract_with_pdftotext(path: Path) -> TextExtractionResult:
    if not shutil.which("pdftotext"):
        return TextExtractionResult("", None, ["pdftotext is not installed or not on PATH."])

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "out.txt"
        proc = subprocess.run(
            ["pdftotext", "-layout", str(path), str(out_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            return TextExtractionResult("", None, [f"pdftotext failed: {proc.stderr.strip()}"])
        return TextExtractionResult(out_path.read_text(encoding="utf-8", errors="replace").strip(), "pdftotext", [])
