from __future__ import annotations

from slaif_ocr.extractors import (
    extract_amounts,
    extract_dates,
    extract_external_document_no,
    extract_invoice_number,
    extract_vat_id,
    normalize_amount,
    normalize_date,
)
from slaif_ocr.schema import ValidationStatus


def test_normalize_date_supports_slovenian_formats() -> None:
    assert normalize_date("15. 06. 2026") == "2026-06-15"
    assert normalize_date("15/6/2026") == "2026-06-15"
    assert normalize_date("2026-6-15") == "2026-06-15"
    assert normalize_date("31.02.2026") is None


def test_normalize_amount_supports_slovenian_formats() -> None:
    assert normalize_amount("1.234,56") == "1234.56"
    assert normalize_amount("1234,56") == "1234.56"
    assert normalize_amount("1234.56") == "1234.56"
    assert normalize_amount("1.234") == "1234"


def test_date_and_amount_extractors_return_valid_normalized_values() -> None:
    text = "\n".join(
        [
            "Datum računa: 15. 06. 2026",
            "Rok plačila: 30. 06. 2026",
            "Znesek brez DDV: 1.234,56",
            "DDV: 274,00",
            "Skupaj z DDV: 1.508,56",
        ]
    )

    dates = extract_dates(text)
    amounts = extract_amounts(text)

    assert dates["document_date"].value == "2026-06-15"
    assert dates["document_date"].validation_status is ValidationStatus.valid
    assert dates["due_date"].value == "2026-06-30"
    assert dates["due_date"].validation_status is ValidationStatus.valid

    assert amounts["amount"].value == "1234.56"
    assert amounts["amount"].validation_status is ValidationStatus.valid
    assert amounts["vat_amount"].value == "274.00"
    assert amounts["vat_amount"].validation_status is ValidationStatus.valid
    assert amounts["amount_including_vat"].value == "1508.56"
    assert amounts["amount_including_vat"].validation_status is ValidationStatus.valid


def test_invalid_date_evidence_is_marked_invalid() -> None:
    field = extract_dates("Datum računa: 31.02.2026")["document_date"]

    assert field.value is None
    assert field.validation_status is ValidationStatus.invalid
    assert field.raw == "Datum računa: 31.02.2026"


def test_multiple_vat_ids_are_ambiguous() -> None:
    field = extract_vat_id("ID za DDV: SI12345678\nVAT ID: SI87654321")

    assert field.value is None
    assert field.validation_status is ValidationStatus.ambiguous
    assert field.candidates == ["SI12345678", "SI87654321"]


def test_invoice_number_extraction_accepts_label_proximate_value() -> None:
    field = extract_external_document_no("Št. računa: 26A0647")

    assert field.value == "26A0647"
    assert field.raw == "Št. računa: 26A0647"
    assert field.validation_status is ValidationStatus.valid
    assert extract_invoice_number("Št. računa: 26A0647").value == "26A0647"


def test_ambiguous_invoice_number_values_return_null() -> None:
    field = extract_external_document_no("Št. računa: A-100\nDokument št.: B-200")

    assert field.value is None
    assert field.validation_status is ValidationStatus.ambiguous
    assert field.candidates == ["A-100", "B-200"]


def test_missing_values_remain_null() -> None:
    date_fields = extract_dates("")
    amount_fields = extract_amounts("")

    assert extract_vat_id("").value is None
    assert extract_vat_id("").validation_status is ValidationStatus.missing
    assert extract_external_document_no("").value is None
    assert extract_external_document_no("").validation_status is ValidationStatus.missing

    for field in date_fields.values():
        assert field.value is None
        assert field.validation_status is ValidationStatus.missing

    for field in amount_fields.values():
        assert field.value is None
        assert field.validation_status is ValidationStatus.missing
