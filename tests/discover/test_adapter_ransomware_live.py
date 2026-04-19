import json
from pathlib import Path

from scripts.discover.adapters.ransomware_live import parse

FIXTURE = Path(__file__).parent / "fixtures" / "ransomware_live_sample.json"


def test_parse_keeps_rail_victim_drops_bakery():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candidates = parse(payload, discovered_at="2026-04-19")
    assert len(candidates) == 1
    c = candidates[0]
    assert "db schenker" in c.title.lower()
    assert c.source_id == "ransomware_live"
    assert c.source_type == "leak_site"
    assert c.raw_date == "2024-03-01"
