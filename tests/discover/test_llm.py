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


def test_passes_fully_qualified_haiku_model_flag():
    # `--model haiku` is NOT a valid CLI alias (only `sonnet`/`opus`
    # are); passing it silently falls back to the default model. We
    # must pass the fully-qualified `claude-haiku-4-5` to actually run
    # on Haiku instead of paying Sonnet prices.
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
    assert captured["cmd"][idx + 1] == "claude-haiku-4-5"
    assert "--output-format" in captured["cmd"]
    assert "json" in captured["cmd"]


def test_strips_markdown_code_fences_around_json():
    # Claude 4.x routinely wraps JSON in ```json ... ``` fences;
    # the wrapper must strip them before parsing.
    fenced = '```json\n{"ok": true, "n": 2}\n```'
    with patch("subprocess.run", side_effect=_fake_run(fenced)):
        result, _meta = call_haiku_json("p")
    assert result == {"ok": True, "n": 2}


def test_strips_plain_triple_backtick_fences():
    # Models sometimes omit the language tag on the opening fence.
    fenced = "```\n{\"a\": 1}\n```"
    with patch("subprocess.run", side_effect=_fake_run(fenced)):
        result, _meta = call_haiku_json("p")
    assert result == {"a": 1}


def test_plain_json_without_fences_still_parses():
    with patch("subprocess.run", side_effect=_fake_run('{"a": 1}')):
        result, _meta = call_haiku_json("p")
    assert result == {"a": 1}
