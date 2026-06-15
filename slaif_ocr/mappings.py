from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MappingContext:
    root: Path
    mapping_dir: Path
    strm_accounts: dict[str, str]
    bc_metadata_mapping: dict[str, Any]
    warnings: list[str]


def load_mapping_context(root: Path) -> MappingContext:
    mapping_dir = root / "data" / "mapping"
    warnings: list[str] = []
    strm_accounts: dict[str, str] = {}
    bc_metadata_mapping: dict[str, Any] = {}

    if not mapping_dir.exists():
        warnings.append(f"Missing mapping folder: {mapping_dir}")
        return MappingContext(
            root=root,
            mapping_dir=mapping_dir,
            strm_accounts=strm_accounts,
            bc_metadata_mapping=bc_metadata_mapping,
            warnings=warnings,
        )

    strm_path = mapping_dir / "sm_lastni_konti_mapping.json"
    if strm_path.exists():
        try:
            strm_accounts = json.loads(strm_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append(f"Could not parse {strm_path}: {exc}")
    else:
        warnings.append(f"Missing STRM mapping file: {strm_path}")

    bc_path = mapping_dir / "ocr_to_bc_dms_metadata_mapping.json"
    if bc_path.exists():
        try:
            bc_metadata_mapping = json.loads(bc_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            warnings.append(f"Could not parse {bc_path}: {exc}")
    else:
        warnings.append(f"Missing BC metadata mapping file: {bc_path}")

    return MappingContext(
        root=root,
        mapping_dir=mapping_dir,
        strm_accounts=strm_accounts,
        bc_metadata_mapping=bc_metadata_mapping,
        warnings=warnings,
    )


def exact_strm_matches(text: str, mappings: dict[str, str]) -> list[str]:
    normalized = text.upper()
    matches: list[str] = []
    for code in mappings:
        if "X" in code.upper():
            continue
        if code.upper() in normalized:
            matches.append(code)
    return sorted(set(matches))
