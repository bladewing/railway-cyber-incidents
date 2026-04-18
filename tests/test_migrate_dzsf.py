from pathlib import Path
import yaml

from scripts.migrate_dzsf import migrate

FIXTURE = Path(__file__).parent / "fixtures" / "mini_dzsf.xlsx"


def test_migrates_all_rows(tmp_repo):
    incidents_dir = tmp_repo / "incidents"
    count = migrate(FIXTURE, incidents_dir)
    assert count == 3
    assert len(list(incidents_dir.glob("*.yaml"))) == 3


def test_known_fields_round_trip(tmp_repo):
    migrate(FIXTURE, tmp_repo / "incidents")
    docs = [yaml.safe_load(p.read_text()) for p in sorted(tmp_repo.glob("incidents/*.yaml"))]
    by_date = {d["event_date"]: d for d in docs}
    wannacry = by_date["2017-05-13"]
    assert wannacry["countries_impacted"] == ["DE", "RU"]
    assert wannacry["confirmation_status"] == "confirmed"
    assert wannacry["extortion"] is True
    assert wannacry["supply_chain"] is False
    assert wannacry["attack_vector"] == "exploit"
    assert wannacry["threat_actor"] == "Lazarous Group"
    assert wannacry["attribution_confidence"] == "suspected"
    assert any(m["name"].lower() == "wannacry" for m in wannacry["malware"])
    assert "payment_system" in wannacry["affected_systems"]
    assert "station_it" in wannacry["affected_systems"]
    assert "rail_operations" in wannacry["affected_systems"]


def test_asterisk_date_gets_month_precision(tmp_repo):
    migrate(FIXTURE, tmp_repo / "incidents")
    docs = [yaml.safe_load(p.read_text()) for p in sorted(tmp_repo.glob("incidents/*.yaml"))]
    by_date = {d["event_date"]: d for d in docs}
    # 01.07.2015* → 2015-07-01 with month precision
    assert "2015-07-01" in by_date
    assert by_date["2015-07-01"]["event_date_precision"] == "month"


def test_provenance_block_emitted_with_needs_review(tmp_repo):
    migrate(FIXTURE, tmp_repo / "incidents")
    any_doc = yaml.safe_load(next(tmp_repo.glob("incidents/*.yaml")).read_text())
    assert any_doc["provenance"]["origin"] == "DZSF-2020-23-S-1202"
    assert any_doc["provenance"]["needs_review"] is True


def test_output_passes_schema_validation(tmp_repo):
    from scripts.validate import validate_repository
    migrate(FIXTURE, tmp_repo / "incidents")
    errors = validate_repository(tmp_repo)
    assert errors == [], "\n".join(errors)
