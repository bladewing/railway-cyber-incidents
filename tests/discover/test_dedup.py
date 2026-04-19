from pathlib import Path
from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.dedup import DedupResult, dedup

FIXTURES = Path(__file__).parent / "fixtures" / "incidents"


def _cand(url="https://new.example.org/x", title="", raw_date="2017-05-14"):
    return Candidate(
        url=url,
        title=title,
        raw_date=raw_date,
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="",
        discovered_at="2026-04-19",
    )


def test_exact_url_hit_drops_without_llm():
    c = _cand(url="https://example.org/wannacry-db")
    with patch("scripts.discover.dedup.call_haiku_json") as m:
        result = dedup(c, incidents_dir=FIXTURES)
    assert result.duplicate_of == "2017-05-13_wannacry"
    assert result.kept is False
    assert result.used_llm is False
    m.assert_not_called()


def test_no_match_passes_through_without_llm():
    c = _cand(url="https://new.example.org/unrelated", title="totally unrelated",
              raw_date="2024-02-02")
    with patch("scripts.discover.dedup.call_haiku_json") as m:
        result = dedup(c, incidents_dir=FIXTURES)
    assert result.duplicate_of is None
    assert result.kept is True
    assert result.used_llm is False
    m.assert_not_called()


def test_near_date_same_org_triggers_llm_and_drops():
    c = _cand(title="WannaCry hits Deutsche Bahn display boards", raw_date="2017-05-14")
    with patch(
        "scripts.discover.dedup.call_haiku_json",
        return_value=({"duplicate_of": "2017-05-13_wannacry", "reason": "same event"}, {"cost_usd": 0.002}),
    ) as m:
        result = dedup(c, incidents_dir=FIXTURES)
    m.assert_called_once()
    assert result.duplicate_of == "2017-05-13_wannacry"
    assert result.kept is False
    assert result.used_llm is True


def test_near_date_llm_says_not_duplicate_keeps():
    # Title chosen so Jaccard vs existing WannaCry tokens is exactly 0.5, triggering
    # the LLM tiebreak while still representing a semantically distinct event.
    #
    # Candidate tokens: {deutsche, bahn, display, boards, unrelated, outage}  (6)
    # Existing tokens:  {deutsche, bahn, wannacry, affected, display, boards} (6)
    # Intersection: {deutsche, bahn, display, boards} = 4
    # Union: {deutsche, bahn, display, boards, unrelated, outage, wannacry, affected} = 8
    # Jaccard = 4/8 = 0.5  →  meets the JACCARD_FLOOR (>=), LLM is called.
    c = _cand(title="Deutsche Bahn display boards unrelated outage", raw_date="2017-05-14")
    with patch(
        "scripts.discover.dedup.call_haiku_json",
        return_value=({"duplicate_of": None, "reason": "different event"}, {"cost_usd": 0.002}),
    ):
        result = dedup(c, incidents_dir=FIXTURES)
    assert result.duplicate_of is None
    assert result.kept is True
    assert result.used_llm is True
