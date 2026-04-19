"""ENISA Transport Threat Landscape PDF adapter.

PDF text is pre-extracted by the fetch wrapper; `parse` is pure and
operates on paragraphs split by blank lines. One candidate per paragraph
that contains at least one rail keyword.
"""

from __future__ import annotations

import re

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail

_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _month_year_to_iso(para: str) -> str | None:
    m = _DATE_RE.search(para)
    if not m:
        return None
    month = _MONTHS[m.group(1).lower()]
    return f"{m.group(2)}-{month}"


def parse(text: str, *, pdf_url: str, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for idx, para in enumerate(paragraphs):
        if not matches_rail(para, kws):
            continue
        raw_date = _month_year_to_iso(para)
        title = para.split(".")[0][:120]
        out.append(
            Candidate(
                url=pdf_url,
                title=title,
                raw_date=raw_date,
                source_id="enisa_transport",
                source_type="advisory",
                lang="en",
                excerpt=para[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(pdf_url: str, *, discovered_at: str, timeout_s: int = 30) -> list[Candidate]:
    import httpx
    import pypdf
    import io

    resp = httpx.get(pdf_url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
    return parse(text, pdf_url=pdf_url, discovered_at=discovered_at)
