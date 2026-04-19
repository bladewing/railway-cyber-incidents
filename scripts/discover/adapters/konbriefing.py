"""Konbriefing adapter — parses the generic 'Cyber Attacks' topic page
and filters for rail-adjacent entries.

The site no longer publishes a dedicated railway page; the generic
listing lives at /en-topics/cyber-attacks.html. Entries are
<article class="portfolio-item"> blocks containing a bold title div,
a flag+date div, a free-text location line, and one or more external
source links.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail

_ARTICLE_SELECTOR = "article.portfolio-item"
_TITLE_SELECTOR = 'div[style*="font-weight:bold"]'
_EXTERNAL_LINK_SELECTOR = 'a[href^="http"][target="_blank"]'

# Date formats seen on the page: "August 16, 2025", "April 1, 2025",
# "March 2025", "July 2025 ?".  Capture anything that looks like an
# English month followed by an optional day and a 4-digit year.
_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b[^\n<]{0,20}?(\d{4})"
)
_MONTHS = {
    "January": "01", "February": "02", "March": "03", "April": "04",
    "May": "05", "June": "06", "July": "07", "August": "08",
    "September": "09", "October": "10", "November": "11", "December": "12",
}


def _extract_date(article_text: str) -> str | None:
    m = _DATE_RE.search(article_text)
    if not m:
        return None
    month, year = m.group(1), m.group(2)
    # Prefer an explicit day if present adjacent to the month match.
    day_match = re.search(
        rf"{month}\s+(\d{{1,2}}),?\s+{year}", article_text
    )
    if day_match:
        return f"{year}-{_MONTHS[month]}-{int(day_match.group(1)):02d}"
    return f"{year}-{_MONTHS[month]}"


def _article_to_candidate(
    article: Tag, kws: frozenset[str], discovered_at: str
) -> Candidate | None:
    title_el = article.select_one(_TITLE_SELECTOR)
    link_el = article.select_one(_EXTERNAL_LINK_SELECTOR)
    if title_el is None or link_el is None:
        return None
    title = title_el.get_text(" ", strip=True)
    # Receiver-name line (country / operator) is the div immediately
    # following the title's parent block; include it in the match haystack
    # to catch cases where the title says "railway company" but operator
    # is only in the receiver line, and vice versa.
    receiver_el = title_el.parent.find_next_sibling("div") if title_el.parent else None
    receiver_text = receiver_el.get_text(" ", strip=True) if receiver_el else ""
    haystack = f"{title} {receiver_text}"
    if not matches_rail(haystack, kws):
        return None
    href = link_el.get("href")
    url = href if isinstance(href, str) else ""
    if not title or not url.startswith(("http://", "https://")):
        return None
    article_text = article.get_text(" ", strip=True)
    raw_date = _extract_date(article_text)
    return Candidate(
        url=url,
        title=title,
        raw_date=raw_date,
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt=article_text[:500],
        discovered_at=discovered_at,
    )


def parse(html: str, *, discovered_at: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    kws = load_rail_keywords()
    out: list[Candidate] = []
    for article in soup.select(_ARTICLE_SELECTOR):
        cand = _article_to_candidate(article, kws, discovered_at)
        if cand is not None:
            out.append(cand)
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 15) -> list[Candidate]:
    import httpx

    resp = httpx.get(
        url,
        timeout=timeout_s,
        follow_redirects=True,
        headers={"User-Agent": "railway-cyber-incidents-discover/0.1"},
    )
    resp.raise_for_status()
    return parse(resp.text, discovered_at=discovered_at)
