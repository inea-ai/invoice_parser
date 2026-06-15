from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ValidationStatus(str, Enum):
    missing = "missing"
    candidate = "candidate"
    valid = "valid"
    ambiguous = "ambiguous"
    invalid = "invalid"
    defaulted = "defaulted"
    unsupported = "unsupported"
    blocked = "blocked"


class ReviewStatus(str, Enum):
    needs_review = "needs_review"
    ready_for_review = "ready_for_review"
    blocked = "blocked"
    rejected = "rejected"
    approved = "approved"


class FieldValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any = None
    raw: str | None = None
    confidence: float = 0.0
    source: str | None = None
    page: int | None = None
    bbox: list[float] | None = None
    validation_status: ValidationStatus = ValidationStatus.missing
    candidates: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_count: int = 0
    text_native: bool = False


class InvoiceOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["0.1"] = "0.1"
    parser_version: str
    source_file: str
    source_name: str
    source_sha256: str
    created_at: str
    document: DocumentMetadata = Field(default_factory=DocumentMetadata)
    engines: list[dict[str, Any]] = Field(default_factory=list)
    fields: dict[str, dict[str, FieldValue]]
    warnings: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = ReviewStatus.needs_review

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


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
            "currency_code": FieldValue(
                value="EUR",
                raw="local default currency",
                confidence=0.2,
                source="local_default",
                validation_status=ValidationStatus.defaulted,
            ),
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
