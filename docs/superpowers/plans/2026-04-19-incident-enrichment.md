# Incident enrichment implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich all 31 existing incident entries via heavy websearch with batched parallel subagents, producing reviewable drafts in `incidents/.drafts/` for bulk maintainer approval.

**Architecture:** A prep phase adds the sidecar scaffolding and a promotion helper; a pilot task validates the subagent protocol on one incident; seven batched enrichment tasks dispatch 3–5 parallel subagents each, with a serial vocab-consolidation task between batches; a final handoff commits the review artefacts and summarises next steps.

**Tech Stack:** Python 3.11+, uv, pytest, PyYAML, JSON Schema (Draft 2020-12), `superpowers:subagent-driven-development`, `WebSearch` / `WebFetch` tools inside subagents.

**Spec:** `docs/superpowers/specs/2026-04-19-incident-enrichment-design.md`

---

## Incident batch assignment

Seven batches (chronological event_date order; size 5/5/5/5/4/4/3 = 31):

- **Batch 1:** `2014-12-25_dzsf-import`, `2015-07-01_dzsf-import`, `2015-12-23_blackenergy3-killdisk`, `2016-03-04_nordkorea`, `2016-11-26_variante-hddcryptor`
- **Batch 2:** `2017-05-13_wannacry`, `2017-06-27_petya-variante`, `2017-10-01_dzsf-import`, `2017-10-12_dzsf-import`, `2017-11-18_dzsf-import`
- **Batch 3:** `2018-01-01_nordkorea`, `2018-05-14_dzsf-import`, `2019-01-01_dzsf-import`, `2020-01-27_dzsf-import`, `2020-04-16_dzsf-import`
- **Batch 4:** `2020-05-07_nefilim`, `2020-07-02_netwalker`, `2020-07-23_revil`, `2020-08-10_dzsf-import`, `2020-10-01_conti`
- **Batch 5:** `2020-10-28_ransomexx`, `2020-12-05_dzsf-import`, `2021-03-19_dzsf-import`, `2021-04-18_lockbit`
- **Batch 6:** `2021-04-20_dzsf-import`, `2021-07-09_meteor`, `2021-07-20_dzsf-import`, `2021-07-22_death-kitty`
- **Batch 7:** `2021-09-21_is`, `2021-10-24_badrabbit`, `2021-10-29_dzsf-import`

The pilot task (Task 5) runs the first incident of Batch 1 (`2014-12-25_dzsf-import`) alone to validate the protocol end-to-end; Task 6 dispatches the remaining four incidents of Batch 1 in parallel.

---

## Task 1: Create enrichment branch and sidecar scaffolding

**Files:**
- Create: `incidents/.drafts/` (directory, gitignored)
- Create: `incidents/.drafts/REVIEW.md`
- Create: `incidents/.drafts/VOCAB_PROPOSALS.md`
- Create: `incidents/.drafts/ESCALATIONS.md`
- Modify: `.gitignore`

- [ ] **Step 1: Create the enrichment branch**

```bash
git checkout -b enrich/incidents-2026-04
```

Expected: `Switched to a new branch 'enrich/incidents-2026-04'`

- [ ] **Step 2: Create the sidecar directory**

```bash
mkdir -p incidents/.drafts
```

- [ ] **Step 3: Seed `incidents/.drafts/REVIEW.md`**

```markdown
# Incident enrichment review — 2026-04-19

Maintainer's top-level triage file. One row per incident. Read this first,
then drill into per-incident drafts and logs as needed.

| id | status | sources | fields filled | needs_review flipped | vocab proposed | escalated | draft path |
|---|---|---|---|---|---|---|---|
```

Write exactly this content to `incidents/.drafts/REVIEW.md`.

- [ ] **Step 4: Seed `incidents/.drafts/VOCAB_PROPOSALS.md`**

```markdown
# Proposed vocabulary additions — 2026-04-19

Consolidated list of vocabulary values proposed by enrichment subagents.
Maintainer triages: accept (keep), rename, or reject before incident drafts
referencing the value are promoted to `incidents/`.

Proposals are appended in the order batches complete. Duplicates across
batches are deduplicated by the post-batch vocab-merge step.
```

Write exactly this content to `incidents/.drafts/VOCAB_PROPOSALS.md`.

- [ ] **Step 5: Seed `incidents/.drafts/ESCALATIONS.md`**

```markdown
# Escalations — 2026-04-19

Incidents where the subagent could not meet the ≥2-independent-source
threshold or found conflicting core facts. Each section documents what
was tried and recommends keep / annotate / drop.

Sorted (when multiple) by recommendation strength: strongest "drop" first,
strongest "keep" last — so similar cases batch together during review.
```

Write exactly this content to `incidents/.drafts/ESCALATIONS.md`.

- [ ] **Step 6: Append the drafts directory to `.gitignore`**

Read the current `.gitignore` to confirm `incidents/.drafts/` is not already present, then append:

```
# Enrichment sidecar drafts (see docs/superpowers/specs/2026-04-19-incident-enrichment-design.md)
incidents/.drafts/
```

- [ ] **Step 7: Verify drafts are ignored by git**

```bash
git status --short
```

Expected output contains:
```
 M .gitignore
```

and does NOT list anything under `incidents/.drafts/`.

- [ ] **Step 8: Commit scaffolding**

```bash
git add .gitignore
git commit -m "chore: set up incident enrichment sidecar"
```

Expected: one-line commit output with the commit SHA.

---

## Task 2: Regression test — validators ignore the drafts directory

**Files:**
- Modify: `tests/test_validate.py` (add two tests)
- Modify: `tests/test_build_release.py` (add one test)

