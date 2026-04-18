"""Build release artefacts in dist/ from incidents/*.yaml."""
from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

FLAT_COLUMNS = [
    "id", "event_date", "event_date_precision", "reported_date",
    "countries_impacted", "region",
    "target_organization", "industry_sector", "operator_type",
    "attack_vector", "supply_chain", "extortion", "motive",
    "threat_actor", "threat_actor_country", "attribution_confidence",
    "confirmation_status", "data_published",
    "impact_scope", "duration_hours",
    "affected_trains", "affected_passengers", "monetary_damage_eur",
    "ip_compromised", "org_data_compromised", "customer_data_compromised",
    "mitre_attack_techniques", "description_en",
]


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    return value


def _load_incidents(incidents_dir: Path) -> list[dict[str, Any]]:
    docs = []
    for path in sorted(incidents_dir.glob("*.yaml")):
        if path.name == "TEMPLATE.yaml":
            continue
        docs.append(_normalize(yaml.safe_load(path.read_text(encoding="utf-8"))))
    return docs


def _semi(values: Iterable[str] | None) -> str:
    return ";".join(values) if values else ""


def _flat_row(doc: dict[str, Any]) -> dict[str, Any]:
    impact = doc.get("impact") or {}
    magnitude = (impact.get("magnitude") or {}) if impact else {}
    data_comp = (impact.get("data_compromise") or {}) if impact else {}
    return {
        "id": doc["id"],
        "event_date": doc["event_date"],
        "event_date_precision": doc["event_date_precision"],
        "reported_date": doc.get("reported_date") or "",
        "countries_impacted": _semi(doc.get("countries_impacted")),
        "region": doc.get("region") or "",
        "target_organization": doc.get("target_organization") or "",
        "industry_sector": doc.get("industry_sector") or "",
        "operator_type": doc.get("operator_type") or "",
        "attack_vector": doc.get("attack_vector") or "",
        "supply_chain": doc.get("supply_chain"),
        "extortion": doc.get("extortion"),
        "motive": doc.get("motive") or "",
        "threat_actor": doc.get("threat_actor") or "",
        "threat_actor_country": doc.get("threat_actor_country") or "",
        "attribution_confidence": doc.get("attribution_confidence") or "",
        "confirmation_status": doc["confirmation_status"],
        "data_published": doc.get("data_published"),
        "impact_scope": impact.get("scope") or "",
        "duration_hours": impact.get("duration_hours"),
        "affected_trains": magnitude.get("affected_trains"),
        "affected_passengers": magnitude.get("affected_passengers"),
        "monetary_damage_eur": magnitude.get("monetary_damage_eur"),
        "ip_compromised": data_comp.get("intellectual_property"),
        "org_data_compromised": data_comp.get("organizational_data"),
        "customer_data_compromised": data_comp.get("customer_data"),
        "mitre_attack_techniques": _semi(doc.get("mitre_attack_techniques")),
        "description_en": (doc.get("description_en") or "").strip(),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if v is None else v) for k, v in r.items()})


