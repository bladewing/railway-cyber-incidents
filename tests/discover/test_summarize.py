from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.summarize import summarize


def _c(lang="en", excerpt="Some excerpt"):
    return Candidate(
        url="https://example.org/x",
        title="t",
        raw_date=None,
        source_id="konbriefing",
        source_type="news",
        lang=lang,
        excerpt=excerpt,
        discovered_at="2026-04-19",
    )


def test_summarize_returns_en_for_english_source():
    with patch(
        "scripts.discover.summarize.call_haiku_json",
        return_value=({"description_en": "One sentence.", "description_de": None}, {"cost_usd": 0.002}),
    ):
        result, _ = summarize(_c(lang="en"))
    assert result.description_en == "One sentence."
    assert result.description_de is None


def test_summarize_returns_both_for_german_source():
    with patch(
        "scripts.discover.summarize.call_haiku_json",
        return_value=(
            {"description_en": "English translation.", "description_de": "Deutscher Originaltext."},
            {"cost_usd": 0.003},
        ),
    ):
        result, _ = summarize(_c(lang="de", excerpt="Deutsch..."))
    assert result.description_en == "English translation."
    assert result.description_de == "Deutscher Originaltext."