Rationale: both `scripts/validate.py` and `scripts/build_release.py` currently use non-recursive `Path.glob("*.yaml")` on `incidents/`, which already skips subdirectories. This task locks that behaviour in with tests so a future refactor (e.g., to `rglob`) cannot silently pull draft files into validation or release artefacts.

- [ ] **Step 1: Write the failing test in `tests/test_validate.py`**

Append to `tests/test_validate.py`:

```python
def test_validator_ignores_drafts_directory(tmp_repo, minimal_incident):
    """Files under incidents/.drafts/ must never be validated."""
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    drafts_dir = tmp_repo / "incidents" / ".drafts"
    drafts_dir.mkdir()
    # A deliberately broken draft — missing required fields.
    _write(drafts_dir / "2099-12-31_broken.yaml", {"id": "nope"})
    errors = validate_repository(tmp_repo)
    assert errors == [], f"drafts dir must be skipped, got: {errors}"


def test_validator_ignores_hidden_subdirs_generally(tmp_repo, minimal_incident):
    """Regression: glob('*.yaml') on incidents/ must remain non-recursive."""
    _write(tmp_repo / "incidents" / "2020-01-01_example.yaml", minimal_incident)
    nested = tmp_repo / "incidents" / "subdir"
    nested.mkdir()
    _write(nested / "2099-12-31_broken.yaml", {"id": "nope"})
    errors = validate_repository(tmp_repo)
    assert errors == []
```

- [ ] **Step 2: Run tests to confirm they pass (they should already)**

```bash
uv run pytest tests/test_validate.py::test_validator_ignores_drafts_directory tests/test_validate.py::test_validator_ignores_hidden_subdirs_generally -v
```

Expected: 2 passed.

If they fail, investigate before proceeding — the behaviour we're locking in may already be broken.

- [ ] **Step 3: Inspect `tests/test_build_release.py` to learn its fixture style**

```bash
head -40 tests/test_build_release.py
```

Note the import names and fixture usage so the new test matches local style.

- [ ] **Step 4: Add an equivalent test to `tests/test_build_release.py`**

Append a test that calls the build entrypoint against a `tmp_repo` containing one valid incident and one broken draft under `.drafts/`. Assert the resulting CSV/JSONL contains exactly one row/line.

Implementation detail: if `build_release.py` doesn't currently take a repo-root argument, skip this step and record a one-line comment in the file explaining why, pointing back to this task. (The validator test alone covers the critical case; the release builder only fails silently on drafts in the worst case.)

- [ ] **Step 5: Run the full validate + build test suites**

```bash
uv run pytest tests/test_validate.py tests/test_build_release.py -v
```

Expected: all tests pass, including the new ones.

- [ ] **Step 6: Commit**

```bash
git add tests/test_validate.py tests/test_build_release.py
git commit -m "test: lock in non-recursive incidents globbing"
```

---

## Task 3: Implement `scripts/promote_drafts.py` (TDD)

**Files:**
- Create: `scripts/promote_drafts.py`
- Create: `tests/test_promote_drafts.py`

A small helper to move approved drafts from `incidents/.drafts/<id>.yaml` to `incidents/<id>.yaml` with a pre-flight check that every referenced vocabulary value exists in the real vocab files.

- [ ] **Step 1: Write the first failing test — `--only` promotes a single draft**

Create `tests/test_promote_drafts.py`:

```python
from pathlib import Path
import yaml
import pytest

from scripts.promote_drafts import promote, PromotionError


def _make_draft(repo: Path, incident_id: str, doc: dict) -> Path:
    drafts = repo / "incidents" / ".drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    path = drafts / f"{incident_id}.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def _make_original(repo: Path, incident_id: str, doc: dict) -> Path:
    path = repo / "incidents" / f"{incident_id}.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def test_only_promotes_single_incident(tmp_repo, minimal_incident):
    incident_id = minimal_incident["id"]
    _make_original(tmp_repo, incident_id, {"id": incident_id, "stub": True})
    _make_draft(tmp_repo, incident_id, minimal_incident)

    promoted = promote(tmp_repo, only=[incident_id])

    assert promoted == [incident_id]
    final_path = tmp_repo / "incidents" / f"{incident_id}.yaml"
    assert yaml.safe_load(final_path.read_text()) == minimal_incident
    assert not (tmp_repo / "incidents" / ".drafts" / f"{incident_id}.yaml").exists()
```

- [ ] **Step 2: Run to confirm it fails**

```bash
uv run pytest tests/test_promote_drafts.py::test_only_promotes_single_incident -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.promote_drafts'`.

- [ ] **Step 3: Implement the minimal `promote` function**

Create `scripts/promote_drafts.py`:

```python
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

    promoted: list[str] = []
    for incident_id in candidates:
        src = _drafts_dir(repo_root) / f"{incident_id}.yaml"
        if not src.exists():
            raise PromotionError(f"no draft for {incident_id}")
        dst = _incidents_dir(repo_root) / f"{incident_id}.yaml"
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
```

- [ ] **Step 4: Run the test to confirm it passes**

```bash
uv run pytest tests/test_promote_drafts.py::test_only_promotes_single_incident -v
```

Expected: PASS.

- [ ] **Step 5: Add the missing-vocab safety check — failing test**

Append to `tests/test_promote_drafts.py`:

```python
def test_refuses_to_promote_when_draft_uses_unknown_vocab(tmp_repo, minimal_incident):
    incident_id = minimal_incident["id"]
    draft = dict(minimal_incident)
    # affected_systems references a value not in vocabularies/affected_systems.yaml
    draft["affected_systems"] = ["not_a_real_system"]
    _make_draft(tmp_repo, incident_id, draft)

    with pytest.raises(PromotionError, match="not_a_real_system"):
        promote(tmp_repo, only=[incident_id])

    # Draft must still be in place — nothing moved.
    assert (tmp_repo / "incidents" / ".drafts" / f"{incident_id}.yaml").exists()
```

