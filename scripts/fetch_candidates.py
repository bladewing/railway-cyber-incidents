"""Stage 1 — deterministic fetch of all enabled aggregators to candidates.json."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from scripts.discover.adapters import bsi, enisa, eurepoc, konbriefing, ransomware_live
from scripts.discover.aggregators_config import AggregatorConfig, load_aggregators

LOG = logging.getLogger("discover.fetch")

# Store module references so that monkeypatching the module attribute
# (e.g. in tests) is visible at call time — capturing .fetch directly
# at import would freeze the original reference.
_ADAPTER_MODULES = {
    "konbriefing": konbriefing,
    "eurepoc": eurepoc,
    "ransomware_live": ransomware_live,
    "enisa_transport": enisa,
    "bsi_lagebericht": bsi,
}


def _inputs_for(agg: AggregatorConfig) -> list[str]:
    if agg.kind == "pdf":
        return list(agg.pdfs)
    return [agg.url] if agg.url else []


def run(*, output_path: Path, discovered_at: str | None = None) -> dict:
    discovered_at = discovered_at or date.today().isoformat()
    all_candidates: list[dict] = []
    errors: list[dict] = []
    for agg in load_aggregators():
        if not agg.enabled:
            continue
        mod = _ADAPTER_MODULES.get(agg.id)
        if mod is None:
            errors.append({"aggregator": agg.id, "error": "no adapter registered"})
            continue
        for src in _inputs_for(agg):
            try:
                cands = mod.fetch(src, discovered_at=discovered_at)
                all_candidates.extend(c.to_dict() for c in cands)
                LOG.info("%s: %d candidates from %s", agg.id, len(cands), src)
            except Exception as e:  # adapter isolation — one bad source doesn't kill the run
                errors.append({"aggregator": agg.id, "error": str(e)})
                LOG.warning("%s fetch failed: %s", agg.id, e)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(all_candidates, indent=2, ensure_ascii=False))
    return {"fetched": len(all_candidates), "errors": errors}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="dist/candidates.json")
    args = ap.parse_args()
    summary = run(output_path=Path(args.output))
    print(
        f"fetched: {summary['fetched']} candidates; "
        f"errors: {len(summary['errors'])}"
    )
    for e in summary["errors"]:
        print(f"  [{e['aggregator']}] {e['error']}")


if __name__ == "__main__":
    main()
