"""Validate incidents/*.yaml against schema and cross-file invariants."""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


class ValidationError(Exception):
    pass


# A pragmatic URL check: absolute http(s) URL with a host component.
_URL_RE = re.compile(r"^https?://[^\s/?#]+(?:[/?#][^\s]*)?$", re.IGNORECASE)


def load_schema(repo_root: Path) -> dict[str, Any]:
    return json.loads((repo_root / "schema" / "incident.schema.json").read_text())


def _normalize_dates(value: Any) -> Any:
    """Recursively convert date/datetime to ISO-8601 strings for JSON Schema."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize_dates(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_dates(v) for v in value]
    return value


def _check_source_urls(doc: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for i, src in enumerate(doc.get("sources") or []):
        if not isinstance(src, dict):
            continue
        url = src.get("url")
        if isinstance(url, str) and not _URL_RE.match(url):
            errors.append(f"sources.{i}.url: '{url}' is not a valid absolute URL")
    return errors


def validate_incident(doc: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    normalised = _normalize_dates(doc)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []
    for err in validator.iter_errors(normalised):
        path = ".".join(str(p) for p in err.absolute_path) or "<root>"
        errors.append(f"{path}: {err.message}")
    errors.extend(_check_source_urls(normalised))
    # Cross-field check: event_date <= reported_date
    ed, rd = normalised.get("event_date"), normalised.get("reported_date")
    if ed and rd and ed > rd:
        errors.append(
            f"event_date ({ed}) must be <= reported_date ({rd})"
        )
    return errors


def validate_repository(repo_root: Path) -> list[str]:
    schema = load_schema(repo_root)
    incidents_dir = repo_root / "incidents"
    errors: list[str] = []
    seen_ids: dict[str, Path] = {}

    for yaml_path in sorted(incidents_dir.glob("*.yaml")):
        if yaml_path.name == "TEMPLATE.yaml":
            continue
        try:
            doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{yaml_path.name}: YAML parse error: {exc}")
            continue

        if not isinstance(doc, dict):
            errors.append(f"{yaml_path.name}: top-level must be a mapping")
            continue

        for msg in validate_incident(doc, schema):
            errors.append(f"{yaml_path.name}: {msg}")

        stem = yaml_path.stem
        doc_id = doc.get("id")
        if doc_id and doc_id != stem:
            errors.append(
                f"{yaml_path.name}: id '{doc_id}' does not match filename stem '{stem}'"
            )
        if doc_id:
            if doc_id in seen_ids:
                errors.append(
                    f"{yaml_path.name}: duplicate id '{doc_id}' "
                    f"(also in {seen_ids[doc_id].name})"
                )
            else:
                seen_ids[doc_id] = yaml_path

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    errors = validate_repository(repo_root)
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
        return 1
    print("OK: all incidents valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