- [ ] **Step 6: Run it — expect failure**

```bash
uv run pytest tests/test_promote_drafts.py::test_refuses_to_promote_when_draft_uses_unknown_vocab -v
```

Expected: FAIL — the current implementation doesn't check vocabularies.

- [ ] **Step 7: Add the vocab pre-flight check to `promote_drafts.py`**

Edit `scripts/promote_drafts.py` — add helper and call it before moving files:

```python
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
    values = yaml.safe_load(path.read_text()) or []
    return {v for v in values if isinstance(v, str)}


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
    return violations
```

Then in `promote`, before the `shutil.move`:

```python
        draft = yaml.safe_load(src.read_text())
        violations = _vocab_violations(repo_root, draft)
        if violations:
            raise PromotionError(
                f"{incident_id}: cannot promote, vocab not merged: {'; '.join(violations)}"
            )
```

- [ ] **Step 8: Run the vocab test to confirm it passes**

```bash
uv run pytest tests/test_promote_drafts.py::test_refuses_to_promote_when_draft_uses_unknown_vocab -v
```

Expected: PASS.

- [ ] **Step 9: Run the whole new test file**

```bash
uv run pytest tests/test_promote_drafts.py -v
```

Expected: both tests pass.

- [ ] **Step 10: Lint the new script**

```bash
uv run ruff check scripts/promote_drafts.py tests/test_promote_drafts.py
```

Expected: no errors. Fix any reported issues inline before continuing.

- [ ] **Step 11: Commit**

```bash
git add scripts/promote_drafts.py tests/test_promote_drafts.py
git commit -m "feat: add promote_drafts.py helper with vocab safety check"
```

---

## Task 4: Write the subagent prompt template

**Files:**
- Create: `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md`

This is the fixed protocol every enrichment subagent receives. It is referenced verbatim by Tasks 5, 6, 8, 10, 12, 14, 16, 18. Keeping it in one file avoids drift across dispatches.

- [ ] **Step 1: Create the prompt template file**

Write the following verbatim to `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md`:

````markdown
# Enrichment subagent prompt — 2026-04-19

You are a research subagent enriching one railway-cyber-incident YAML entry. The
repository is a curated dataset of real-world railway cyber incidents; your job
is to fill schema fields from credible public sources while being strictly
disciplined about what counts as "confirmed".

## Your inputs

- **Incident ID:** `{{INCIDENT_ID}}`
- **Current YAML:** `incidents/{{INCIDENT_ID}}.yaml` — read it first.
- **Schema:** `schema/incident.schema.json`
- **Codebook:** `CODEBOOK.md`
- **Vocabularies:** `vocabularies/*.yaml`

## Hard rules (non-negotiable)

1. **Prefer `null` over invention.** If a field is not attested by a credible
   public source, leave it `null`. Never fabricate threat actors, attributions,
   dates, or numbers.
2. Filename stem must equal the `id` field.
3. Source URLs must be absolute `http(s)://...`.
4. All dates are ISO 8601 strings (`YYYY-MM-DD`).
5. `event_date <= reported_date` when both are set.
6. Any value you put in a vocabulary-controlled field must either already be
   in the relevant `vocabularies/*.yaml`, or be added to a per-incident scratch
   file (see Vocabulary Expansion below) — never invent a value and use it
   without a scratch-file entry.

## Research protocol

Perform **at least 20** distinct web searches across 5 rounds. Record every
query in the research log.

- **Round 1 — Broad English:** e.g. `"<country> railway cyberattack <year>"`,
  `"<target_org> cyber incident"` if known.
- **Round 2 — Narrow English + CERT advisories:** BSI, ENISA, CISA, NCSC,
  CERT-FR, CERT-Bund. Combine known malware family or threat actor names.
- **Round 3 — German press and academic sources:** heise, Golem, Tagesschau,
  FAZ, SZ, DZSF references, academic papers.
- **Round 4 — Native language of the incident country:** only when it surfaces
  facts absent from EN/DE sources. (e.g., Russian for RU, Mandarin for CN,
  Farsi for IR, Korean for KR.)
- **Round 5 — Cross-checks:** MITRE ATT&CK technique lookups, MITRE Software
  IDs (`S\d{4}`), Wikipedia incident pages, vendor threat reports (Mandiant,
  Kaspersky, ESET, Dragos, Claroty).

For each accepted source, record: URL, publisher, publication date, language,
and which facts it supports. For rejected sources, record the reason briefly.

## Independence threshold

Count a source as **independent** only if it is a distinct publisher.
Syndicated wire copies of the same Reuters/AP story count as one.

- If ≥2 independent non-DZSF sources corroborate the core facts (date, country,
  that it happened, and ideally target org): you may set `needs_review: false`
  on a draft that started `true`. On a draft that started `false`, keep
  `false`.
- Below the threshold: keep the original `needs_review` value, do **not**
  regress `false` to `true`, and emit an escalation entry.

## Field mapping

For every non-null field in your draft, the research log must record which
source(s) attest to it. Default to `null` for:

- `threat_actor` / `threat_actor_country` / `attribution_confidence` when no
  credible attribution exists.
- Any quantitative field in `impact.magnitude` (trains / passengers / damage)
  unless at least one source gives a specific figure.
- `mitre_attack_techniques` unless a primary or vendor source maps the
  incident to specific techniques.

## Vocabulary expansion (scratch files)

If you need a value that isn't in the vocabulary:

1. Write the proposal to `incidents/.drafts/{{INCIDENT_ID}}.vocab.yaml` with
   the structure:
   ```yaml
   - vocab: industry_sectors       # filename stem in vocabularies/
     value: freight_terminal       # proposed new value
     justification: >
       Incident at a container/freight terminal — distinct from line-haul
       `freight`. Source: https://example.org/...
   ```