def _datapackage(incidents_count: int) -> dict[str, Any]:
    return {
        "name": "railway-cyber-incidents",
        "title": "Railway Cyber Incidents",
        "version": "0.1.0",
        "licenses": [{"name": "CC-BY-4.0", "title": "Creative Commons Attribution 4.0"}],
        "resources": [
            {
                "name": "incidents",
                "path": "incidents.csv",
                "format": "csv",
                "profile": "tabular-data-resource",
                "schema": {
                    "primaryKey": "id",
                    "fields": [{"name": c, "type": "string"} for c in FLAT_COLUMNS],
                },
            },
            {
                "name": "affected_systems",
                "path": "affected_systems.csv",
                "format": "csv",
                "profile": "tabular-data-resource",
                "schema": {
                    "fields": [
                        {"name": "incident_id", "type": "string"},
                        {"name": "system", "type": "string"},
                    ],
                    "foreignKeys": [{
                        "fields": "incident_id",
                        "reference": {"resource": "incidents", "fields": "id"},
                    }],
                },
            },
            {
                "name": "sources",
                "path": "sources.csv",
                "format": "csv",
                "profile": "tabular-data-resource",
                "schema": {
                    "fields": [
                        {"name": "incident_id", "type": "string"},
                        {"name": "url", "type": "string"},
                        {"name": "type", "type": "string"},
                        {"name": "publisher", "type": "string"},
                        {"name": "published_date", "type": "date"},
                        {"name": "language", "type": "string"},
                        {"name": "accessed_date", "type": "date"},
                    ],
                    "foreignKeys": [{
                        "fields": "incident_id",
                        "reference": {"resource": "incidents", "fields": "id"},
                    }],
                },
            },
            {
                "name": "malware",
                "path": "malware.csv",
                "format": "csv",
                "profile": "tabular-data-resource",
                "schema": {
                    "fields": [
                        {"name": "incident_id", "type": "string"},
                        {"name": "name", "type": "string"},
                        {"name": "family", "type": "string"},
                        {"name": "mitre_software_id", "type": "string"},
                    ],
                    "foreignKeys": [{
                        "fields": "incident_id",
                        "reference": {"resource": "incidents", "fields": "id"},
                    }],
                },
            },
            {
                "name": "mitre_techniques",
                "path": "mitre_techniques.csv",
                "format": "csv",
                "profile": "tabular-data-resource",
                "schema": {
                    "fields": [
                        {"name": "incident_id", "type": "string"},
                        {"name": "technique_id", "type": "string"},
                    ],
                    "foreignKeys": [{
                        "fields": "incident_id",
                        "reference": {"resource": "incidents", "fields": "id"},
                    }],
                },
            },
        ],
    }


def build_release(repo_root: Path) -> Path:
    incidents = _load_incidents(repo_root / "incidents")
    dist = repo_root / "dist"
    dist.mkdir(exist_ok=True)

    # incidents.csv (flat)
    _write_csv(dist / "incidents.csv", [_flat_row(d) for d in incidents], FLAT_COLUMNS)

    # incidents.jsonl (full nested)
    with (dist / "incidents.jsonl").open("w", encoding="utf-8") as f:
        for d in incidents:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # affected_systems.csv
    rows = [
        {"incident_id": d["id"], "system": s}
        for d in incidents for s in (d.get("affected_systems") or [])
    ]
    _write_csv(dist / "affected_systems.csv", rows, ["incident_id", "system"])

    # sources.csv
    rows = [
        {
            "incident_id": d["id"],
            "url": s["url"],
            "type": s["type"],
            "publisher": s.get("publisher") or "",
            "published_date": s.get("published_date") or "",
            "language": s.get("language") or "",
            "accessed_date": s.get("accessed_date") or "",
        }
        for d in incidents for s in d["sources"]
    ]
    _write_csv(
        dist / "sources.csv", rows,
        ["incident_id", "url", "type", "publisher",
         "published_date", "language", "accessed_date"],
    )

    # malware.csv
    rows = [
        {
            "incident_id": d["id"],
            "name": m["name"],
            "family": m.get("family") or "",
            "mitre_software_id": m.get("mitre_software_id") or "",
        }
        for d in incidents for m in (d.get("malware") or [])
    ]
    _write_csv(
        dist / "malware.csv", rows,
        ["incident_id", "name", "family", "mitre_software_id"],
    )

    # mitre_techniques.csv
    rows = [
        {"incident_id": d["id"], "technique_id": t}
        for d in incidents for t in (d.get("mitre_attack_techniques") or [])
    ]
    _write_csv(dist / "mitre_techniques.csv", rows, ["incident_id", "technique_id"])

    # datapackage.json
    (dist / "datapackage.json").write_text(
        json.dumps(_datapackage(len(incidents)), indent=2, ensure_ascii=False)
    )

    return dist


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    dist = build_release(repo_root)
    print(f"Release built in {dist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
