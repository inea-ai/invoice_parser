from __future__ import annotations

import re
from datetime import date
from typing import Callable

from .mappings import exact_strm_matches
from .schema import FieldValue, ValidationStatus


DATE_TOKEN_RE = r"(?P<value>\b\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}\b|\b\d{4}-\d{1,2}-\d{1,2}\b)"
AMOUNT_TOKEN_RE = r"(?P<value>-?\d{1,3}(?:[.\s]\d{3})*(?:[.,]\d{2})|-?\d+(?:[.,]\d{2})?)"
VAT_ID_TOKEN_RE = r"(?P<value>SI\s*[-]?\s*\d{1,8})"
INVOICE_NO_TOKEN_RE = r"(?P<value>[A-Z0-9][A-Z0-9./\- ]{1,35})"

DATE_LABELS = {
    "document_date": [
        "datum dokumenta",
        "datum računa",
        "datum izdaje",
        "datum fakture",
    ],
    "service_date": [
        "datum opravljene storitve",
        "datum storitve",
        "opravljena storitev",
        "datum dobave",
    ],
    "payment_date": [
        "datum plačila",
        "datum placila",
        "plačano dne",
        "placano dne",
    ],
    "due_date": [
        "rok plačila",
        "rok placila",
        "datum zapadlosti",
        "zapadlost",
        "valuta",
    ],
}

AMOUNT_LABELS = {
    "amount": [
        "osnova",
        "znesek brez ddv",
        "neto",
        "davčna osnova",
        "davcna osnova",
    ],
    "vat_amount": [
        "ddv",
        "znesek ddv",
        "davek",
    ],
    "amount_including_vat": [
        "skupaj",
        "za plačilo",
        "za placilo",
        "znesek za plačilo",
        "znesek za placilo",
        "skupaj z ddv",
    ],
}

VAT_ID_LABELS = [
    "id za ddv",
    "davčna št.",
    "davcna st.",
    "vat",
    "vat id",
]

INVOICE_NO_LABELS = [
    "št. računa",
    "st. racuna",
    "številka računa",
    "stevilka racuna",
    "račun št.",
    "racun st.",
    "dokument št.",
    "dokument st.",
]


def extract_dates(text: str) -> dict[str, FieldValue]:
    return {
        field_name: _extract_labeled_field(
            text=text,
            labels=labels,
            value_pattern=DATE_TOKEN_RE,
            normalizer=normalize_date,
            field_name=field_name,
            source="text_regex",
            confidence=0.93,
            invalid_note="A date-like value was found but it is not a valid calendar date.",
        )
        for field_name, labels in DATE_LABELS.items()
    }


def extract_amounts(text: str) -> dict[str, FieldValue]:
    return {
        field_name: _extract_labeled_field(
            text=text,
            labels=labels,
            value_pattern=AMOUNT_TOKEN_RE,
            normalizer=normalize_amount,
            field_name=field_name,
            source="text_regex",
            confidence=0.91,
            invalid_note="An amount-like value was found but it could not be normalized.",
        )
        for field_name, labels in AMOUNT_LABELS.items()
    }


def extract_vat_id(text: str) -> FieldValue:
    return _extract_labeled_field(
        text=text,
        labels=VAT_ID_LABELS,
        value_pattern=VAT_ID_TOKEN_RE,
        normalizer=normalize_vat_id,
        field_name="supplier.vat_id",
        source="text_regex",
        confidence=0.96,
        invalid_note="A VAT ID-like value was found but it is not a valid Slovenian VAT ID.",
    )


def extract_external_document_no(text: str) -> FieldValue:
    return _extract_labeled_field(
        text=text,
        labels=INVOICE_NO_LABELS,
        value_pattern=INVOICE_NO_TOKEN_RE,
        normalizer=normalize_invoice_number,
        field_name="invoice.external_document_no",
        source="text_regex",
        confidence=0.88,
        invalid_note="An invoice-number-like value was found but it could not be normalized.",
    )


def extract_invoice_number(text: str) -> FieldValue:
    return extract_external_document_no(text)


