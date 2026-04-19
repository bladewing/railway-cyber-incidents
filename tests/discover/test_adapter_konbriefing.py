from pathlib import Path

from scripts.discover.adapters.konbriefing import parse
from scripts.discover.candidate import Candidate

FIXTURE = Path(__file__).parent / "fixtures" / "konbriefing_sample.html"


def test_parse_extracts_candidates_from_fixture():
    html = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(html, discovered_at="2026-04-19")
    assert len(candidates) == 2
    c = candidates[0]
    assert isinstance(c, Candidate)
    assert c.url.startswith("https://")
    assert "db schenker" in c.title.lower()
    assert c.raw_date == "2024-03-01"
    assert c.source_id == "konbriefing"
    assert c.source_type == "news"
    assert c.lang == "en"
    assert c.discovered_at == "2026-04-19"
