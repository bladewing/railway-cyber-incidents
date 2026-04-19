from pathlib import Path

from scripts.discover.adapters.eurepoc import parse

FIXTURE = Path(__file__).parent / "fixtures" / "eurepoc_sample.csv"


def test_parse_returns_two_rail_candidates():
    csv_text = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(csv_text, discovered_at="2026-04-19")
    assert len(candidates) == 2
    assert all(c.source_id == "eurepoc" for c in candidates)
    titles = [c.title.lower() for c in candidates]
    assert any("db schenker" in t for t in titles)
    assert any("metro" in t for t in titles)


def test_parse_deduplicates_by_incident_id():
    # Fixture has two rows with incident_id=1001 (multi-receiver rows).
    csv_text = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(csv_text, discovered_at="2026-04-19")
    db_schenker = [c for c in candidates if "db schenker" in c.title.lower()]
    assert len(db_schenker) == 1
    assert db_schenker[0].raw_date == "2024-03-01"


def test_parse_filters_out_non_rail_rows():
    csv_text = FIXTURE.read_text(encoding="utf-8")
    candidates = parse(csv_text, discovered_at="2026-04-19")
    titles = [c.title.lower() for c in candidates]
    # "bakery" row has no rail keyword; "Vocational … Training" must not
    # match because 'train' is a whole-word token and 'training' is not.
    assert not any("bakery" in t for t in titles)
    assert not any("vocational" in t for t in titles)
