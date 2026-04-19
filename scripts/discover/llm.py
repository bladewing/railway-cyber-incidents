"""Thin wrapper around the `claude` CLI for Haiku JSON calls.

Two things to know about the CLI envelope:

* ``--model haiku`` is **not** a valid CLI alias — only ``sonnet`` and
  ``opus`` are. Passing an invalid alias silently falls back to the
  session default (often Sonnet), so we pass the fully-qualified
  ``claude-haiku-4-5`` to actually get Haiku pricing/latency.
* Claude 4.x models routinely wrap JSON responses in a
  ```` ```json ... ``` ```` fence even when the prompt says not to.
  We strip fences before ``json.loads`` instead of relying on retries.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass

_HAIKU_MODEL = "claude-haiku-4-5"

# Matches ```json\n...\n``` or ```\n...\n``` wrappers, optionally with
# leading/trailing whitespace. DOTALL so `.` matches newlines.
_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(?P<body>.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


class LLMError(RuntimeError):
    """Raised when the LLM produces unusable output after retries."""


@dataclass
class CallMeta:
    cost_usd: float
    input_tokens: int
    output_tokens: int

    def as_dict(self) -> dict:
        return {
            "cost_usd": self.cost_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


def _strip_fences(raw: str) -> str:
    """Remove a surrounding markdown code fence, if present."""
    m = _FENCE_RE.match(raw)
    return m.group("body") if m else raw


def call_haiku_json(
    prompt: str,
    *,
    retries: int = 1,
    timeout_s: int = 60,
) -> tuple[dict | list, dict]:
    """Call `claude -p --model claude-haiku-4-5 --output-format json`.

    Strips markdown code fences from the model's ``result`` before
    parsing (Claude 4.x reliably wraps JSON in ``` ```json ... ``` ```
    fences regardless of prompt instructions). Adds a strict-JSON
    reminder on retry. Raises ``LLMError`` when no attempt yields
    parseable JSON after fence-stripping.
    """
    last_err: Exception | None = None
    attempt_prompt = prompt
    for attempt in range(retries + 1):
        proc = subprocess.run(
            [
                "claude",
                "-p",
                attempt_prompt,
                "--model",
                _HAIKU_MODEL,
                "--output-format",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=True,
        )
        outer = json.loads(proc.stdout)
        raw = outer.get("result", "")
        meta = CallMeta(
            cost_usd=float(outer.get("total_cost_usd", 0.0)),
            input_tokens=int(outer.get("usage", {}).get("input_tokens", 0)),
            output_tokens=int(outer.get("usage", {}).get("output_tokens", 0)),
        ).as_dict()
        payload = raw if isinstance(raw, str) else json.dumps(raw)
        try:
            parsed = json.loads(_strip_fences(payload))
            return parsed, meta
        except json.JSONDecodeError as e:
            last_err = e
            attempt_prompt = (
                prompt + "\n\nReturn ONLY valid JSON. No prose. No code fences."
            )
    raise LLMError(f"Haiku returned unparseable JSON after {retries + 1} attempts: {last_err}")
