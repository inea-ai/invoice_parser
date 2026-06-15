from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FieldValue:
    value: Any = None
    raw: str | None = None
    confidence: float = 0.0
    source: str | None = None
    page: int | None = None
    bbox: list[float] | None = None
    validation_status: str = "missing"
    candidates: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def empty_invoice_fields() -> dict[str, dict[str, FieldValue]]:
    return {
        "supplier": {
            "name": FieldValue(),
            "vat_id": FieldValue(),
            "bc_vendor_no": FieldValue(),
        },
        "invoice": {
            "document_date": FieldValue(),
            "service_date": FieldValue(),
            "payment_date": FieldValue(),
            "due_date": FieldValue(),
            "external_document_no": FieldValue(),
            "currency_code": FieldValue(value="EUR", raw="default local currency", confidence=0.2, source="default", validation_status="defaulted"),
        },
        "amounts": {
            "amount": FieldValue(),
            "vat_amount": FieldValue(),
            "amount_including_vat": FieldValue(),
        },
        "routing": {
            "strm_code": FieldValue(),
            "strn_code": FieldValue(),
            "dms_document_type_code": FieldValue(),
            "dms_document_type": FieldValue(),
            "area": FieldValue(),
        },
    }


def fields_to_dict(fields: dict[str, dict[str, FieldValue]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {
        section: {name: value.to_dict() for name, value in values.items()}
        for section, values in fields.items()
    }
