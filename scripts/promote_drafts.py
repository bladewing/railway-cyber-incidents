"""Move approved drafts from incidents/.drafts/ to incidents/."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from typing import Iterable

import yaml


class PromotionError(Exception):
    pass


def _drafts_dir(repo_root: Path) -> Path:
    return repo_root / "incidents" / ".drafts"


def _incidents_dir(repo_root: Path) -> Path:
    return repo_root / "incidents"


def _available_drafts(repo_root: Path) -> list[str]:
    return sorted(p.stem for p in _drafts_dir(repo_root).glob("*.yaml"))


_VOCAB_FIELDS = {
    "industry_sector": "industry_sectors",
    "operator_type": "operator_types",
    "attack_vector": "attack_vectors",
    "motive": "motives",
    "confirmation_status": "confidence_levels",
    "attribution_confidence": "confidence_levels",
    "event_date_precision": "event_date_precision",
    "affected_systems": "affected_systems",
}


def _load_vocab(repo_root: Path, vocab_name: str) -> set[str]:
    path = repo_root / "vocabularies" / f"{vocab_name}.yaml"
    data = yaml.safe_load(path.read_text()) or []
    if isinstance(data, dict):
        data = data.get("values", [])
    ids: set[str] = set()
    for entry in data:
        if isinstance(entry, str):
            ids.add(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("id"), str):
            ids.add(entry["id"])
    return ids


def _vocab_violations(repo_root: Path, draft: dict) -> list[str]:
    violations: list[str] = []
    for field, vocab_name in _VOCAB_FIELDS.items():
        value = draft.get(field)
        if value is None:
            continue
        vocab = _load_vocab(repo_root, vocab_name)
        values = value if isinstance(value, list) else [value]
        for v in values:
            if v not in vocab:
                violations.append(f"{field}={v!r} not in vocabularies/{vocab_name}.yaml")
    # impact.scope is nested
    impact = draft.get("impact") or {}
    scope = impact.get("scope") if isinstance(impact, dict) else None
    if scope is not None:
        vocab = _load_vocab(repo_root, "impact_scopes")
        if scope not in vocab:
            violations.append(f"impact.scope={scope!r} not in vocabularies/impact_scopes.yaml")
    # sources[].type is vocab-controlled (vocabularies/source_types.yaml)
    sources = draft.get("sources") or []
    if isinstance(sources, list):
        vocab = _load_vocab(repo_root, "source_types")
        for src in sources:
            stype = src.get("type") if isinstance(src, dict) else None
            if stype is not None and stype not in vocab:
                violations.append(
                    f"sources[].type={stype!r} not in vocabularies/source_types.yaml"
                )
    return violations


def promote(
    repo_root: Path,
    *,
    only: Iterable[str] | None = None,
    exclude: Iterable[str] | None = None,
) -> list[str]:
    exclude_set = set(exclude or [])
    if only is not None:
        candidates = list(only)
    else:
        candidates = _available_drafts(repo_root)
    candidates = [c for c in candidates if c not in exclude_set]

    # Two-pass: validate all candidates first, then move. Keeps batches atomic
    # on vocab failure — a bad apple doesn't leave earlier candidates promoted.
    plan: list[tuple[str, Path, Path]] = []
    for incident_id in candidates:
        src = _drafts_dir(repo_root) / f"{incident_id}.yaml"
        if not src.exists():
            raise PromotionError(f"no draft for {incident_id}")
        draft = yaml.safe_load(src.read_text())
        violations = _vocab_violations(repo_root, draft)
        if violations:
            raise PromotionError(
                f"{incident_id}: cannot promote, vocab not merged: {'; '.join(violations)}"
            )
        dst = _incidents_dir(repo_root) / f"{incident_id}.yaml"
        plan.append((incident_id, src, dst))

    promoted: list[str] = []
    for incident_id, src, dst in plan:
        shutil.move(str(src), str(dst))
        promoted.append(incident_id)
    return promoted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", action="append", default=[], help="promote only this id (repeatable)")
    parser.add_argument("--exclude", action="append", default=[], help="skip this id (repeatable)")
    parser.add_argument("--all", action="store_true", help="promote all remaining drafts")
    args = parser.parse_args(argv)

    if not args.only and not args.all:
        parser.error("pass --only <id> (repeatable) or --all")
    repo_root = Path(__file__).resolve().parent.parent
    only = args.only or None
    try:
        promoted = promote(repo_root, only=only, exclude=args.exclude)
    except PromotionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for pid in promoted:
        print(f"promoted {pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
