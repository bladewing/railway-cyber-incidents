"""ransomware.live adapter — victims feed filtered by rail keywords."""

from __future__ import annotations

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail


def parse(payload: list[dict], *, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    for entry in payload:
        victim = entry.get("victim", "")
        description = entry.get("description", "") or ""
        hay = f"{victim} {description}"
        if not matches_rail(hay, kws):
            continue
        url = entry.get("post_url")
        if not url or not url.startswith(("http://", "https://")):
            continue
        raw_date = (entry.get("discovered") or "")[:10] or None
        title = f"{victim} — leak-site listing ({entry.get('group', 'unknown group')})"
        excerpt = description[:500]
        out.append(
            Candidate(
                url=url,
                title=title,
                raw_date=raw_date,
                source_id="ransomware_live",
                source_type="leak_site",
                lang="en",
                excerpt=excerpt,
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 20) -> list[Candidate]:
    import httpx

    # api.ransomware.live's IPv6 endpoint unconditionally 301s to www, which 404s.
    # Bind the client socket to an IPv4 local address to force AF_INET resolution.
    transport = httpx.HTTPTransport(local_address="0.0.0.0")
    with httpx.Client(
        transport=transport,
        timeout=timeout_s,
        follow_redirects=True,
        headers={"User-Agent": "railway-cyber-incidents-discover/0.1"},
    ) as client:
        resp = client.get(url)
    resp.raise_for_status()
    return parse(resp.json(), discovered_at=discovered_at)
