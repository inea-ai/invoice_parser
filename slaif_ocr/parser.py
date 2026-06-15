from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .pdf import PdfExtractionResult, extract_pdf_document
from .schema import DocumentMetadata, InvoiceOutput, ReviewStatus, empty_invoice_fields


def default_root() -> Path:
    return Path(".")


def default_invoice_dir(root: Path) -> Path:
    return root / "data" / "invoice"


def default_json_dir(root: Path) -> Path:
    return root / "ocr" / "json"


def list_invoices(invoice_dir: Path) -> list[Path]:
    if not invoice_dir.exists():
        return []
    return sorted(path for path in invoice_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")


def parse_invoice(path: Path, root: Path | None = None, write_json: bool = True, out_dir: Path | None = None) -> dict[str, Any]:
    root = root or default_root()
    out_dir = out_dir or default_json_dir(root)

    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path}")

    pdf_document = extract_pdf_document(path)
    output = empty_parse_output(path, pdf_document)
    output_data = output.model_dump(mode="json")

    if write_json:
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{path.stem}.json"
        output_path.write_text(json.dumps(output_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {**output_data, "output_file": str(output_path)}

    return output_data


def empty_parse_output(path: Path, pdf_document: PdfExtractionResult | None = None) -> InvoiceOutput:
    document = DocumentMetadata(page_count=0, text_native=False)
    warnings: list[str] = []
    if pdf_document is not None:
        document = DocumentMetadata(page_count=pdf_document.page_count, text_native=pdf_document.text_native)
        warnings.extend(pdf_document.warnings)

    return InvoiceOutput(
        parser_version=__version__,
        source_file=str(path),
        source_name=path.name,
        source_sha256=sha256_file(path),
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        document=document,
        engines=[],
        fields=empty_invoice_fields(),
        warnings=warnings,
        review_status=ReviewStatus.needs_review,
    )


def batch_parse(invoice_dir: Path, root: Path | None = None, out_dir: Path | None = None) -> list[dict[str, Any]]:
    root = root or default_root()
    results = []
    for pdf in list_invoices(invoice_dir):
        results.append(parse_invoice(pdf, root=root, write_json=True, out_dir=out_dir))
    return results


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
