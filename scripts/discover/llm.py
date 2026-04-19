"""Thin wrapper around the `claude` CLI for Haiku JSON calls."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass


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


def call_haiku_json(
    prompt: str,
    *,
    retries: int = 1,
    timeout_s: int = 60,
) -> tuple[dict | list, dict]:
    """Call `claude -p --model haiku --output-format json` and return (parsed_inner, meta).

    Adds a strict-JSON reminder on retry. Raises LLMError when no retry
    produces valid JSON.
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
                "haiku",
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
        try:
            parsed = json.loads(raw if isinstance(raw, str) else json.dumps(raw))
            return parsed, meta
        except json.JSONDecodeError as e:
            last_err = e
            attempt_prompt = (
                prompt + "\n\nReturn ONLY valid JSON. No prose. No code fences."
            )
    raise LLMError(f"Haiku returned unparseable JSON after {retries + 1} attempts: {last_err}")
