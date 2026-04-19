"""Loader for aggregators.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

_CONFIG = Path(__file__).resolve().parents[2] / "aggregators.yaml"


@dataclass(frozen=True)
class AggregatorConfig:
    id: str
    kind: str
    enabled: bool
    source_type: str
    url: str | None = None
    pdfs: tuple[str, ...] = field(default_factory=tuple)


def load_aggregators(path: Path = _CONFIG) -> list[AggregatorConfig]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[AggregatorConfig] = []
    for entry in data["aggregators"]:
        out.append(
            AggregatorConfig(
                id=entry["id"],
                kind=entry["kind"],
                enabled=entry.get("enabled", True),
                source_type=entry["source_type"],
                url=entry.get("url"),
                pdfs=tuple(entry.get("pdfs") or ()),
            )
        )
    return out
