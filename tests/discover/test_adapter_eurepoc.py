import json
from pathlib import Path

from scripts.discover.adapters.eurepoc import parse

FIXTURE = Path(__file__).parent / "fixtures" / "eurepoc_sample.json"


def test_parse_returns_two_rail_candidates():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candidates = parse(payload, discovered_at="2026-04-19")
    assert len(candidates) == 2
    ids = [c.source_id for c in candidates]
    assert ids == ["eurepoc", "eurepoc"]
    assert candidates[0].raw_date == "2024-03-01"
    assert "db schenker" in candidates[0].title.lower()
