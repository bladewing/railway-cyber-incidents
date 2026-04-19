from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.classify import classify


def _c(title="Rail hit", excerpt="Ransomware at rail operator"):
    return Candidate(
        url="https://example.org/x",
        title=title,
        raw_date="2024-01-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt=excerpt,
        discovered_at="2026-04-19",
    )


def test_classify_keeps_rail_cyber_above_threshold():
    with patch(
        "scripts.discover.classify.call_haiku_json",
        return_value=({"is_rail_cyber": True, "confidence": 0.9, "reason": "rail+ransomware"}, {"cost_usd": 0.001}),
    ):
        verdict, meta = classify(_c())
    assert verdict.is_rail_cyber is True
    assert verdict.kept is True
    assert meta["cost_usd"] == 0.001


def test_classify_drops_below_confidence_floor():
    with patch(
        "scripts.discover.classify.call_haiku_json",
        return_value=({"is_rail_cyber": True, "confidence": 0.4, "reason": "weak"}, {"cost_usd": 0.001}),
    ):
        verdict, _ = classify(_c())
    assert verdict.kept is False


def test_classify_drops_not_rail_cyber():
    with patch(
        "scripts.discover.classify.call_haiku_json",
        return_value=({"is_rail_cyber": False, "confidence": 0.9, "reason": "physical sabotage"}, {"cost_usd": 0.001}),
    ):
        verdict, _ = classify(_c(title="Train derailment"))
    assert verdict.kept is False


def test_classify_prompt_includes_title_and_excerpt():
    captured = {}

    def _fake(prompt, **kwargs):
        captured["prompt"] = prompt
        return ({"is_rail_cyber": True, "confidence": 0.9, "reason": "ok"}, {"cost_usd": 0.001})

    with patch("scripts.discover.classify.call_haiku_json", side_effect=_fake):
        classify(_c(title="DB Schenker hit", excerpt="Ransomware attack..."))
    assert "DB Schenker hit" in captured["prompt"]
    assert "Ransomware attack" in captured["prompt"]
