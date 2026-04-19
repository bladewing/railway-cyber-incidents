import json
from pathlib import Path
import jsonschema

SCHEMA = json.loads(Path("schema/incident.schema.json").read_text())


def _minimal_incident(**extra_provenance):
    return {
        "id": "2026-04-19_test",
        "schema_version": "1.0",
        "event_date": "2026-04-19",
        "event_date_precision": "day",
        "countries_impacted": ["DE"],
        "confirmation_status": "reported",
        "description_en": "Test incident for schema validation.",
        "sources": [{"url": "https://example.org/x", "type": "news"}],
        "last_updated": "2026-04-19",
        "provenance": {"needs_review": True, **extra_provenance},
    }


def test_provenance_accepts_discovered_by():
    jsonschema.validate(_minimal_incident(discovered_by="discover_incidents"), SCHEMA)


def test_provenance_accepts_aggregator():
    jsonschema.validate(_minimal_incident(aggregator="konbriefing"), SCHEMA)


def test_provenance_accepts_haiku_classify_confidence():
    jsonschema.validate(_minimal_incident(haiku_classify_confidence=0.82), SCHEMA)


def test_provenance_rejects_bad_confidence_type():
    with _pytest_raises():
        jsonschema.validate(_minimal_incident(haiku_classify_confidence="high"), SCHEMA)


def _pytest_raises():
    import pytest
    return pytest.raises(jsonschema.ValidationError)
