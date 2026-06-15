from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class OcrEvidence:
    page: int
    text: str
    confidence: float | None
    bbox: list[float] | None
    engine: str
    engine_version: str | None
    preprocessing: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "preprocessing": self.preprocessing,
        }


@dataclass(frozen=True)
class OcrAdapterResult:
    engine: str
    engine_version: str | None
    available: bool
    warnings: list[str] = field(default_factory=list)
    evidence: list[OcrEvidence] = field(default_factory=list)

    def to_engine_record(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "engine_version": self.engine_version,
            "available": self.available,
            "warnings": list(self.warnings),
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class LocalOcrRun:
    engines: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    evidence: list[OcrEvidence] = field(default_factory=list)


class OcrAdapter(Protocol):
    name: str

    def run(self, path: Path) -> OcrAdapterResult: ...