def extract_strm_code(text: str, mappings: dict[str, str]) -> FieldValue:
    matches = exact_strm_matches(text, mappings)
    if len(matches) == 1:
        code = matches[0]
        return FieldValue(
            value=code,
            raw=code,
            confidence=0.78,
            source="mapping_exact_match",
            validation_status=ValidationStatus.valid,
            notes=[f"Maps to {mappings[code]}"],
        )
    if len(matches) > 1:
        return FieldValue(
            value=None,
            raw=None,
            confidence=0.0,
            source="mapping_exact_match",
            validation_status=ValidationStatus.ambiguous,
            candidates=matches,
            notes=["Multiple STRM mapping codes found."],
        )
    return FieldValue()


def _extract_labeled_field(
    text: str,
    labels: list[str],
    value_pattern: str,
    normalizer: Callable[[str], str | None],
    field_name: str,
    source: str,
    confidence: float,
    invalid_note: str,
) -> FieldValue:
    valid_candidates: list[tuple[str, str]] = []
    invalid_evidence: list[str] = []

    for label in labels:
        pattern = re.compile(
            rf"(?im)^\s*[-*]?\s*{re.escape(label)}\s*[:\-]?\s*[\s\S]{{0,80}}?{value_pattern}"
        )
        for match in pattern.finditer(text):
            raw_value = match.group("value")
            normalized = normalizer(raw_value)
            raw_evidence = match.group(0).strip()
            if normalized is None:
                invalid_evidence.append(raw_evidence)
            else:
                valid_candidates.append((normalized, raw_evidence))

    return _finalize_field(
        valid_candidates=valid_candidates,
        invalid_evidence=invalid_evidence,
        source=source,
        confidence=confidence,
        field_name=field_name,
        invalid_note=invalid_note,
    )


def _finalize_field(
    valid_candidates: list[tuple[str, str]],
    invalid_evidence: list[str],
    source: str,
    confidence: float,
    field_name: str,
    invalid_note: str,
) -> FieldValue:
    unique = sorted({value for value, _raw in valid_candidates})
    if len(unique) == 1:
        raw = next(raw for value, raw in valid_candidates if value == unique[0])
        return FieldValue(
            value=unique[0],
            raw=raw,
            confidence=confidence,
            source=source,
            validation_status=ValidationStatus.valid,
        )
    if len(unique) > 1:
        return FieldValue(
            value=None,
            raw=None,
            confidence=0.0,
            source=source,
            validation_status=ValidationStatus.ambiguous,
            candidates=unique,
            notes=[f"Multiple candidates found for {field_name}."],
        )
    if invalid_evidence:
        return FieldValue(
            value=None,
            raw=invalid_evidence[0],
            confidence=0.0,
            source=source,
            validation_status=ValidationStatus.invalid,
            notes=[invalid_note],
        )
    return FieldValue()


def normalize_date(raw: str) -> str | None:
    cleaned = re.sub(r"\s+", "", raw)
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", cleaned):
        year, month, day = [int(part) for part in cleaned.split("-")]
    else:
        parts = re.split(r"[./-]", cleaned)
        if len(parts) != 3:
            return None
        day, month, year = [int(part) for part in parts]
        if year < 100:
            year += 2000

    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def normalize_amount(raw: str) -> str | None:
    cleaned = re.sub(r"[\s\u00a0]", "", raw)
    if not cleaned:
        return None

    sign = ""
    if cleaned.startswith("-"):
        sign = "-"
        cleaned = cleaned[1:]

    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        normalized = cleaned.replace(".", "").replace(",", ".")
    elif cleaned.count(".") > 1:
        normalized = cleaned.replace(".", "")
    elif "." in cleaned:
        whole, fractional = cleaned.split(".", 1)
        if len(fractional) == 3 and whole.isdigit() and fractional.isdigit():
            normalized = whole + fractional
        else:
            normalized = cleaned
    else:
        normalized = cleaned

    normalized = sign + normalized
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", normalized):
        return None
    return normalized


def normalize_vat_id(raw: str) -> str | None:
    cleaned = re.sub(r"[\s\-]", "", raw.upper())
    if re.fullmatch(r"SI\d{8}", cleaned):
        return cleaned
    return None


def normalize_invoice_number(raw: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", raw).strip(" .:-")
    return cleaned or None
