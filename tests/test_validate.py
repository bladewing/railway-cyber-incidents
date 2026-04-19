import yaml
from pathlib import Path
import pytest

from scripts.validate import (
    load_schema, validate_incident, validate_repository, ValidationError,
)


def _write(path: Path, doc: dict) -> None:
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def test_minimal_valid_incident_passes(tmp_repo, minimal_incident):
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert errors == []


def test_missing_required_field_fails(tmp_repo, minimal_incident):
    del minimal_incident["sources"]
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert any("sources" in e for e in errors)


def test_id_must_match_filename(tmp_repo, minimal_incident):
    _write(tmp_repo / "incidents" / "2020-01-01_other.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert any("id" in e and "filename" in e.lower() for e in errors)


def test_duplicate_ids_fail(tmp_repo, minimal_incident):
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    other = dict(minimal_incident)
    _write(tmp_repo / "incidents" / "2020-01-01_example-copy.yaml", {**other, "id": "2020-01-01_example"})
    # duplicate filename stem would be caught by OS; duplicate id across files:
    errors = validate_repository(tmp_repo)
    assert any("duplicate" in e.lower() for e in errors)


def test_event_date_after_reported_date_fails(tmp_repo, minimal_incident):
    minimal_incident["reported_date"] = "2019-12-01"  # before event_date
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert any("event_date" in e and "reported_date" in e for e in errors)


def test_invalid_vocab_value_fails(tmp_repo, minimal_incident):
    minimal_incident["affected_systems"] = ["not_a_real_system"]
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert any("affected_systems" in e or "not_a_real_system" in e for e in errors)


def test_empty_sources_list_fails(tmp_repo, minimal_incident):
    minimal_incident["sources"] = []
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert any("sources" in e for e in errors)


def test_malformed_url_fails(tmp_repo, minimal_incident):
    minimal_incident["sources"][0]["url"] = "not-a-url"
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    errors = validate_repository(tmp_repo)
    assert any("url" in e.lower() for e in errors)


def test_validator_ignores_drafts_directory(tmp_repo, minimal_incident):
    """Files under incidents/.drafts/ must never be validated."""
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    drafts_dir = tmp_repo / "incidents" / ".drafts"
    drafts_dir.mkdir()
    # A deliberately broken draft — missing required fields.
    _write(drafts_dir / "2099-12-31_broken.yaml", {"id": "nope"})
    errors = validate_repository(tmp_repo)
    assert errors == [], f"drafts dir must be skipped, got: {errors}"


def test_validator_ignores_hidden_subdirs_generally(tmp_repo, minimal_incident):
    """Regression: glob('*.yaml') on incidents/ must remain non-recursive."""
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    nested = tmp_repo / "incidents" / "subdir"
    nested.mkdir()
    _write(nested / "2099-12-31_broken.yaml", {"id": "nope"})
    errors = validate_repository(tmp_repo)
    assert errors == []
