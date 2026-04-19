"""BSI Lagebericht PDF adapter — German-language text, same shape as ENISA."""

from __future__ import annotations

import re

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail

_DE_DATE_RE = re.compile(
    r"\b(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{4})\b",
    re.IGNORECASE,
)
_DE_MONTHS = {
    "januar": "01", "februar": "02", "märz": "03", "april": "04",
    "mai": "05", "juni": "06", "juli": "07", "august": "08",
    "september": "09", "oktober": "10", "november": "11", "dezember": "12",
}


def _de_month_year_to_iso(para: str) -> str | None:
    m = _DE_DATE_RE.search(para)
    if not m:
        return None
    return f"{m.group(2)}-{_DE_MONTHS[m.group(1).lower()]}"


def parse(text: str, *, pdf_url: str, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    for para in paragraphs:
        if not matches_rail(para, kws):
            continue
        raw_date = _de_month_year_to_iso(para)
        title = para.split(".")[0][:120]
        out.append(
            Candidate(
                url=pdf_url,
                title=title,
                raw_date=raw_date,
                source_id="bsi_lagebericht",
                source_type="advisory",
                lang="de",
                excerpt=para[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(pdf_url: str, *, discovered_at: str, timeout_s: int = 30) -> list[Candidate]:
    import io

    import httpx
    import pypdf

    resp = httpx.get(pdf_url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    reader = pypdf.PdfReader(io.BytesIO(resp.content))
    text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
    return parse(text, pdf_url=pdf_url, discovered_at=discovered_at)
