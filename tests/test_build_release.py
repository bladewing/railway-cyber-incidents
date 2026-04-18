import csv
import json
import shutil
from pathlib import Path
import pytest
import yaml

from scripts.build_release import build_release


@pytest.fixture
def repo_with_two_incidents(tmp_repo, minimal_incident):
    a = dict(minimal_incident)
    a["id"] = "2020-01-01_alpha"
    a["affected_systems"] = ["payment_system", "website"]
    a["malware"] = [{"name": "FooCrypt", "family": "ransomware"}]

    b = dict(minimal_incident)
    b["id"] = "2021-06-15_beta"
    b["event_date"] = "2021-06-15"
    b["countries_impacted"] = ["FR", "IT"]
    b["affected_systems"] = ["rail_operations"]
    b["sources"] = [
        {"url": "https://a.example/1", "type": "news"},
        {"url": "https://a.example/2", "type": "cert_advisory"},
    ]

    (tmp_repo / "incidents" / "2020-01-01_alpha.yaml").write_text(
        yaml.safe_dump(a, sort_keys=False)
    )
    (tmp_repo / "incidents" / "2021-06-15_beta.yaml").write_text(
        yaml.safe_dump(b, sort_keys=False)
    )
    return tmp_repo


def test_build_writes_expected_files(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    for name in [
        "incidents.csv", "incidents.jsonl", "affected_systems.csv",
        "sources.csv", "malware.csv", "mitre_techniques.csv",
        "datapackage.json",
    ]:
        assert (dist / name).exists(), f"missing {name}"


def test_incidents_csv_has_one_row_per_incident(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    with (dist / "incidents.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert {r["id"] for r in rows} == {"2020-01-01_alpha", "2021-06-15_beta"}


def test_countries_serialized_as_semicolon(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    with (dist / "incidents.csv").open() as f:
        rows = {r["id"]: r for r in csv.DictReader(f)}
    assert rows["2021-06-15_beta"]["countries_impacted"] == "FR;IT"


def test_affected_systems_long_format(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    with (dist / "affected_systems.csv").open() as f:
        rows = list(csv.DictReader(f))
    pairs = {(r["incident_id"], r["system"]) for r in rows}
    assert ("2020-01-01_alpha", "payment_system") in pairs
    assert ("2020-01-01_alpha", "website") in pairs
    assert ("2021-06-15_beta", "rail_operations") in pairs
    assert len(rows) == 3


def test_sources_long_format(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    with (dist / "sources.csv").open() as f:
        rows = list(csv.DictReader(f))
    # 1 source in alpha + 2 sources in beta = 3
    assert len(rows) == 3


def test_jsonl_has_one_object_per_line(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    lines = (dist / "incidents.jsonl").read_text().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)  # must parse


def test_datapackage_declares_primary_and_foreign_keys(repo_with_two_incidents):
    dist = build_release(repo_with_two_incidents)
    dp = json.loads((dist / "datapackage.json").read_text())
    by_name = {r["name"]: r for r in dp["resources"]}
    assert by_name["incidents"]["schema"]["primaryKey"] == "id"
    fks = by_name["affected_systems"]["schema"]["foreignKeys"]
    assert any(
        fk["fields"] == "incident_id"
        and fk["reference"]["resource"] == "incidents"
        and fk["reference"]["fields"] == "id"
        for fk in fks
    )
