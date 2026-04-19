"""EuRepoC adapter — Transport-sector filter over the Zenodo CSV release.

The public HTTP API is gone; the canonical artefact is now the Global
Dataset CSV on Zenodo (https://zenodo.org/records/14965395). The
dataset switched to CC-BY-NC-4.0 on 2025-04-02 — usage in this
academic-research project is compatible, but downstream redistribution
must preserve the NC clause for any EuRepoC-derived fields.
"""

from __future__ import annotations

import csv
import io

from scripts.discover.candidate import Candidate
from scripts.discover.keywords import load_rail_keywords, matches_rail


def _normalize_date(raw: str | None) -> str | None:
    """EuRepoC CSV start_date is DD.MM.YYYY or 'Not available'."""
    if not raw or raw == "Not available":
        return None
    parts = raw.split(".")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        dd, mm, yyyy = parts
        return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
    return None


def _first_url(cell: str | None) -> str | None:
    if not cell:
        return None
    # source_url cells concatenate multiple URLs with ';'.
    for candidate in cell.split(";"):
        candidate = candidate.strip()
        if candidate.startswith(("http://", "https://")):
            return candidate
    return None


def parse(csv_text: str, *, discovered_at: str) -> list[Candidate]:
    kws = load_rail_keywords()
    out: list[Candidate] = []
    seen_incidents: set[str] = set()
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # Dataset has one row per receiver; same incident_id repeats.
        # Keep only the first row per incident to avoid duplicates.
        incident_id = row.get("incident_id") or ""
        if incident_id and incident_id in seen_incidents:
            continue
        haystack = " ".join(
            row.get(col) or ""
            for col in ("receiver_name", "receiver_category", "receiver_subcategory", "name")
        )
        if not matches_rail(haystack, kws):
            continue
        url = _first_url(row.get("source_url"))
        if not url:
            continue
        seen_incidents.add(incident_id)
        name = (row.get("name") or "").strip()
        description = (row.get("description") or "").strip()
        out.append(
            Candidate(
                url=url,
                title=name or description[:120] or f"EuRepoC incident {incident_id}",
                raw_date=_normalize_date(row.get("start_date")),
                source_id="eurepoc",
                source_type="database",
                lang="en",
                excerpt=description[:500],
                discovered_at=discovered_at,
            )
        )
    return out


def fetch(url: str, *, discovered_at: str, timeout_s: int = 60) -> list[Candidate]:
    import httpx

    resp = httpx.get(
        url,
        timeout=timeout_s,
        follow_redirects=True,
        headers={"User-Agent": "railway-cyber-incidents-discover/0.1"},
    )
    resp.raise_for_status()
    return parse(resp.text, discovered_at=discovered_at)
