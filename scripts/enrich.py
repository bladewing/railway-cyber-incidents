"""Thin wrapper around the existing enrichment subagent flow for one incident id.

The enrichment prompt lives at docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md
and uses the sonnet-class model because it performs 20+ web searches
across 5 rounds — this is deliberately not Haiku.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "superpowers"
    / "plans"
    / "2026-04-19-enrichment-subagent-prompt.md"
)


def _build_prompt(incident_id: str) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return template.replace("{{INCIDENT_ID}}", incident_id)


def run(*, incident_id: str, timeout_s: int = 1800) -> dict:
    prompt = _build_prompt(incident_id)
    proc = subprocess.run(
        ["claude", "-p", prompt, "--model", "sonnet", "--output-format", "json"],
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=True,
    )
    outer = json.loads(proc.stdout)
    raw = outer.get("result", "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"incident_id": incident_id, "status": "unparseable", "raw": raw}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("incident_id")
    args = ap.parse_args()
    result = run(incident_id=args.incident_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
