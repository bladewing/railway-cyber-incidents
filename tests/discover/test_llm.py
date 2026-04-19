import json
import subprocess
from unittest.mock import patch

import pytest

from scripts.discover.llm import LLMError, call_haiku_json


def _fake_run(outer_result, cost=0.001):
    payload = {
        "result": outer_result if isinstance(outer_result, str) else json.dumps(outer_result),
        "total_cost_usd": cost,
        "usage": {"input_tokens": 100, "output_tokens": 10},
    }

    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=json.dumps(payload), stderr=""
        )

    return _run


def test_happy_path_returns_parsed_inner_json_plus_cost():
    with patch("subprocess.run", side_effect=_fake_run({"is_rail_cyber": True, "confidence": 0.9})):
        result, meta = call_haiku_json("prompt")
    assert result == {"is_rail_cyber": True, "confidence": 0.9}
    assert meta["cost_usd"] == 0.001
    assert meta["input_tokens"] == 100


def test_retries_once_on_invalid_inner_json():
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            outer = {"result": "not json", "total_cost_usd": 0.001,
                     "usage": {"input_tokens": 10, "output_tokens": 2}}
        else:
            outer = {"result": json.dumps({"ok": True}), "total_cost_usd": 0.002,
                     "usage": {"input_tokens": 20, "output_tokens": 5}}
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    with patch("subprocess.run", side_effect=_run):
        result, meta = call_haiku_json("p", retries=1)
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_raises_after_exhausting_retries():
    def _run(cmd, **kwargs):
        outer = {"result": "never json", "total_cost_usd": 0.0,
                 "usage": {"input_tokens": 0, "output_tokens": 0}}
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    with patch("subprocess.run", side_effect=_run):
        with pytest.raises(LLMError):
            call_haiku_json("p", retries=1)


def test_passes_model_flag():
    captured = {}

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        outer = {"result": "{}", "total_cost_usd": 0.0,
                 "usage": {"input_tokens": 0, "output_tokens": 0}}
        return subprocess.CompletedProcess(args=cmd, returncode=0,
                                           stdout=json.dumps(outer), stderr="")

    with patch("subprocess.run", side_effect=_run):
        call_haiku_json("p")
    assert "--model" in captured["cmd"]
    idx = captured["cmd"].index("--model")
    assert captured["cmd"][idx + 1] == "haiku"
    assert "--output-format" in captured["cmd"]
    assert "json" in captured["cmd"]
