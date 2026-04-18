# Incident enrichment — design spec

**Date:** 2026-04-19
**Author:** Lukas Iffländer (via brainstorming session)
**Scope:** Update all 31 existing incident entries in `incidents/*.yaml` via extensive websearch, producing reviewable drafts for bulk human approval.

## Goal

Promote the 30 entries currently flagged `needs_review: true` to fully enriched records, and re-verify the 1 entry already flagged `needs_review: false` (`2017-05-13_wannacry`). Enrichment means: fill schema fields from credible public sources, add proper citations to `sources:`, normalise vocabularies, and bump `last_updated`.

This is a data-quality pass, not a schema change. `schema_version` stays `"1.0"`.

## Success criteria

- Every incident file has been researched with a documented query log.
- ≥80% of entries have ≥2 independent non-DZSF sources and can flip `needs_review: false`.
- All unresolvable cases are escalated to the maintainer via `ESCALATIONS.md` with a clear keep/annotate/drop recommendation.
- Proposed vocabulary additions are triaged before any incident draft that uses them is merged.
- All five CI checks (`ruff`, `validate.py`, `pytest`, `build_release.py`, `frictionless`) pass on the final branch.

## Non-goals

- No schema changes or field additions.
- No retroactive re-run of `scripts/migrate_dzsf.py` — stubs are edited in place.
- No enrichment of incidents not yet in the repo (discovery of new incidents is out of scope).
- No translation of source quotes beyond what the subagent needs to extract facts.

## Decisions from brainstorming

| Question | Decision |
|---|---|
| Execution model | Hybrid: batch drafting into sidecar + bulk review |
| Scope | All 31 entries, including re-verifying the already-reviewed one |
| Research depth | Heavy (20+ searches, cross-check ≥3 sources where possible) |
| Low-evidence policy | Escalate to maintainer via `ESCALATIONS.md` |
| Staging | Sidecar directory `incidents/.drafts/` + `REVIEW.md` |
| Parallelism | Batched parallel subagents, 3–5 per batch |
| Vocabulary expansion | Auto-append with per-incident scratch files, serial post-batch merge |
| Source languages | English + German + native-language when it provides unique facts |
| Orchestration | Implementation plan + `superpowers:subagent-driven-development` |
| Contributor attribution | Append `"Lukas Iffländer"` to `contributors:` on significant enrichment only |
| Escalation circuit breaker | Pause if ≥10 of 31 incidents escalate |
| Commit cadence | Commit only at `final-review-handoff`, not per batch |
| Plan tracking | Per-task checkbox markers (`[ ] / [x]`) |
| Promotion helper | New `scripts/promote_drafts.py` script |

## Architecture

```
plans/2026-04-19-incident-enrichment.md     (plan file — source of truth for progress)
            │
            │  subagent-driven-development executes tasks in batches of 3–5
            ▼
┌───────────────────────────────────────────────────────────────┐
│  Per incident (parallel subagents within a batch):            │
│    1. Read incidents/<id>.yaml                                │
│    2. Heavy websearch (EN + DE + native when unique)          │
│    3. Cross-check ≥3 independent sources where possible       │
│    4. Produce:                                                 │
│       - incidents/.drafts/<id>.yaml          (proposed YAML)  │
│       - incidents/.drafts/<id>.log.md        (research log)   │
│       - incidents/.drafts/<id>.vocab.yaml    (vocab scratch)  │
│       - row in REVIEW.md                                       │
│       - section in VOCAB_PROPOSALS.md (if applicable)          │
│       - section in ESCALATIONS.md (if low-evidence)           │
└───────────────────────────────────────────────────────────────┘
            │
            │  post-batch serial vocab-merge task
            ▼
   vocabularies/*.yaml updated with `# PROPOSED` markers
            │
            │  final-review-handoff: commit branch, surface summary
            ▼
   Maintainer bulk review → scripts/promote_drafts.py → CI checks → merge
