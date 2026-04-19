import json
from pathlib import Path
from unittest.mock import patch

from scripts.discover.classify import ClassifyVerdict
from scripts.discover.extract import ExtractedFields
from scripts.discover.summarize import SummaryResult


def _candidate_dict(url, title, source_id="konbriefing"):
    return {
        "url": url, "title": title, "raw_date": "2024-03-01",
        "source_id": source_id, "source_type": "news", "lang": "en",
        "excerpt": "rail ransomware", "discovered_at": "2026-04-19",
    }


def test_orchestrator_writes_one_stub_per_kept_candidate(tmp_path):
    from scripts import stub_candidates

    candidates_path = tmp_path / "candidates.json"
    drafts_dir = tmp_path / "drafts"
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()
    candidates_path.write_text(json.dumps([
        _candidate_dict("https://a.example/1", "DB Schenker hit"),
        _candidate_dict("https://a.example/2", "train derailment"),
    ]))

    # classify: first kept, second dropped
    classify_out = iter([
        (ClassifyVerdict(True, 0.9, "ok", True), {"cost_usd": 0.001}),
        (ClassifyVerdict(False, 0.9, "physical", False), {"cost_usd": 0.001}),
    ])
    extract_out = (ExtractedFields("2024-03-01", "day", ("DE",), "DB Schenker", None),
                   {"cost_usd": 0.002})
    summary_out = (SummaryResult("Rail freight operator hit.", None), {"cost_usd": 0.002})

    with patch("scripts.stub_candidates.classify", side_effect=lambda c: next(classify_out)), \
         patch("scripts.stub_candidates.dedup", return_value=type("D", (), {
             "duplicate_of": None, "kept": True, "used_llm": False, "meta": None
         })()), \
         patch("scripts.stub_candidates.extract", return_value=extract_out), \
         patch("scripts.stub_candidates.summarize", return_value=summary_out):
        summary = stub_candidates.run(
            candidates_path=candidates_path,
            drafts_dir=drafts_dir,
            incidents_dir=incidents_dir,
            cost_log_path=tmp_path / ".cost.log",
        )

    stubs = list(drafts_dir.glob("*.yaml"))
    assert len(stubs) == 1
    assert summary["classified_kept"] == 1
    assert summary["dropped_classify"] == 1
    assert summary["stubs_written"] == 1
    assert summary["total_cost_usd"] > 0


def test_orchestrator_halts_on_max_cost(tmp_path):
    from scripts import stub_candidates

    candidates_path = tmp_path / "candidates.json"
    candidates_path.write_text(json.dumps([
        _candidate_dict("https://a.example/1", "DB Schenker hit"),
        _candidate_dict("https://a.example/2", "SNCF hit"),
    ]))
    drafts_dir = tmp_path / "drafts"
    incidents_dir = tmp_path / "incidents"
    incidents_dir.mkdir()

    with patch(
        "scripts.stub_candidates.classify",
        return_value=(ClassifyVerdict(True, 0.9, "ok", True), {"cost_usd": 10.0}),
    ), patch("scripts.stub_candidates.dedup", return_value=type("D", (), {
        "duplicate_of": None, "kept": True, "used_llm": False, "meta": None
    })()), patch("scripts.stub_candidates.extract", return_value=(
        ExtractedFields("2024-03-01", "day", ("DE",), "X", None), {"cost_usd": 0.0}
    )), patch("scripts.stub_candidates.summarize", return_value=(
        SummaryResult("x.", None), {"cost_usd": 0.0}
    )):
        summary = stub_candidates.run(
            candidates_path=candidates_path,
            drafts_dir=drafts_dir,
            incidents_dir=incidents_dir,
            cost_log_path=tmp_path / ".cost.log",
            max_cost_usd=1.0,
        )

    assert summary["halted_on_cost"] is True
    assert summary["stubs_written"] == 1
