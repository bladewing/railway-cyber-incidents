from pathlib import Path

import yaml

from scripts.discover.candidate import Candidate
from scripts.discover.classify import ClassifyVerdict
from scripts.discover.extract import ExtractedFields
from scripts.discover.stub_writer import write_stub
from scripts.discover.summarize import SummaryResult


def _c():
    return Candidate(
        url="https://konbriefing.com/x",
        title="DB Schenker ransomware",
        raw_date="2024-03-01",
        source_id="konbriefing",
        source_type="news",
        lang="en",
        excerpt="rail freight",
        discovered_at="2026-04-19",
    )


def _en_inputs():
    return (
        ClassifyVerdict(True, 0.82, "rail+ransomware", True),
        ExtractedFields("2024-03-01", "day", ("DE",), "DB Schenker", None),
        SummaryResult("Rail freight operator hit by ransomware.", None),
    )


def test_stub_filename_matches_id_field(tmp_path):
    verdict, fields, summary = _en_inputs()
    path = write_stub(_c(), verdict, fields, summary, drafts_dir=tmp_path)
    assert path.parent == tmp_path
    assert path.suffix == ".yaml"
    doc = yaml.safe_load(path.read_text())
    assert doc["id"] == path.stem
    assert doc["id"].startswith("2024-03-01_")


def test_stub_marks_needs_review_and_null_enums(tmp_path):
    verdict, fields, summary = _en_inputs()
    path = write_stub(_c(), verdict, fields, summary, drafts_dir=tmp_path)
    doc = yaml.safe_load(path.read_text())
    assert doc["provenance"]["needs_review"] is True
    assert doc["provenance"]["discovered_by"] == "discover_incidents"
    assert doc["provenance"]["aggregator"] == "konbriefing"
    assert doc["provenance"]["haiku_classify_confidence"] == 0.82
    for key in ("industry_sector", "operator_type", "attack_vector",
                "motive", "affected_systems", "malware", "threat_actor"):
        assert doc.get(key) is None
    assert doc["impact"]["scope"] is None


def test_stub_includes_source_with_absolute_url(tmp_path):
    verdict, fields, summary = _en_inputs()
    path = write_stub(_c(), verdict, fields, summary, drafts_dir=tmp_path)
    doc = yaml.safe_load(path.read_text())
    assert doc["sources"][0]["url"].startswith("https://")
    assert doc["sources"][0]["type"] == "news"
    assert doc["sources"][0]["language"] == "en"


def test_stub_has_all_required_top_level_keys(tmp_path):
    """Stub must carry every field validate.py requires, so promotion won't fail."""
    import subprocess
    import shutil

    # Copy fixture incidents + place stub alongside under a temp incidents/ root.
    incidents = tmp_path / "incidents"
    drafts = incidents / "drafts"
    incidents.mkdir()
    drafts.mkdir()
    # Minimal synthetic incident so validate has something to parse.
    (incidents / "2024-03-01_example.yaml").write_text(
        "id: 2024-03-01_example\nschema_version: \"1.0\"\nevent_date: 2024-03-01\n"
        "event_date_precision: day\ncountries_impacted: [DE]\nconfirmation_status: reported\n"
        "description_en: Test.\nsources:\n  - url: https://example.org/\n    type: news\n"
        "last_updated: 2024-03-01\n",
        encoding="utf-8",
    )
    verdict, fields, summary = _en_inputs()
    write_stub(_c(), verdict, fields, summary, drafts_dir=drafts)

    # We do NOT run scripts/validate.py here — that belongs to the later
    # drafts-exclusion regression test. Instead, assert the stub parses
    # as YAML and has required keys.
    path = next(drafts.glob("*.yaml"))
    doc = yaml.safe_load(path.read_text())
    for required in ("id", "schema_version", "event_date", "event_date_precision",
                     "countries_impacted", "confirmation_status", "description_en",
                     "sources", "last_updated"):
        assert required in doc and doc[required] is not None
