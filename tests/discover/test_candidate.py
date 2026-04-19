import json

from scripts.discover.candidate import Candidate


def test_candidate_roundtrip_json():
    c = Candidate(
        url="https://example.org/a",
        title="Rail hit",
        raw_date="2024-03-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="snippet",
        discovered_at="2026-04-19",
    )
    payload = c.to_dict()
    assert json.loads(json.dumps(payload)) == payload
    assert Candidate.from_dict(payload) == c


def test_candidate_requires_absolute_url():
    import pytest
    with pytest.raises(ValueError):
        Candidate(
            url="/relative",
            title="t",
            raw_date="2024-01-01",
            source_id="x",
            source_type="news",
            lang="en",
            excerpt="",
            discovered_at="2026-04-19",
        )