```

**Key properties:**

- Plan file is the single source of truth for progress; per-task state survives session restarts.
- `incidents/.drafts/` is gitignored and excluded from `scripts/validate.py` / `scripts/build_release.py` — drafts cannot break CI.
- `REVIEW.md` is append-only during enrichment; the maintainer reads it top-to-bottom to triage.
- Vocabulary additions merge before incident drafts (two-phase), so schema validation stays green at every intermediate state.

## Per-incident subagent protocol

**Inputs:** `incident_id`, current `incidents/<id>.yaml`, paths to `CODEBOOK.md`, `schema/incident.schema.json`, `vocabularies/*.yaml`. Hard rules: prefer `null` over invention, filename stem == id, absolute http(s) URLs, ISO 8601 dates, source-language policy.

**Steps:**

1. **Seed** — parse stub for hints (date, country, known malware/actor, DZSF origin).
2. **Search phase — 20+ queries across 5 rounds:**
   - Round 1: broad EN queries.
   - Round 2: narrow EN + CERT advisories (BSI, ENISA, CISA, NCSC, CERT-FR, CERT-Bund).
   - Round 3: German press (heise, Golem, Tagesschau, FAZ, SZ) + DZSF-adjacent academic references.
   - Round 4: native-language searches in the incident country's language — include only when they surface facts absent from EN/DE sources.
   - Round 5: cross-checks — MITRE ATT&CK IDs, malware Software IDs, Wikipedia, vendor threat reports (Mandiant, Kaspersky, ESET, Dragos, Claroty).
3. **Extract fields** — map findings to schema; record source URL(s) per field; null anything not attested by ≥1 credible source.
4. **Build `sources:` list** — every cited URL with `type`, `publisher`, `published_date`, `language`, `accessed_date: 2026-04-19`. Deduplicate.
5. **Vocabulary check** — unknown values go to `incidents/.drafts/<id>.vocab.yaml` (not directly into real vocab files) and to `VOCAB_PROPOSALS.md`.
6. **Self-validate** — re-run invariants from `scripts/validate.py` (filename==id, ISO dates, `event_date <= reported_date`, absolute URLs, enum membership including pending proposals).
7. **Set `needs_review`** — set `false` only if ≥2 independent non-DZSF sources corroborate the core facts. If the entry started `true` and the threshold is not met: keep `true` and escalate. If the entry started `false` (re-verification case) and the threshold is not met: keep `false` (do not regress), but escalate with a "prior review may be under-sourced" note so the maintainer can decide whether to demote.
8. **Bump `last_updated`** to `2026-04-19`.
9. **Append `"Lukas Iffländer"` to `contributors:`** — only when significant enrichment occurred. Pure escalations (no real findings) do not trigger the append.
10. **Write outputs** — draft YAML, log file, vocab scratch (if any), append to REVIEW/VOCAB_PROPOSALS/ESCALATIONS as applicable.
11. **Return summary** — short JSON-ish status (status, sources_found, fields_filled, vocab_proposed_count, escalated) so the orchestrator can update the plan without re-reading files.

**Thresholds:**

- "Significant enrichment" ≡ ≥1 new non-DZSF source added AND ≥3 fields moved off `null` or default.
- "Independent source" ≡ distinct publisher; syndicated wire reports count as one.

## Sidecar layout

```
incidents/
├── 2014-12-25_dzsf-import.yaml        (original, untouched during enrichment)
├── ... 30 more originals ...
└── .drafts/                            (gitignored; excluded from validate/build)
    ├── REVIEW.md                       (triage table)
    ├── VOCAB_PROPOSALS.md              (proposed vocabulary additions)
    ├── ESCALATIONS.md                  (low-evidence incidents needing maintainer decision)
    ├── 2014-12-25_dzsf-import.yaml     (proposed replacement)
    ├── 2014-12-25_dzsf-import.log.md   (research log)
    ├── 2014-12-25_dzsf-import.vocab.yaml (vocab scratch, if applicable)
    └── ... (per incident) ...
```

### `REVIEW.md` format

```markdown
# Incident enrichment review — 2026-04-19

| id | status | sources | fields filled | needs_review flipped | vocab proposed | escalated | draft path |
|---|---|---|---|---|---|---|---|
| 2014-12-25_dzsf-import | drafted | 3 | 7/25 | no | — | yes | .drafts/2014-12-25_dzsf-import.yaml |
| 2015-07-01_dzsf-import | drafted | 5 | 14/25 | yes | industry_sectors:freight_terminal | — | .drafts/2015-07-01_dzsf-import.yaml |
| 2017-05-13_wannacry | re-verified | 6 | 22/25 | no change | — | — | .drafts/2017-05-13_wannacry.yaml |
```

One row per incident; sortable/filterable by eye.

### `<id>.log.md` format

```markdown
# Research log: <id>

## Queries attempted
1. "China railway cyberattack 2014" (EN, websearch) — 2 relevant hits
2. "中国 铁路 网络攻击 2014" (ZH, native) — 0 relevant hits
... (all 20+ queries logged)

## Sources evaluated (accepted / rejected)
- ACCEPTED: https://reuters.com/... — primary reporting
- REJECTED: https://randomblog.com/... — unsourced rumor

## Field-by-field attribution
- event_date: 2014-12-25 — source [1]
- countries_impacted: [CN] — sources [1], [2]
- target_organization: null — no public attribution found
- ...

## Open questions / caveats
(anything the reviewer should notice)
```

### `VOCAB_PROPOSALS.md` format

```markdown
## Proposed: industry_sectors.freight_terminal
- Needed by: 2015-07-01_dzsf-import, 2020-10-28_ransomexx
- Justification: incident at a container/freight terminal, distinct from line-haul `freight`
- Source supporting the need: https://reuters.com/...
```

### `ESCALATIONS.md` format

Sorted by recommendation strength (strongest "drop" at top, strongest "keep" at bottom) so similar cases batch naturally.

```markdown
## 2014-12-25_dzsf-import — low evidence
- Searches attempted: 22 (see log)
- Independent sources found: 0 (only the DZSF reference)
- Subagent recommendation: keep with note, possibly drop
- Maintainer decision: [ ] keep / [ ] annotate / [ ] drop
```

## Vocabulary handling

**Concurrency safety:**

Subagents in the same batch may propose the same vocab value simultaneously, so they never edit `vocabularies/*.yaml` directly. Each subagent writes a per-incident scratch file `incidents/.drafts/<id>.vocab.yaml`. Between batches, a serial orchestrator-run task `postbatch-N-vocab-merge` consolidates the scratch files into real vocab files, appending each new value with a `# PROPOSED 2026-04-19, see VOCAB_PROPOSALS.md` comment and deduplicating.

Draft YAML self-validation (step 6) treats proposed values as valid when a matching `.vocab.yaml` exists for the draft's incident.

**Maintainer review:**

1. Read `VOCAB_PROPOSALS.md`; for each proposed value decide accept / rename / reject.
2. Edit `vocabularies/*.yaml`: strip `# PROPOSED` comments on accepted values; remove rejected values; rename in place for renames.
3. Fix draft YAMLs that referenced renamed/rejected values (sed or manual).
4. Commit vocab changes to child branch `enrich/vocab-2026-04` and merge into `enrich/incidents-2026-04` **before** promoting any incident drafts.

Per repo policy, adding a vocab value is a MINOR schema bump. Data `schema_version` const stays `"1.0"`; no migration needed.

## Escalation policy

**Trigger conditions:**

- Fewer than 2 independent non-DZSF sources after 20+ queries.
- Sources disagree on a core fact (date, country, target, what happened) and the subagent cannot resolve.
- Evidence suggests the incident may be misclassified (not a railway cyber incident).

**Subagent actions on escalation:**

- Append section to `ESCALATIONS.md` with searches attempted, sources found, specific gap/conflict, and a recommendation.
- Write draft YAML with partial findings (any attested fields filled, rest null) into `notes`; keep `needs_review: true`; bump `last_updated`.
- Do **not** append `"Lukas Iffländer"` to `contributors:` on pure escalations.

**Maintainer actions per escalation:**

- **keep** — accept draft as-is (still `needs_review: true`), merge with added notes.
- **annotate** — edit draft to add a fuller note ("researched, insufficient external sources"), optionally flip `needs_review: false`.
- **drop** — delete the draft and the original `incidents/<id>.yaml` (misclassification or unsupported rumor).

**Circuit breaker:** orchestrator pauses and asks the user if ≥10 of 31 incidents escalate. Prevents burning hours on a broken protocol.

## Progress tracking and resumability

**Plan file:** `plans/2026-04-19-incident-enrichment.md`, standard `superpowers:writing-plans` format. Each task uses checkbox markers (`[ ] / [x]`).

**Tasks:**

- 1 prep task: `prep-0-sidecar-setup`.
- 31 per-incident tasks.
- N post-batch vocab-merge tasks (one per batch).
- 1 final task: `final-review-handoff`.

**Per-incident task fields:**

- `status: pending | in_progress | drafted | escalated | failed`
- `draft_path`, `log_path` (written on completion)
- `return_summary` (JSON-ish blob from step 11)
- `attempt_count` (cap retries at 2)

**Resumability:**

- Orchestrator's first action in any session: read plan, find tasks with status ∈ {pending, failed (attempts<2)} and `in_progress` tasks lacking a draft file (treated as crashed, reset to `pending`, attempt_count incremented).
- Batches re-derived from current pending set; no lock files, no external state.

**Prep task (runs once, first):**

- Create `incidents/.drafts/`.
- Append `incidents/.drafts/` to `.gitignore`.
- Update `scripts/validate.py` and `scripts/build_release.py` to skip `.drafts/` (verify first — globbing `incidents/*.yaml` should already exclude hidden dirs).
- Seed `REVIEW.md`, `VOCAB_PROPOSALS.md`, `ESCALATIONS.md` with headers.
- Create branch `enrich/incidents-2026-04`.

**Post-batch task (runs after each batch):**

- Consolidate all scratch `.vocab.yaml` files into real `vocabularies/*.yaml`.
- Deduplicate across batches.
- Delete scratch files.
- Runs serially — never as a subagent.

**Final task:**

- Verify every non-escalated task has a draft file.
- Verify REVIEW.md counts match plan task statuses.
- Commit `REVIEW.md`, `VOCAB_PROPOSALS.md`, `ESCALATIONS.md`, and the updated plan on the enrichment branch.
- Print handoff summary: total drafts, escalations, vocab proposals, next steps.

**Circuit breakers:**

- ≥10 escalations → pause, ask user.
- Any task exceeds 2 failed attempts → mark `failed`, add to ESCALATIONS.md as "subagent repeatedly failed", continue with the rest.
- Orchestrator approaches its context limit → wrap current batch cleanly, ensure plan state is up to date in memory, suggest user restart for continuation.

## Merge workflow (drafts → real data)

**Maintainer bulk review pass (manual):**

1. Read `REVIEW.md` top-to-bottom.
2. Resolve `VOCAB_PROPOSALS.md` first; merge `enrich/vocab-2026-04` into the enrichment branch.
3. Resolve `ESCALATIONS.md` with keep/annotate/drop decisions, editing drafts or deleting as needed.
4. Spot-check a sample of drafts (e.g., every 5th) by reading `.yaml` and `.log.md` side-by-side.

**Promotion helper (`scripts/promote_drafts.py`, ~80 lines, new):**

- Reads `incidents/.drafts/*.yaml`.
- Moves each to `incidents/<id>.yaml` (overwriting the stub); leaves the `.log.md` in `.drafts/`.
- Flags: `--only <id>`, `--all`, `--exclude <id>`.
- Exits non-zero if a draft references a vocab value not yet merged into `vocabularies/*.yaml`.

**Post-promotion validation (must all pass):**

```bash
make lint
make validate
make test
make build
uv run frictionless validate dist/datapackage.json
```

**Commit structure on `enrich/incidents-2026-04`:**

1. `chore: set up incident enrichment sidecar`
2. `feat(vocab): add values from 2026-04 enrichment pass`
3. `feat: enrich <id>` — one commit per promoted incident (enables targeted revert).
4. `docs: archive enrichment review artefacts` (move `REVIEW.md` etc. to `docs/enrichment/2026-04/`; clean up drafts).

**Final merge to main:** preserve per-incident commits (don't squash) so `git blame` on `incidents/*.yaml` attributes facts to enrichment commits.

**Rollback:** each incident = one commit; `git revert <sha>` per incident. Pre-promotion abort is trivial (delete branch, delete `.drafts/`).

## Open risks

- **Session time budget:** 31 × 30–45 min heavy research is 15–23h wall clock even with parallelism. Resumability is essential. Mitigated by plan-file state.
- **Research quality variance:** heavy search on obscure CN/IR incidents may produce 0 usable sources while the subagent logs 22 queries. Mitigated by escalation policy and circuit breaker.
- **Vocab sprawl:** subagents proposing many one-off values. Mitigated by two-phase merge (maintainer reviews every proposal before incidents relying on it ship).
- **Source rot / URL death:** historical incidents may only be cited in now-dead URLs. Mitigated by recording `accessed_date` and preferring archived/official sources; Wayback Machine URLs acceptable when originals are dead.
- **Attribution hallucination:** subagents must not invent threat-actor attributions. Enforced by "prefer null over invention" and the per-field source-attribution record in the log.

## Out of scope for this spec

- The actual implementation plan (tasks, ordering, exact prompts) — produced next via `superpowers:writing-plans`.
- Schema changes.
- New incident discovery.
- Public release / DOI minting (follows normal release flow after merge).
