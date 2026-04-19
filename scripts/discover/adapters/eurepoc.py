"""EuRepoC adapter — Transport-sector filter over the public API."""

from __future__ import annotations

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail


def parse(payload: dict, *, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    for entry in payload.get("incidents", []):
        subsector = entry.get("subsector", "")
        summary = entry.get("summary", "") or ""
        name = entry.get("name", "") or ""
        # Filter: EuRepoC Transport is broader than rail; keep only rail-adjacent.
        hay = f"{subsector} {name} {summary}"
        if not matches_rail(hay, kws):
            continue
        url = entry.get("url")
        if not url or not url.startswith(("http://", "https://")):
            continue
        out.append(
            Candidate(
                url=url,
                title=name,
                raw_date=entry.get("date"),
                source_id="eurepoc",
                source_type="database",
                lang="en",
                excerpt=summary[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 20) -> list[Candidate]:
    import httpx

    resp = httpx.get(url, timeout=timeout_s, follow_redirects=True,
                     headers={"User-Agent": "railway-cyber-incidents-discover/0.1"})
    resp.raise_for_status()
    return parse(resp.json(), discovered_at=discovered_at)