2. Use the proposed value in your draft YAML.
3. Also append a section to `incidents/.drafts/VOCAB_PROPOSALS.md`:
   ```markdown
   ## Proposed: industry_sectors.freight_terminal
   - Needed by: {{INCIDENT_ID}}
   - Justification: ...
   - Source supporting the need: https://...
   ```
   Append-only — do not rewrite existing sections. If another batch already
   proposed the same value, add your incident ID to the existing "Needed by"
   line.

Do **not** edit `vocabularies/*.yaml` directly. The serial post-batch
vocab-merge step consolidates scratch files into real vocab files.

## Escalation conditions

Emit an escalation entry to `incidents/.drafts/ESCALATIONS.md` when:

- Fewer than 2 independent non-DZSF sources found after ≥20 queries.
- Sources disagree on a core fact you cannot resolve.
- You suspect the incident is misclassified (not actually railway, not
  actually cyber, or duplicated by another entry).

Escalation entry format:

```markdown
## {{INCIDENT_ID}} — <one-line reason>
- Searches attempted: <N> (see log)
- Independent non-DZSF sources found: <N>
- Specific gap or conflict: <one paragraph>
- Subagent recommendation: keep | annotate | drop
- Maintainer decision: [ ] keep / [ ] annotate / [ ] drop
```

On escalation you still produce a draft YAML (with partial findings and
`needs_review` unchanged from the original), a research log, and a REVIEW.md
row. You do **not** append `"Lukas Iffländer"` to `contributors:` on pure
escalations.

## Significant enrichment attribution

Append `"Lukas Iffländer"` to `contributors:` **only** when both conditions
hold:

1. At least one new non-DZSF source has been added to `sources:`.
2. At least three fields have been moved off `null` or default placeholders.

Otherwise leave `contributors:` unchanged.

## Outputs (all under `incidents/.drafts/`)

1. `{{INCIDENT_ID}}.yaml` — the full proposed replacement entry. `last_updated: 2026-04-19`.
2. `{{INCIDENT_ID}}.log.md` — the research log, using the format in the spec.
3. `{{INCIDENT_ID}}.vocab.yaml` — only if vocab proposals exist.
4. One appended row in `REVIEW.md`:
   ```markdown
   | {{INCIDENT_ID}} | <drafted|re-verified|escalated> | <sources count> | <filled>/<total> | <yes|no|no change> | <vocab keys, comma-separated, or —> | <yes|—> | .drafts/{{INCIDENT_ID}}.yaml |
   ```
5. Appended section in `VOCAB_PROPOSALS.md` if applicable.
6. Appended section in `ESCALATIONS.md` if applicable.

## Self-validation before returning

Before writing your outputs, run the invariants `scripts/validate.py` checks:

- Filename stem equals `id`.
- All dates ISO 8601, `event_date <= reported_date`.
- All source URLs match `^https?://[^\s/?#]+...`.
- Every value in a vocabulary-controlled field is either in the real vocab
  or in your `{{INCIDENT_ID}}.vocab.yaml`.

If you cannot self-validate, that is a bug — escalate rather than ship a
broken draft.

## Return summary (for the orchestrator)

Return a short JSON object:

```json
{
  "incident_id": "{{INCIDENT_ID}}",
  "status": "drafted | re-verified | escalated | failed",
  "sources_found": <int>,
  "non_dzsf_sources_found": <int>,
  "fields_filled": <int>,
  "needs_review_final": true | false,
  "vocab_proposed": ["industry_sectors.freight_terminal", ...],
  "escalated": true | false,
  "significant_enrichment": true | false,
  "draft_path": "incidents/.drafts/{{INCIDENT_ID}}.yaml",
  "log_path": "incidents/.drafts/{{INCIDENT_ID}}.log.md"
}
```
````

- [ ] **Step 2: Commit the prompt template**

```bash
git add docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md
git commit -m "docs: add enrichment subagent prompt template"
```

---

## Task 5: Pilot run — enrich `2014-12-25_dzsf-import`

**Files (subagent writes):**
- Create: `incidents/.drafts/2014-12-25_dzsf-import.yaml`
- Create: `incidents/.drafts/2014-12-25_dzsf-import.log.md`
- (conditional) Create: `incidents/.drafts/2014-12-25_dzsf-import.vocab.yaml`
- Modify: `incidents/.drafts/REVIEW.md` (append row)
- (conditional) Modify: `incidents/.drafts/VOCAB_PROPOSALS.md`, `incidents/.drafts/ESCALATIONS.md`

Pilot a single incident to validate the protocol before parallel dispatch.
This is a sanity check: if the subagent misunderstands any part of the
prompt template, catch it now with one incident rather than five in parallel.

- [ ] **Step 1: Dispatch the enrichment subagent**

Use the `Agent` tool with `subagent_type: general-purpose`, `run_in_background: false`.

**Agent description:** `Pilot enrichment: 2014-12-25_dzsf-import`

**Agent prompt:** the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with `{{INCIDENT_ID}}` substituted for `2014-12-25_dzsf-import` throughout. Also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."

- [ ] **Step 2: Inspect the returned summary**

Verify the JSON summary has:
- `incident_id: "2014-12-25_dzsf-import"`
- `status` is one of `drafted | re-verified | escalated | failed`
- `draft_path` and `log_path` point to existing files

If `status: failed`: do not continue. Read the agent's last message, diagnose, and re-run. Cap retries at 2.

- [ ] **Step 3: Verify outputs on disk**

```bash
ls -la incidents/.drafts/2014-12-25_dzsf-import*
```

Expected: at least `.yaml` and `.log.md`; optionally `.vocab.yaml`.

