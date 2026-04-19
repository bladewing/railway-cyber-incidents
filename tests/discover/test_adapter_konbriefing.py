from pathlib import Path

from scripts.discover.adapters.konbriefing import parse
from scripts.discover.candidate import Candidate

FIXTURE = Path(__file__).parent / "fixtures" / "konbriefing_sample.html"


def test_parse_keeps_rail_entries_and_drops_non_rail():
    html = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(html, discovered_at="2026-04-19")
    assert len(candidates) == 2
    titles = [c.title.lower() for c in candidates]
    assert any("db schenker" in t for t in titles)
    assert any("metro" in t for t in titles)
    assert not any("bakery" in t for t in titles)


def test_parse_extracts_fields_for_first_candidate():
    html = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(html, discovered_at="2026-04-19")
    c = candidates[0]
    assert isinstance(c, Candidate)
    assert c.url.startswith("https://")
    assert "db schenker" in c.title.lower()
    assert c.raw_date == "2024-03-01"
    assert c.source_id == "konbriefing"
    assert c.source_type == "news"
    assert c.lang == "en"
    assert c.discovered_at == "2026-04-19"
