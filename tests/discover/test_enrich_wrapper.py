import json
import subprocess
from pathlib import Path
from unittest.mock import patch


def test_enrich_wraps_subagent_prompt_with_given_id(tmp_path, monkeypatch):
    from scripts import enrich

    captured = {}

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        outer = {
            "result": json.dumps({"incident_id": "2024-03-01_db-schenker", "status": "drafted"}),
            "total_cost_usd": 0.05,
            "usage": {"input_tokens": 500, "output_tokens": 200},
        }
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)
    result = enrich.run(incident_id="2024-03-01_db-schenker")

    assert "2024-03-01_db-schenker" in captured["cmd"][2]  # prompt body
    assert result["incident_id"] == "2024-03-01_db-schenker"
    assert result["status"] == "drafted"
    # Enrichment runs sonnet-class model (subagent-driven depth), not haiku.
    assert "--model" in captured["cmd"]
    idx = captured["cmd"].index("--model")
    assert captured["cmd"][idx + 1] == "sonnet"
