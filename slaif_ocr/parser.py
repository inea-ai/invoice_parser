from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .extractors import extract_amounts, extract_dates, extract_external_document_no, extract_strm_code, extract_vat_id
from .mappings import load_mapping_context
from .schema import empty_invoice_fields, fields_to_dict
from .text_extract import extract_text


def default_root() -> Path:
    return Path.cwd()


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
    path = path.resolve()
    out_dir = out_dir or default_json_dir(root)

    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a PDF file, got: {path}")

    mapping_context = load_mapping_context(root)
    text_result = extract_text(path)
    text = text_result.text

    fields = empty_invoice_fields()
    warnings = [*mapping_context.warnings, *text_result.warnings]

    if text:
        for field_name, value in extract_dates(text).items():
            fields["invoice"][field_name] = value
        for field_name, value in extract_amounts(text).items():
            fields["amounts"][field_name] = value
        fields["supplier"]["vat_id"] = extract_vat_id(text)
        fields["invoice"]["external_document_no"] = extract_external_document_no(text)
        fields["routing"]["strm_code"] = extract_strm_code(text, mapping_context.strm_accounts)
    else:
        warnings.append("No source text available; field extraction was not attempted.")

    output = {
        "schema_version": "0.1",
        "parser_version": __version__,
        "source_file": str(path),
        "source_name": path.name,
        "source_sha256": sha256_file(path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "text_extraction": {
            "source": text_result.source,
            "text_length": len(text),
            "text_excerpt": text[:1200] if text else "",
        },
        "fields": fields_to_dict(fields),
        "warnings": warnings,
        "review_status": "needs_review",
    }

    if write_json:
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"{path.stem}.json"
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        output["output_file"] = str(output_path.resolve())

    return output


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
