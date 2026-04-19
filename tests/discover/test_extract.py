from unittest.mock import patch

from scripts.discover.candidate import Candidate
from scripts.discover.extract import ExtractedFields, extract


def _c():
    return Candidate(
        url="https://example.org/x",
        title="DB Schenker hit",
        raw_date="2024-03-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="rail freight ransomware",
        discovered_at="2026-04-19",
    )


def test_extract_uses_article_body_when_available():
    def _fake_fetch(url, timeout_s=10):
        return "Long article body about DB Schenker in Germany on 2024-03-01."

    with patch(
        "scripts.discover.extract.call_haiku_json",
        return_value=(
            {
                "event_date": "2024-03-01",
                "event_date_precision": "day",
                "countries_impacted": ["DE"],
                "target_organization": "DB Schenker",
                "reported_date": None,
            },
            {"cost_usd": 0.002},
        ),
    ):
        with patch("scripts.discover.extract._fetch_article_text", side_effect=_fake_fetch):
            fields, meta = extract(_c())
    assert fields == ExtractedFields(
        event_date="2024-03-01",
        event_date_precision="day",
        countries_impacted=("DE",),
        target_organization="DB Schenker",
        reported_date=None,
    )


def test_extract_fails_open_on_fetch_error():
    def _raise(url, timeout_s=10):
        raise RuntimeError("network")

    with patch(
        "scripts.discover.extract.call_haiku_json",
        return_value=(
            {
                "event_date": "2024-03-01",
                "event_date_precision": "day",
                "countries_impacted": [],
                "target_organization": None,
                "reported_date": None,
            },
            {"cost_usd": 0.001},
        ),
    ):
        with patch("scripts.discover.extract._fetch_article_text", side_effect=_raise):
            fields, _ = extract(_c())
    assert fields.event_date == "2024-03-01"  # Haiku was still called with excerpt-only
    assert fields.countries_impacted == ()
