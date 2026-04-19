"""Pass 3 — extract structured fields from the article body (or excerpt fallback)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scripts.discover.candidate import Candidate
from scripts.discover.llm import call_haiku_json

PROMPT_TEMPLATE = """\
Extract facts from the text below. Return JSON ONLY, no prose:
{{
  "event_date": "YYYY-MM-DD" or null,
  "event_date_precision": "day" | "month" | "year",
  "countries_impacted": ["ISO-3166 alpha-2", ...],
  "target_organization": "string" or null,
  "reported_date": "YYYY-MM-DD" or null
}}

Rules:
- Prefer null over inventing a value.
- Use "day" precision only when a full date is explicit. "month" when only
  month+year is given. "year" when only the year is given.
- countries_impacted lists every country where the attack caused impact,
  ISO 3166-1 alpha-2 codes (DE, FR, IT, ...).
- target_organization is the primary victim if named; otherwise null.

Text:
{body}
"""


@dataclass(frozen=True)
class ExtractedFields:
    event_date: str | None
    event_date_precision: str
    countries_impacted: tuple[str, ...]
    target_organization: str | None
    reported_date: str | None


def _fetch_article_text(url: str, timeout_s: int = 10) -> str:
    import httpx
    from bs4 import BeautifulSoup

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)[:8000]


def _as_tuple(v: Any) -> tuple[str, ...]:
    if not isinstance(v, list):
        return ()
    return tuple(str(x) for x in v if isinstance(x, str))


def extract(c: Candidate) -> tuple[ExtractedFields, dict]:
    try:
        body = _fetch_article_text(c.url)
    except Exception:
        body = c.excerpt or c.title
    prompt = PROMPT_TEMPLATE.format(body=body[:6000])
    parsed, meta = call_haiku_json(prompt)
    return (
        ExtractedFields(
            event_date=(parsed.get("event_date") or None),
            event_date_precision=str(parsed.get("event_date_precision") or "day"),
            countries_impacted=_as_tuple(parsed.get("countries_impacted")),
            target_organization=(parsed.get("target_organization") or None),
            reported_date=(parsed.get("reported_date") or None),
        ),
        meta,
    )
