from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .mappings import exact_strm_matches
from .schema import FieldValue


DATE_RE = r"(?P<date>\b\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4}\b|\b\d{4}-\d{1,2}-\d{1,2}\b)"
AMOUNT_RE = r"(?P<amount>-?\d{1,3}(?:[.\s]\d{3})*(?:,\d{2})|-?\d+(?:,\d{2})?)"

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
    ],
    "payment_date": [
        "datum plačila",
        "datum placila",
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
    ],
    "vat_amount": [
        "ddv",
        "znesek ddv",
    ],
    "amount_including_vat": [
        "skupaj",
        "za plačilo",
        "za placilo",
        "znesek za plačilo",
        "znesek za placilo",
    ],
}


def extract_dates(text: str) -> dict[str, FieldValue]:
    return {
        field_name: _find_labeled_date(text, labels, field_name)
        for field_name, labels in DATE_LABELS.items()
    }


def extract_amounts(text: str) -> dict[str, FieldValue]:
    return {
        field_name: _find_labeled_amount(text, labels, field_name)
        for field_name, labels in AMOUNT_LABELS.items()
    }


def extract_vat_id(text: str) -> FieldValue:
    candidates = []
    for match in re.finditer(r"\bSI\s*[-]?\s*(\d{8})\b", text, flags=re.IGNORECASE):
        raw = match.group(0)
        value = "SI" + match.group(1)
        candidates.append((value, raw))

    unique = sorted({value for value, _raw in candidates})
    if len(unique) == 1:
        raw = next(raw for value, raw in candidates if value == unique[0])
        return FieldValue(
            value=unique[0],
            raw=raw,
            confidence=0.86,
            source="regex",
            validation_status="valid",
        )
    if len(unique) > 1:
        return FieldValue(
            value=None,
            raw=None,
            confidence=0.0,
            source="regex",
            validation_status="ambiguous",
            candidates=unique,
            notes=["Multiple VAT IDs found; manual or vendor lookup required."],
        )
    return FieldValue()


def extract_external_document_no(text: str) -> FieldValue:
    labels = [
        "št. računa",
        "st. racuna",
        "številka računa",
        "stevilka racuna",
        "račun št",
        "racun st",
        "dokument št",
        "dokument st",
    ]
    for label in labels:
        pattern = re.compile(
            rf"(?i){re.escape(label)}\.?\s*[:\-]?\s*(?P<value>[A-Z0-9][A-Z0-9./\- ]{{2,35}})"
        )
        match = pattern.search(text)
        if match:
            value = re.sub(r"\s+", " ", match.group("value")).strip(" .:-")
            return FieldValue(
                value=value,
                raw=match.group(0).strip(),
                confidence=0.72,
                source="regex",
                validation_status="candidate",
            )
    return FieldValue()


def extract_strm_code(text: str, mappings: dict[str, str]) -> FieldValue:
    matches = exact_strm_matches(text, mappings)
    if len(matches) == 1:
        code = matches[0]
        return FieldValue(
            value=code,
            raw=code,
            confidence=0.78,
            source="mapping_exact_match",
            validation_status="valid",
            notes=[f"Maps to {mappings[code]}"],
        )
    if len(matches) > 1:
        return FieldValue(
            value=None,
            raw=None,
            confidence=0.0,
            source="mapping_exact_match",
            validation_status="ambiguous",
            candidates=matches,
            notes=["Multiple STRM mapping codes found."],
        )
    return FieldValue()


def _find_labeled_date(text: str, labels: list[str], field_name: str) -> FieldValue:
    candidates: list[tuple[str, str]] = []
    for label in labels:
        pattern = re.compile(rf"(?i){re.escape(label)}\s*[:\-]?\s*.{{0,40}}?{DATE_RE}")
        for match in pattern.finditer(text):
            raw_date = match.group("date")
            normalized = normalize_date(raw_date)
            if normalized:
                candidates.append((normalized, match.group(0).strip()))

    return _single_candidate_field(candidates, source="regex", confidence=0.82, field_name=field_name)


def _find_labeled_amount(text: str, labels: list[str], field_name: str) -> FieldValue:
    candidates: list[tuple[str, str]] = []
    for label in labels:
        pattern = re.compile(rf"(?i){re.escape(label)}\s*[:\-]?\s*.{{0,50}}?{AMOUNT_RE}")
        for match in pattern.finditer(text):
            raw_amount = match.group("amount")
            normalized = normalize_amount(raw_amount)
            if normalized is not None:
                candidates.append((str(normalized), match.group(0).strip()))

    return _single_candidate_field(candidates, source="regex", confidence=0.70, field_name=field_name)


def _single_candidate_field(
    candidates: list[tuple[str, str]],
    source: str,
    confidence: float,
    field_name: str,
) -> FieldValue:
    unique = sorted({value for value, _raw in candidates})
    if len(unique) == 1:
        raw = next(raw for value, raw in candidates if value == unique[0])
        return FieldValue(
            value=unique[0],
            raw=raw,
            confidence=confidence,
            source=source,
            validation_status="valid",
        )
    if len(unique) > 1:
        return FieldValue(
            value=None,
            raw=None,
            confidence=0.0,
            source=source,
            validation_status="ambiguous",
            candidates=unique,
            notes=[f"Multiple candidates found for {field_name}."],
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


def normalize_amount(raw: str) -> Decimal | None:
    cleaned = raw.replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
