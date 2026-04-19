"""Pass 2 — dedup against existing incidents. Deterministic first, Haiku on ambiguity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from scripts.discover.candidate import Candidate
from scripts.discover.llm import call_haiku_json

DATE_WINDOW_DAYS = 7
JACCARD_FLOOR = 0.5

_DEFAULT_INCIDENTS_DIR = Path(__file__).resolve().parents[2] / "incidents"


@dataclass(frozen=True)
class _Existing:
    id: str
    event_date: date | None
    urls: frozenset[str]
    tokens: frozenset[str]
    description_en: str


@dataclass(frozen=True)
class DedupResult:
    duplicate_of: str | None
    reason: str
    kept: bool
    used_llm: bool
    meta: dict | None = None


def _tokens(*parts: str) -> frozenset[str]:
    joined = " ".join(p.lower() for p in parts if p)
    return frozenset(t for t in re.split(r"\W+", joined) if len(t) >= 3)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_iso(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


@lru_cache(maxsize=16)
def _load_existing(incidents_dir: Path) -> tuple[_Existing, ...]:
    out: list[_Existing] = []
    for path in sorted(incidents_dir.glob("*.yaml")):
        if path.name == "TEMPLATE.yaml":
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(doc, dict):
            continue
        urls = frozenset(
            (s or {}).get("url", "") for s in (doc.get("sources") or [])
            if isinstance(s, dict) and s.get("url")
        )
        tokens = _tokens(doc.get("target_organization") or "",
                         doc.get("description_en") or "")
        out.append(
            _Existing(
                id=str(doc.get("id", path.stem)),
                event_date=_parse_iso(str(doc.get("event_date") or "")),
                urls=urls,
                tokens=tokens,
                description_en=str(doc.get("description_en") or ""),
            )
        )
    return tuple(out)


DEDUP_PROMPT = """\
You are deciding whether a newly-discovered candidate is the SAME incident
as any of the existing incidents below. Answer JSON ONLY:
{{"duplicate_of": "<incident id>" | null, "reason": "<=20 words"}}

Candidate:
  title: {title}
  date: {date}
  url: {url}
  excerpt: {excerpt}

Possibly matching existing incidents:
{existing}
"""


def _render_existing(e: _Existing) -> str:
    return f"- id: {e.id}\n  date: {e.event_date}\n  description: {e.description_en[:300]}"


def dedup(c: Candidate, *, incidents_dir: Path = _DEFAULT_INCIDENTS_DIR) -> DedupResult:
    existing = _load_existing(incidents_dir)

    # Exact URL match
    for e in existing:
        if c.url in e.urls:
            return DedupResult(e.id, "exact URL match", kept=False, used_llm=False)

    cand_date = _parse_iso(c.raw_date)
    cand_tokens = _tokens(c.title, c.excerpt)

    ambiguous: list[_Existing] = []
    for e in existing:
        if not cand_date or not e.event_date:
            continue
        if abs((cand_date - e.event_date).days) > DATE_WINDOW_DAYS:
            continue
        if _jaccard(cand_tokens, e.tokens) >= JACCARD_FLOOR:
            ambiguous.append(e)

    if not ambiguous:
        return DedupResult(None, "no match", kept=True, used_llm=False)

    rendered = "\n".join(_render_existing(e) for e in ambiguous[:3])
    prompt = DEDUP_PROMPT.format(
        title=c.title,
        date=c.raw_date or "unknown",
        url=c.url,
        excerpt=(c.excerpt or "")[:500],
        existing=rendered,
    )
    parsed, meta = call_haiku_json(prompt)
    dup = parsed.get("duplicate_of")
    reason = str(parsed.get("reason", ""))[:200]
    if dup:
        return DedupResult(str(dup), reason, kept=False, used_llm=True, meta=meta)
    return DedupResult(None, reason or "llm says distinct", kept=True, used_llm=True, meta=meta)