- [ ] **Step 4: Verify REVIEW.md has exactly one row appended**

```bash
grep "2014-12-25_dzsf-import" incidents/.drafts/REVIEW.md | wc -l
```

Expected: `1`.

- [ ] **Step 5: Self-validate the draft YAML**

```bash
uv run python -c "
from pathlib import Path
import yaml
from scripts.validate import validate_incident, load_schema
doc = yaml.safe_load(Path('incidents/.drafts/2014-12-25_dzsf-import.yaml').read_text())
errors = validate_incident(doc, load_schema(Path('.')))
# Vocab violations are expected here if the draft references proposed vocab values.
# Filter those out; all other errors should be empty.
vocab_only = [e for e in errors if 'is not one of' in e or 'is not valid' in e]
schema_errors = [e for e in errors if e not in vocab_only]
print('SCHEMA_ERRORS:', schema_errors)
print('VOCAB_ONLY:', vocab_only)
assert schema_errors == [], f'non-vocab schema errors: {schema_errors}'
print('OK')
"
```

Expected: `OK`. If schema errors beyond vocab gaps appear, the subagent's self-validation step failed — escalate the pilot itself as a protocol bug, update the prompt template, and retry.

- [ ] **Step 6: Update the plan's checkbox for this task**

Mark this task's checkboxes as done in this plan file. No commit yet; commits are deferred to Task 20.

- [ ] **Step 7: Proceed to Task 6 only if the pilot produced a valid draft**

If the pilot escalated (low evidence) but the YAML and log are well-formed, that is still a success — the protocol works. Continue.

If the pilot failed or produced a malformed draft twice, **stop** and report the failure mode to the user. Do not kick off Batch 1's parallel run with a broken protocol.

---

## Task 6: Batch 1 enrichment — remaining 4 incidents

**Files (subagents write, parallel):**
- Per incident in: `2015-07-01_dzsf-import`, `2015-12-23_blackenergy3-killdisk`, `2016-03-04_nordkorea`, `2016-11-26_variante-hddcryptor`
  - `incidents/.drafts/<id>.yaml`
  - `incidents/.drafts/<id>.log.md`
  - (conditional) `incidents/.drafts/<id>.vocab.yaml`
  - appended rows/sections in REVIEW.md / VOCAB_PROPOSALS.md / ESCALATIONS.md

- [ ] **Step 1: Dispatch 4 parallel enrichment subagents in a single message**

Issue one `Agent` tool call per incident in the same message (so they run concurrently):
- `2015-07-01_dzsf-import`
- `2015-12-23_blackenergy3-killdisk`
- `2016-03-04_nordkorea`
- `2016-11-26_variante-hddcryptor`

Each agent gets:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the prompt template verbatim with `{{INCIDENT_ID}}` substituted.

- [ ] **Step 2: Collect JSON summaries**

Record each summary in a working note. For any with `status: failed`, re-dispatch (cap at 2 retries); after 2 failures, treat as escalation-by-subagent-failure and add a section to ESCALATIONS.md.

- [ ] **Step 3: Verify each incident has the expected files**

```bash
for id in 2015-07-01_dzsf-import 2015-12-23_blackenergy3-killdisk 2016-03-04_nordkorea 2016-11-26_variante-hddcryptor; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

Expected: 4 `OK` lines.

- [ ] **Step 4: Verify REVIEW.md has a row for each**

```bash
for id in 2015-07-01_dzsf-import 2015-12-23_blackenergy3-killdisk 2016-03-04_nordkorea 2016-11-26_variante-hddcryptor; do
  grep -c "${id}" incidents/.drafts/REVIEW.md | xargs -I{} test {} -eq 1 && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

Expected: 4 `OK` lines.

- [ ] **Step 5: Tally escalations**

```bash
grep -c '^## ' incidents/.drafts/ESCALATIONS.md || true
```

If total escalations (cumulative across all batches so far) is ≥10, **stop** and report to the user. Do not continue to Task 7 or later batches.

- [ ] **Step 6: Mark this task's checkboxes done in the plan file**

No commit yet.

---

## Task 7: Post-batch vocab merge — after Batch 1

**Files:**
- Modify: one or more `vocabularies/*.yaml`
- Delete: any `incidents/.drafts/*.vocab.yaml` produced by Batch 1

**Runs serially — never as a subagent.** Consolidates per-incident scratch files from Batch 1 into real vocab files.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none: skip to Step 6.

- [ ] **Step 2: Merge scratch entries into `vocabularies/*.yaml`**

For each `.vocab.yaml` file, for each entry `{vocab: X, value: Y, justification: Z}`:

1. Read `vocabularies/<X>.yaml` (it is a YAML list of strings).
2. If `Y` is already present (either plain or with a `# PROPOSED` comment): skip.
3. Otherwise append a new list item as the **last** line:
   ```yaml
   - Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md
   ```

Use a short Python one-liner via `uv run python -c '...'` if there are many, or edit by hand for ≤3.

- [ ] **Step 3: Verify the vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate VOCAB_PROPOSALS.md if two subagents added the same proposal**

Read `incidents/.drafts/VOCAB_PROPOSALS.md`. If two `## Proposed: X.Y` sections exist for the same `X.Y`, merge them: keep one section, combine the "Needed by" lists.

- [ ] **Step 6: Mark this task's checkboxes done in the plan file**

No commit yet.

---

## Task 8: Batch 2 enrichment (5 incidents)

**Incidents:** `2017-05-13_wannacry`, `2017-06-27_petya-variante`, `2017-10-01_dzsf-import`, `2017-10-12_dzsf-import`, `2017-11-18_dzsf-import`

Note: `2017-05-13_wannacry` starts with `needs_review: false` — this is the re-verification case. Per the prompt template, if <2 independent non-DZSF sources corroborate, keep `false` and escalate; never regress to `true`.

