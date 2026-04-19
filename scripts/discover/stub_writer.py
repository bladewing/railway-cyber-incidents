"""Stub YAML writer. Produces incidents/drafts/<id>.yaml with needs_review: true."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import yaml

from scripts.discover.candidate import Candidate
from scripts.discover.classify import ClassifyVerdict
from scripts.discover.extract import ExtractedFields
from scripts.discover.summarize import SummaryResult


_UMLAUT = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss",
                         "Ä": "a", "Ö": "o", "Ü": "u"})


def _slugify(s: str) -> str:
    s = s.translate(_UMLAUT).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:40] or "unknown"


def _build_id(c: Candidate, fields: ExtractedFields) -> str:
    event_date = fields.event_date or (c.raw_date or date.today().isoformat())[:10]
    if fields.target_organization:
        slug = _slugify(fields.target_organization)
    else:
        h = hashlib.sha1(c.url.encode()).hexdigest()[:4]
        slug = f"{c.source_id}-{h}"
    return f"{event_date}_{slug}"


def _stub_dict(c: Candidate, verdict: ClassifyVerdict, fields: ExtractedFields,
               summary: SummaryResult, today: str) -> dict:
    incident_id = _build_id(c, fields)
    return {
        "id": incident_id,
        "schema_version": "1.0",
        "event_date": fields.event_date,
        "event_date_precision": fields.event_date_precision,
        "reported_date": fields.reported_date,
        "countries_impacted": list(fields.countries_impacted) or [],
        "region": None,
        "coordinates": None,
        "target_organization": fields.target_organization,
        "industry_sector": None,
        "operator_type": None,
        "attack_vector": None,
        "supply_chain": None,
        "malware": None,
        "extortion": None,
        "motive": None,
        "mitre_attack_techniques": None,
        "threat_actor": None,
        "threat_actor_country": None,
        "attribution_confidence": None,
        "confirmation_status": "reported",
        "affected_systems": None,
        "data_published": None,
        "impact": {
            "scope": None,
            "duration_hours": None,
            "magnitude": {
                "affected_trains": None,
                "affected_passengers": None,
                "monetary_damage_eur": None,
            },
            "data_compromise": {
                "intellectual_property": None,
                "organizational_data": None,
                "customer_data": None,
            },
        },
        "description_en": summary.description_en,
        "description_de": summary.description_de,
        "sources": [
            {
                "url": c.url,
                "type": c.source_type,
                "publisher": None,
                "published_date": None,
                "language": c.lang,
                "accessed_date": today,
            }
        ],
        "provenance": {
            "needs_review": True,
            "discovered_by": "discover_incidents",
            "aggregator": c.source_id,
            "haiku_classify_confidence": round(verdict.confidence, 2),
        },
        "contributors": ["discover_incidents"],
        "last_updated": today,
        "notes": None,
    }


def write_stub(
    c: Candidate,
    verdict: ClassifyVerdict,
    fields: ExtractedFields,
    summary: SummaryResult,
    *,
    drafts_dir: Path,
    today: str | None = None,
) -> Path:
    today = today or date.today().isoformat()
    doc = _stub_dict(c, verdict, fields, summary, today)
    drafts_dir.mkdir(parents=True, exist_ok=True)
    out_path = drafts_dir / f"{doc['id']}.yaml"
    with out_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
    return out_path
