import json
from pathlib import Path
from unittest.mock import patch

from scripts.discover.candidate import Candidate


def _make_candidates(source_id, n):
    return [
        Candidate(
            url=f"https://example.org/{source_id}/{i}",
            title=f"{source_id} hit {i}",
            raw_date="2024-01-01",
            source_id=source_id,
            source_type="news",
            lang="en",
            excerpt="",
            discovered_at="2026-04-19",
        )
        for i in range(n)
    ]


def test_orchestrator_calls_each_enabled_adapter_and_writes_json(tmp_path, monkeypatch):
    from scripts import fetch_candidates

    def _fake_konb(url, *, discovered_at, timeout_s=15):
        return _make_candidates("konbriefing", 2)

    def _fake_eurepoc(url, *, discovered_at, timeout_s=20):
        return _make_candidates("eurepoc", 1)

    def _fake_rl(url, *, discovered_at, timeout_s=20):
        raise RuntimeError("ransomware.live unreachable")

    monkeypatch.setattr("scripts.discover.adapters.konbriefing.fetch", _fake_konb)
    monkeypatch.setattr("scripts.discover.adapters.eurepoc.fetch", _fake_eurepoc)
    monkeypatch.setattr("scripts.discover.adapters.ransomware_live.fetch", _fake_rl)
    monkeypatch.setattr("scripts.discover.adapters.enisa.fetch",
                        lambda url, *, discovered_at, timeout_s=30: [])
    monkeypatch.setattr("scripts.discover.adapters.bsi.fetch",
                        lambda url, *, discovered_at, timeout_s=30: [])

    out_path = tmp_path / "candidates.json"
    summary = fetch_candidates.run(output_path=out_path, discovered_at="2026-04-19")

    data = json.loads(out_path.read_text())
    assert len(data) == 3
    ids = sorted({c["source_id"] for c in data})
    assert ids == ["eurepoc", "konbriefing"]
    # Failed adapter is reported, not raised:
    assert summary["errors"] == [{"aggregator": "ransomware_live", "error": "ransomware.live unreachable"}]
    assert summary["fetched"] == 3