- [ ] **Step 1: Dispatch 5 parallel enrichment subagents in a single message**

Issue five `Agent` tool calls in the **same message** (so they run concurrently), one per incident ID:
`2017-05-13_wannacry`, `2017-06-27_petya-variante`, `2017-10-01_dzsf-import`, `2017-10-12_dzsf-import`, `2017-11-18_dzsf-import`.

Each call uses:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with every `{{INCIDENT_ID}}` literal replaced by that agent's incident ID.

At the end of the prompt also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."

- [ ] **Step 2: Collect JSON summaries; retry any failures up to 2 times; record escalations for repeat failures.**

- [ ] **Step 3: Verify files**

```bash
for id in 2017-05-13_wannacry 2017-06-27_petya-variante 2017-10-01_dzsf-import 2017-10-12_dzsf-import 2017-11-18_dzsf-import; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

Expected: 5 `OK` lines.

- [ ] **Step 4: Verify REVIEW.md rows**

```bash
for id in 2017-05-13_wannacry 2017-06-27_petya-variante 2017-10-01_dzsf-import 2017-10-12_dzsf-import 2017-11-18_dzsf-import; do
  grep -c "${id}" incidents/.drafts/REVIEW.md | xargs -I{} test {} -eq 1 && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

Expected: 5 `OK` lines.

- [ ] **Step 5: Tally cumulative escalations; stop if ≥10.**

```bash
grep -c '^## ' incidents/.drafts/ESCALATIONS.md || true
```

- [ ] **Step 6: Mark this task's checkboxes done in the plan file.**

---

## Task 9: Post-batch vocab merge — after Batch 2

Serial consolidation of any `*.vocab.yaml` scratch files produced by Batch 2. Runs as the orchestrator itself, never as a subagent.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none, skip to Step 6.

- [ ] **Step 2: Merge scratch entries into real vocab files**

For each `incidents/.drafts/*.vocab.yaml`, for every entry `{vocab: X, value: Y, justification: Z}`:

1. Read `vocabularies/<X>.yaml` (a YAML list of strings).
2. If `Y` is already present (plain or with a `# PROPOSED` comment), skip it.
3. Otherwise append a new list item as the **last** line of the file:
   ```yaml
   - Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md
   ```

Use inline Python (`uv run python -c '...'`) for batches with many entries, or hand-edit for ≤3.

- [ ] **Step 3: Verify vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate `VOCAB_PROPOSALS.md`**

Read `incidents/.drafts/VOCAB_PROPOSALS.md`. If two `## Proposed: X.Y` sections exist for the same `X.Y` (two subagents proposing the same value independently), merge them: keep one section, combine their "Needed by" lists into a single comma-separated line.

- [ ] **Step 6: Mark checkboxes done in the plan file.**

---

## Task 10: Batch 3 enrichment (5 incidents)

**Incidents:** `2018-01-01_nordkorea`, `2018-05-14_dzsf-import`, `2019-01-01_dzsf-import`, `2020-01-27_dzsf-import`, `2020-04-16_dzsf-import`

- [ ] **Step 1: Dispatch 5 parallel enrichment subagents in a single message**

Issue five `Agent` tool calls in the **same message**, one per Batch 3 incident ID. Each call uses:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with every `{{INCIDENT_ID}}` literal replaced by that agent's incident ID.

At the end of the prompt also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."
- [ ] **Step 2: Collect JSON summaries; retry failures up to 2 times.**
- [ ] **Step 3: Verify files**

```bash
for id in 2018-01-01_nordkorea 2018-05-14_dzsf-import 2019-01-01_dzsf-import 2020-01-27_dzsf-import 2020-04-16_dzsf-import; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

- [ ] **Step 4: Verify REVIEW.md rows (1 per incident).**
- [ ] **Step 5: Tally cumulative escalations; stop if ≥10.**
- [ ] **Step 6: Mark checkboxes done.**

---

## Task 11: Post-batch vocab merge — after Batch 3

Serial consolidation of any `*.vocab.yaml` scratch files produced by Batch 3.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none, skip to Step 6.

- [ ] **Step 2: Merge scratch entries into real vocab files.** For each `{vocab: X, value: Y, justification: Z}` entry, read `vocabularies/<X>.yaml`, skip if `Y` is already present, otherwise append `- Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md` as the last line.
- [ ] **Step 3: Verify vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate `VOCAB_PROPOSALS.md`** — merge duplicate `## Proposed: X.Y` sections.
- [ ] **Step 6: Mark checkboxes done in the plan file.**

---

## Task 12: Batch 4 enrichment (5 incidents)

**Incidents:** `2020-05-07_nefilim`, `2020-07-02_netwalker`, `2020-07-23_revil`, `2020-08-10_dzsf-import`, `2020-10-01_conti`

- [ ] **Step 1: Dispatch 5 parallel enrichment subagents in a single message**

Issue five `Agent` tool calls in the **same message**, one per Batch 4 incident ID. Each call uses:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with every `{{INCIDENT_ID}}` literal replaced by that agent's incident ID.

At the end of the prompt also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."
- [ ] **Step 2: Collect summaries; retry failures.**
- [ ] **Step 3: Verify files**

```bash
for id in 2020-05-07_nefilim 2020-07-02_netwalker 2020-07-23_revil 2020-08-10_dzsf-import 2020-10-01_conti; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

- [ ] **Step 4: Verify REVIEW.md rows.**
- [ ] **Step 5: Tally cumulative escalations; stop if ≥10.**
- [ ] **Step 6: Mark checkboxes done.**

---

## Task 13: Post-batch vocab merge — after Batch 4

Serial consolidation of any `*.vocab.yaml` scratch files produced by Batch 4.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none, skip to Step 6.

- [ ] **Step 2: Merge scratch entries into real vocab files.** For each `{vocab: X, value: Y, justification: Z}` entry, read `vocabularies/<X>.yaml`, skip if `Y` is already present, otherwise append `- Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md` as the last line.
- [ ] **Step 3: Verify vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate `VOCAB_PROPOSALS.md`** — merge duplicate `## Proposed: X.Y` sections.
- [ ] **Step 6: Mark checkboxes done in the plan file.**

