"""Candidate dataclass — the shared shape between Stage 1 and Stage 2."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Candidate:
    url: str
    title: str
    raw_date: str | None
    source_id: str
    source_type: str
    lang: str
    excerpt: str
    discovered_at: str

    def __post_init__(self) -> None:
        if not (self.url.startswith("http://") or self.url.startswith("https://")):
            raise ValueError(f"Candidate.url must be absolute http(s), got {self.url!r}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        return cls(**d)
