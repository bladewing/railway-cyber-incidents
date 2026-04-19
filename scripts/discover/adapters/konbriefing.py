"""Konbriefing adapter — parses the 'Cyber Attacks on Railways' topic page."""

from __future__ import annotations

from bs4 import BeautifulSoup

from scripts.discover.candidate import Candidate

# Selectors calibrated against the fixture in tests/discover/fixtures/konbriefing_sample.html.
# Live selector calibration deferred to first real run.
#
# NOTE: The plan suggested a union selector "ul.cyberattack-list li, ul li"
# but BeautifulSoup's select() with a comma-union returns combined (not
# deduplicated) matches from both sub-selectors, producing duplicates when
# the same elements satisfy both patterns.  Use only the specific selector;
# a broader fallback would require an explicit dedup step that masks real bugs.
_LIST_SELECTOR = "ul.cyberattack-list li"
_DATE_SELECTOR = "span.date, time"
_LINK_SELECTOR = "a[href^='http']"
_SUMMARY_SELECTOR = "p"


def parse(html: str, *, discovered_at: str) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Candidate] = []
    for item in soup.select(_LIST_SELECTOR):
        link = item.select_one(_LINK_SELECTOR)
        if link is None:
            continue
        title = link.get_text(strip=True)
        url = link["href"]
        date_el = item.select_one(_DATE_SELECTOR)
        raw_date = date_el.get_text(strip=True) if date_el else None
        summary_el = item.select_one(_SUMMARY_SELECTOR)
        excerpt = summary_el.get_text(" ", strip=True) if summary_el else ""
        if not title or not url.startswith(("http://", "https://")):
            continue
        out.append(
            Candidate(
                url=url,
                title=title,
                raw_date=raw_date,
                source_id="konbriefing",
                source_type="news",
                lang="en",
                excerpt=excerpt[:500],
                discovered_at=discovered_at,
            )
        )
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