---

## Task 14: Batch 5 enrichment (4 incidents)

**Incidents:** `2020-10-28_ransomexx`, `2020-12-05_dzsf-import`, `2021-03-19_dzsf-import`, `2021-04-18_lockbit`

- [ ] **Step 1: Dispatch 4 parallel enrichment subagents in a single message**

Issue four `Agent` tool calls in the **same message**, one per Batch 5 incident ID. Each call uses:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with every `{{INCIDENT_ID}}` literal replaced by that agent's incident ID.

At the end of the prompt also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."
- [ ] **Step 2: Collect summaries; retry failures.**
- [ ] **Step 3: Verify files**

```bash
for id in 2020-10-28_ransomexx 2020-12-05_dzsf-import 2021-03-19_dzsf-import 2021-04-18_lockbit; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

- [ ] **Step 4: Verify REVIEW.md rows.**
- [ ] **Step 5: Tally cumulative escalations; stop if ≥10.**
- [ ] **Step 6: Mark checkboxes done.**

---

## Task 15: Post-batch vocab merge — after Batch 5

Serial consolidation of any `*.vocab.yaml` scratch files produced by Batch 5.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none, skip to Step 6.

- [ ] **Step 2: Merge scratch entries into real vocab files.** For each `{vocab: X, value: Y, justification: Z}` entry, read `vocabularies/<X>.yaml`, skip if `Y` is already present, otherwise append `- Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md` as the last line.
- [ ] **Step 3: Verify vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate `VOCAB_PROPOSALS.md`** — merge duplicate `## Proposed: X.Y` sections.
- [ ] **Step 6: Mark checkboxes done in the plan file.**

---

## Task 16: Batch 6 enrichment (4 incidents)

**Incidents:** `2021-04-20_dzsf-import`, `2021-07-09_meteor`, `2021-07-20_dzsf-import`, `2021-07-22_death-kitty`

- [ ] **Step 1: Dispatch 4 parallel enrichment subagents in a single message**

Issue four `Agent` tool calls in the **same message**, one per Batch 6 incident ID. Each call uses:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with every `{{INCIDENT_ID}}` literal replaced by that agent's incident ID.

At the end of the prompt also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."
- [ ] **Step 2: Collect summaries; retry failures.**
- [ ] **Step 3: Verify files**

```bash
for id in 2021-04-20_dzsf-import 2021-07-09_meteor 2021-07-20_dzsf-import 2021-07-22_death-kitty; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

- [ ] **Step 4: Verify REVIEW.md rows.**
- [ ] **Step 5: Tally cumulative escalations; stop if ≥10.**
- [ ] **Step 6: Mark checkboxes done.**

---

## Task 17: Post-batch vocab merge — after Batch 6

Serial consolidation of any `*.vocab.yaml` scratch files produced by Batch 6.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none, skip to Step 6.

- [ ] **Step 2: Merge scratch entries into real vocab files.** For each `{vocab: X, value: Y, justification: Z}` entry, read `vocabularies/<X>.yaml`, skip if `Y` is already present, otherwise append `- Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md` as the last line.
- [ ] **Step 3: Verify vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate `VOCAB_PROPOSALS.md`** — merge duplicate `## Proposed: X.Y` sections.
- [ ] **Step 6: Mark checkboxes done in the plan file.**

---

## Task 18: Batch 7 enrichment (3 incidents)

**Incidents:** `2021-09-21_is`, `2021-10-24_badrabbit`, `2021-10-29_dzsf-import`

- [ ] **Step 1: Dispatch 3 parallel enrichment subagents in a single message**

Issue three `Agent` tool calls in the **same message**, one per Batch 7 incident ID. Each call uses:
- `subagent_type: general-purpose`
- `run_in_background: false`
- `description: Enrich <id>`
- `prompt`: the full contents of `docs/superpowers/plans/2026-04-19-enrichment-subagent-prompt.md` with every `{{INCIDENT_ID}}` literal replaced by that agent's incident ID.

At the end of the prompt also tell the agent: "Return the JSON summary at the end of your final message — do not add anything after it."
- [ ] **Step 2: Collect summaries; retry failures.**
- [ ] **Step 3: Verify files**

```bash
for id in 2021-09-21_is 2021-10-24_badrabbit 2021-10-29_dzsf-import; do
  test -f "incidents/.drafts/${id}.yaml" && test -f "incidents/.drafts/${id}.log.md" && echo "OK  ${id}" || echo "FAIL ${id}"
done
```

- [ ] **Step 4: Verify REVIEW.md rows.**
- [ ] **Step 5: Tally cumulative escalations; stop if ≥10.**
- [ ] **Step 6: Mark checkboxes done.**

---

## Task 19: Post-batch vocab merge — after Batch 7

Serial consolidation of any `*.vocab.yaml` scratch files produced by Batch 7.

- [ ] **Step 1: Enumerate scratch files**

```bash
ls incidents/.drafts/*.vocab.yaml 2>/dev/null || echo "(no vocab proposals)"
```

If none, skip to Step 6.

- [ ] **Step 2: Merge scratch entries into real vocab files.** For each `{vocab: X, value: Y, justification: Z}` entry, read `vocabularies/<X>.yaml`, skip if `Y` is already present, otherwise append `- Y  # PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md` as the last line.
- [ ] **Step 3: Verify vocab files still parse**

