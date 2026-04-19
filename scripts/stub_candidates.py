"""Stage 2 — run Passes 1-4 over candidates.json, write stubs to incidents/drafts/."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from scripts.discover.candidate import Candidate
from scripts.discover.classify import classify
from scripts.discover.dedup import dedup
from scripts.discover.extract import extract
from scripts.discover.stub_writer import write_stub
from scripts.discover.summarize import summarize

LOG = logging.getLogger("discover.stub")


def _load_candidates(path: Path) -> list[Candidate]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Candidate.from_dict(d) for d in data]


def run(
    *,
    candidates_path: Path,
    drafts_dir: Path,
    incidents_dir: Path,
    cost_log_path: Path,
    max_cost_usd: float | None = None,
    today: str | None = None,
) -> dict:
    today = today or date.today().isoformat()
    candidates = _load_candidates(candidates_path)

    total_cost = 0.0
    classified_kept = dropped_classify = dropped_dedup = stubs = errored = 0
    halted = False
    almost: list[dict] = []
    errors: list[dict] = []

    for c in candidates:
        # Per-candidate isolation: a transient LLM failure or one bad
        # response (empty result, refusal, quota blip) must not kill the
        # whole batch. Log the URL, count it, and move on — the fetch
        # stage uses the same pattern for adapter isolation.
        try:
            verdict, meta = classify(c)
            total_cost += float(meta.get("cost_usd", 0.0))
            if not verdict.kept:
                dropped_classify += 1
                if 0.5 <= verdict.confidence < 0.6:
                    almost.append({
                        "url": c.url, "confidence": verdict.confidence, "title": c.title,
                    })
                if max_cost_usd is not None and total_cost >= max_cost_usd:
                    halted = True
                    break
                continue
            classified_kept += 1

            dedup_res = dedup(c, incidents_dir=incidents_dir)
            if dedup_res.used_llm and dedup_res.meta:
                total_cost += float(dedup_res.meta.get("cost_usd", 0.0))
            if not dedup_res.kept:
                dropped_dedup += 1
                if max_cost_usd is not None and total_cost >= max_cost_usd:
                    halted = True
                    break
                continue

            fields, meta = extract(c)
            total_cost += float(meta.get("cost_usd", 0.0))
            summary_res, meta = summarize(c)
            total_cost += float(meta.get("cost_usd", 0.0))

            write_stub(c, verdict, fields, summary_res, drafts_dir=drafts_dir, today=today)
            stubs += 1
        except Exception as e:
            errored += 1
            errors.append({"url": c.url, "error": f"{type(e).__name__}: {e}"})
            LOG.warning("%s: candidate failed, skipping: %s", c.url, e)

        if max_cost_usd is not None and total_cost >= max_cost_usd:
            halted = True
            break

    cost_log_path.parent.mkdir(parents=True, exist_ok=True)
    with cost_log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{today}\t{total_cost:.4f}\t{stubs} stubs\n")

    summary = {
        "fetched": len(candidates),
        "classified_kept": classified_kept,
        "dropped_classify": dropped_classify,
        "dropped_dedup": dropped_dedup,
        "stubs_written": stubs,
        "errored": errored,
        "errors": errors[:10],
        "total_cost_usd": round(total_cost, 4),
        "halted_on_cost": halted,
        "almost_passed": almost[:5],
    }
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default="dist/candidates.json")
    ap.add_argument("--drafts-dir", default="incidents/drafts")
    ap.add_argument("--incidents-dir", default="incidents")
    ap.add_argument("--cost-log", default="dist/.discover-cost.log")
    ap.add_argument("--max-cost", type=float, default=None)
    args = ap.parse_args()

    s = run(
        candidates_path=Path(args.candidates),
        drafts_dir=Path(args.drafts_dir),
        incidents_dir=Path(args.incidents_dir),
        cost_log_path=Path(args.cost_log),
        max_cost_usd=args.max_cost,
    )
    print(
        f"fetched: {s['fetched']} | kept: {s['classified_kept']} | "
        f"dropped: classify {s['dropped_classify']}, dedup {s['dropped_dedup']} | "
        f"stubs: {s['stubs_written']} | errored: {s['errored']} | "
        f"cost: ${s['total_cost_usd']:.4f}"
        + (" | HALTED ON COST" if s["halted_on_cost"] else "")
    )
    if s["almost_passed"]:
        print("almost-passed (review):")
        for a in s["almost_passed"]:
            print(f"  {a['confidence']:.2f}  {a['title']}  ({a['url']})")
    if s["errors"]:
        print("errored (logged, not a hard failure):")
        for e in s["errors"]:
            print(f"  {e['error']}  ({e['url']})")


if __name__ == "__main__":
    main()