```bash
uv run python -c "
import yaml
from pathlib import Path
for p in sorted(Path('vocabularies').glob('*.yaml')):
    yaml.safe_load(p.read_text())
print('OK')
"
```

- [ ] **Step 4: Delete processed scratch files**

```bash
rm incidents/.drafts/*.vocab.yaml
```

- [ ] **Step 5: Deduplicate `VOCAB_PROPOSALS.md`** — merge duplicate `## Proposed: X.Y` sections.
- [ ] **Step 6: Mark checkboxes done in the plan file.**

---

## Task 20: Final review handoff — verify, commit, summarise

**Files:**
- Modify: this plan file (all checkboxes complete).
- Add: `incidents/.drafts/REVIEW.md`, `incidents/.drafts/VOCAB_PROPOSALS.md`, `incidents/.drafts/ESCALATIONS.md` to git via an exception commit (they live in a gitignored directory, so use `git add -f`).
- Modify: `vocabularies/*.yaml` (new values with `# PROPOSED` comments).
- Commit all of the above on branch `enrich/incidents-2026-04`.

- [ ] **Step 1: Verify every non-escalated incident has a draft YAML and log**

```bash
uv run python -c "
from pathlib import Path
expected = [p.stem for p in sorted(Path('incidents').glob('*.yaml')) if p.stem != 'TEMPLATE']
missing = []
for stem in expected:
    if not (Path('incidents/.drafts') / f'{stem}.yaml').exists():
        missing.append(stem)
print('MISSING:', missing)
assert not missing, missing
print('OK')
"
```

Expected: `OK`. If `MISSING` is non-empty, return to the relevant batch task and re-dispatch.

- [ ] **Step 2: Cross-check REVIEW.md row count matches draft count**

```bash
DRAFTS=$(ls incidents/.drafts/*.yaml | grep -v '\.vocab\.yaml' | wc -l)
ROWS=$(grep -Ec '^\| 20[0-9]{2}-' incidents/.drafts/REVIEW.md)
echo "drafts=$DRAFTS rows=$ROWS"
test "$DRAFTS" = "$ROWS" && echo "OK" || echo "MISMATCH"
```

Expected: `OK` (31 drafts, 31 rows). If mismatched, a subagent forgot to append its REVIEW.md row — inspect and append manually.

- [ ] **Step 3: Final escalation and vocab-proposal tallies**

```bash
echo "escalations: $(grep -c '^## ' incidents/.drafts/ESCALATIONS.md || true)"
echo "vocab proposals: $(grep -c '^## Proposed:' incidents/.drafts/VOCAB_PROPOSALS.md || true)"
```

Record these numbers in the handoff summary (Step 7).

- [ ] **Step 4: Force-add the review artefacts (they live in a gitignored dir)**

```bash
git add -f incidents/.drafts/REVIEW.md incidents/.drafts/VOCAB_PROPOSALS.md incidents/.drafts/ESCALATIONS.md
```

Draft YAMLs and log files stay gitignored; only the three review-overview files are committed for audit.

- [ ] **Step 5: Add updated vocabularies and this plan file**

```bash
git add vocabularies/*.yaml docs/superpowers/plans/2026-04-19-incident-enrichment.md
```

- [ ] **Step 6: Commit**

```bash
git commit -m "$(cat <<'EOF'
chore: 2026-04 incident enrichment — drafts and review artefacts

Produced drafts for all 31 incidents via batched parallel subagents.
Proposed vocabulary additions marked `# PROPOSED` pending maintainer review.
Review artefacts committed for audit: REVIEW.md, VOCAB_PROPOSALS.md,
ESCALATIONS.md.

Next: maintainer bulk review per docs/superpowers/specs/2026-04-19-incident-enrichment-design.md.
EOF
)"
```

- [ ] **Step 7: Print the handoff summary**

Emit a final message summarising:
- Total drafts produced (should be 31).
- Number of `drafted` vs `re-verified` vs `escalated` vs `failed`.
- Number of vocab proposals.
- Number of escalations.
- The exact next-step instructions for the maintainer:

  > 1. Review `incidents/.drafts/VOCAB_PROPOSALS.md`. Accept/rename/reject each proposed value in `vocabularies/*.yaml` (strip `# PROPOSED` comments on accepted ones). Create child branch `enrich/vocab-2026-04`, commit, merge into `enrich/incidents-2026-04`.
  > 2. Review `incidents/.drafts/ESCALATIONS.md`. For each: mark keep/annotate/drop, editing drafts or deleting as appropriate.
  > 3. Spot-check drafts by reading `incidents/.drafts/<id>.yaml` and `incidents/.drafts/<id>.log.md` side-by-side.
  > 4. Promote approved drafts: `uv run python scripts/promote_drafts.py --all` (or `--only <id>` per incident for per-commit granularity).
  > 5. Run the full CI chain: `make lint && make validate && make test && make build && uv run frictionless validate dist/datapackage.json`.
  > 6. Commit per-incident (`feat: enrich <id>`), then merge `enrich/incidents-2026-04` into `main`.

---

## Open notes

- **Resumability:** Each task is independently verifiable on disk. If a session ends mid-plan, the next session reads the plan, identifies tasks whose verification commands still fail, and re-dispatches only those. `attempt_count` lives in the session's working notes (per the spec's retry cap of 2) and does not need to be persisted in the plan file.
- **Context budget:** The orchestrator must not load every draft and log back into its context after each batch. Trust the subagent's return JSON summary plus the one-shot disk checks; only read individual drafts when a check fails or for the final handoff summary.
- **If Task 2 Step 4 is skipped** (build_release.py lacks a repo-root argument), the comment recording why must point back to this plan; no future task depends on it.
