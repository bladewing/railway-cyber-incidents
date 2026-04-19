# Incident discovery pipeline — design

- **Status:** draft, pending maintainer review
- **Date:** 2026-04-19
- **Author:** Lukas Iffländer (with Claude Code)
- **Related:** `docs/superpowers/specs/2026-04-19-incident-enrichment-design.md`
  (existing enrichment flow this pipeline feeds into)

## Problem

The dataset has 30 incidents; the most recent is from 2021. There is a
~4-year coverage gap (2022–2026) plus pre-2022 incidents that were simply
missed. We need a way to find new railway cyber incidents and prepare them
for inclusion with **acceptable accuracy and minimal token cost**, using
Haiku-class models where possible and deterministic parsing where LLMs
add no value.

## Non-goals

- Not an auto-enrichment tool. Filling vocabulary-controlled fields
  (`attack_vector`, `motive`, `affected_systems`, …), impact magnitudes,
  and threat-actor attribution remains the job of the existing enrichment
  subagent flow (v0.2.0). Discovery produces stubs; enrichment fills
  nulls.
- Not a continuous / scheduled service. One-shot backfill over the full
  history first; an ongoing cron is a separate project once this one has
  been proven.
- Not a general-purpose news crawler. Curated aggregators only in v1;
  broad news-search fallback is opt-in via flag.

## Scope

**In**:

- Backfill of the entire history (pre-2022 gaps + the 2022–2026 gap).
- Curated aggregator adapters: konbriefing, EuRepoC, ENISA Transport
  Threat Landscape, ransomware.live, BSI Lagebericht.
- Optional GDELT / news-search fallback gated behind a `--gap` flag.
- Dedup against `incidents/*.yaml` (deterministic + Haiku tiebreak).
- Writing stubs to `incidents/drafts/` with `needs_review: true`.
- Cost reporting per run.
- `scripts/enrich.py` — thin wrapper that dispatches the existing
  v0.2.0 enrichment subagent flow on a single incident id.

**Out**:

- Continuous scheduling / cron.
- Auto-filling vocabulary-controlled fields (handled by enrichment).
- Writing directly to `incidents/` (all output goes through the review
  workflow and `scripts/promote_drafts.py`).

## Architecture

```
                   ┌──────────────────────────┐
                   │  aggregators.yaml (new)  │   checked-in curated source list
                   │  - konbriefing           │
                   │  - EuRepoC               │
                   │  - ENISA transport PDFs  │
                   │  - ransomware.live       │
                   │  - BSI Lagebericht PDFs  │
                   └────────────┬─────────────┘
                                │
                                ▼
           scripts/fetch_candidates.py        Stage 1 — no LLM
           ┌───────────────────────────────┐
           │ httpx + BeautifulSoup + pypdf │
           │ per-source adapter            │
           │ -> list[Candidate]            │
           └────────────┬──────────────────┘
                        │
                        ▼
            dist/candidates.json            reviewable, re-runnable
                        │
                        ▼
            scripts/stub_candidates.py       Stage 2 — Haiku only
           ┌───────────────────────────────┐
           │ 1. classify  (rail∧cyber?)    │
           │ 2. dedup     (determ+Haiku)   │
           │ 3. extract   (date/country)   │
           │ 4. summarise (description_en) │
           └────────────┬──────────────────┘
                        │
                        ▼
             incidents/drafts/*.yaml         needs_review: true stubs
                        │
                        ▼
              (optional) existing enrichment subagent flow
                        │
                        ▼
              scripts/promote_drafts.py → incidents/
```

Stage 1 is deterministic and re-runnable offline. Stage 2 is idempotent
on the same `candidates.json` (`temperature=0` via `claude -p --model
haiku`).

## LLM transport

All LLM calls use the installed `claude` CLI via subprocess:

```python
subprocess.run(
    ["claude", "-p", prompt, "--model", "haiku", "--output-format", "json"],
    capture_output=True, check=True, timeout=60,
)
```

The CLI uses the user's existing `claude login` session — i.e. the
Claude Code subscription, not an API key. Output JSON includes `result`,
`usage`, and `total_cost_usd`, which the pipeline sums for the run bill.

No Anthropic SDK dependency is added.

## Aggregators (v1 list)

`aggregators.yaml` (new, checked in, editable by non-dev contributors):

| id             | kind  | source                                                          | notes                                   |
|----------------|-------|-----------------------------------------------------------------|-----------------------------------------|
| konbriefing    | html  | `konbriefing.com/en-topics/cyber-attacks.html`                  | generic listing, rail-filtered in adapter (dedicated railway page retired) |
| eurepoc        | csv   | Zenodo Global Dataset CSV, rail-filtered in adapter             | EU-centric; CC-BY-NC-4.0 (academic use) |
| enisa_transport| pdf   | annual Transport Threat Landscape PDFs                          | text-extract via `pypdf` + rail keywords|
| ransomware_live| json  | `api.ransomware.live/v2/recentvictims` (IPv4-forced in adapter) | filter victim names with rail keywords  |
| bsi_lagebericht| pdf   | BSI annual Lagebericht PDFs                                     | German rail keywords                    |

**Rail keyword list** (one file, reused everywhere): `rail`, `railway`,
`railroad`, `train`, `metro`, `subway`, `tram`, `transit`, plus operator
names (DB Schenker, Deutsche Bahn, SNCF, Trenitalia, ÖBB, NS, Amtrak,
ProRail, …). Editable YAML under `vocabularies/rail_keywords.yaml`
(fits the existing `vocabularies/` convention; not a controlled enum,
but an aggregator filter list).

Each adapter is isolated: one aggregator failing (site down, PDF layout
change) logs a warning and the run continues with the others.

## Candidate shape (`dist/candidates.json`)

```json
{
  "url": "https://...",
  "title": "...",
  "raw_date": "2023-08-14",
  "source_id": "konbriefing",
  "source_type": "news",
  "lang": "en",
  "excerpt": "first 500 chars of article text if obtainable",
  "discovered_at": "2026-04-19"
}
```

`source_type` maps to the existing `vocabularies/source_types.yaml`
values (`news`, `advisory`, `vendor_report`, …); adapter-level mapping
keeps the value correct without an LLM call.

## Stage 2 passes

Each pass is a separate `claude -p` subprocess call with a small prompt
and JSON output. All at `--model haiku`, `temperature=0`.

### Pass 1 — Classify (rail ∧ cyber?)

- Input: `title` + `excerpt` only. No full article fetch yet.
- Output: `{"is_rail_cyber": bool, "confidence": 0-1, "reason": "≤20 words"}`.
- Drop if `is_rail_cyber=false` OR `confidence<0.6`.
- Expected kill rate: 60–80% of noisy sources.

### Pass 2 — Dedup

Deterministic first, Haiku only on ambiguity:

- **Exact drop**: candidate URL already appears in any `sources[].url`
  of an existing `incidents/*.yaml`.
- **Ambiguous** (triggers Haiku): `|candidate.event_date − existing.event_date| ≤ 7
  days` AND Jaccard similarity ≥ 0.5 between the lowercased
  whitespace-split token sets of `candidate.title` and
  `existing.target_organization ?? existing.description_en`.
- **Haiku prompt**: candidate + the 1–3 possibly-matching existing
  incidents (id + description_en + sources) → `{"duplicate_of":
  "<id>"|null, "reason": "≤20 words"}`.
- If `duplicate_of` set → log and drop.

### Pass 3 — Extract fields

- Only now fetch full article text (httpx, 10s timeout, one retry).
- Prompt output schema:
  ```json
  {
    "event_date": "YYYY-MM-DD|null",
    "event_date_precision": "day|month|year",
    "countries_impacted": ["DE", ...],
    "target_organization": "string|null",
    "reported_date": "YYYY-MM-DD|null"
  }
  ```
- Fail-open on extract errors: write what we got, leave rest `null`.

### Pass 4 — English description

- Prompt: "Write 1–3 sentences in English describing what happened.
  Neutral tone, no speculation, no adjectives. Facts only. ≤80 words."
- If source is DE/FR/other, this pass doubles as translation.

### Token budget (Haiku 4.5 pricing, estimate)

| pass | input | output | share of candidates |
|------|-------|--------|---------------------|
| 1    | ~300  | ~30    | all                 |
| 2    | ~500–1500 | ~40 | ~5% (ambiguous only) |
| 3    | ~2000–4000 | ~100 | survivors of Pass 1 |
| 4    | ~2000–4000 | ~100 | survivors of Pass 1 |

Budget: **~$0.001–0.003 per surviving candidate**. Dead candidates cost
only Pass 1. Full backfill with ~300 candidates → <$1 expected.

Prompt caching: system prompt and rail keyword list are identical across
calls within a run, so `claude -p` serves cached prefixes automatically.

## Stub shape

Filename: `incidents/drafts/<event_date>_<slug>.yaml`. `slug` is a
lowercased, de-umlauted, `-`-joined short form of `target_organization`,
falling back to `<source_id>-<4-char-hash-of-url>`. Filename stem equals
`id` — validator invariant preserved.

```yaml
id: 2023-08-14_db-schenker
schema_version: "1.0"
event_date: 2023-08-14
event_date_precision: day
reported_date: null
countries_impacted: [DE]
target_organization: DB Schenker
confirmation_status: reported
description_en: >
  Short English summary here.
sources:
  - url: https://konbriefing.com/...
    type: news
    publisher: null
    published_date: null
    language: en
    accessed_date: 2026-04-19
provenance:
  needs_review: true
  discovered_by: discover_incidents
  aggregator: konbriefing
  haiku_classify_confidence: 0.82
contributors:
  - "discover_incidents"
last_updated: 2026-04-19
```

**Kept `null` (humans / enrichment fill later)**: `region`,
`coordinates`, `industry_sector`, `operator_type`, `attack_vector`,
`supply_chain`, `malware`, `extortion`, `motive`,
`mitre_attack_techniques`, `threat_actor`, `threat_actor_country`,
`attribution_confidence`, `affected_systems`, `data_published`,
entire `impact.*` tree (including `impact.scope`), `description_de`.

If the source article is in German, swap: original-language text goes to
`description_de`, Pass 4 translation goes to `description_en`.

### Schema bump

`provenance.needs_review` is already used by the DZSF import. The three
new keys — `provenance.discovered_by`, `provenance.aggregator`,
`provenance.haiku_classify_confidence` — are added as **optional** fields
under `provenance` in a MINOR schema bump at the start of implementation.
No migration needed for existing incidents (additive).

## Directory conventions

- `incidents/drafts/` — **committed**. Discovery stubs shared across
  contributors. Excluded from `scripts/validate.py` and
  `scripts/build_release.py` globs (existing non-recursive glob already
  covers this; regression test locks it in).
- `incidents/.drafts/` — **gitignored** (unchanged). Transient workspace
  for the existing enrichment subagent flow.
- `dist/candidates.json` — build artefact, gitignored via existing
  `dist/` rule.
- `dist/.discover-cost.log` — running cost log, gitignored.

## Operator workflow

```
$ make discover
  → fetch_candidates.py (Stage 1, ~30s, no LLM)
  → dist/candidates.json
  → stub_candidates.py (Stage 2, Haiku per-candidate)
  → incidents/drafts/*.yaml
  → report:
      fetched: 412
      classified rail+cyber: 38
      dedup dropped: 7
      stubs written: 31
      tokens used: 142k  (est $0.04)
      almost-passed sample: [url, url, url]

$ git status incidents/drafts/
  → 31 new files

$ $EDITOR incidents/drafts/2023-08-14_db-schenker.yaml
  → maintainer scans; `rm` false positives; keep the rest

$ git add incidents/drafts/ && git commit -m "chore: discovery stubs 2026-04-19"
```

Per-stub enrichment (optional, uses existing v0.2.0 flow):

```
$ uv run scripts/enrich.py 2023-08-14_db-schenker    # thin wrapper (new)
  → dispatches existing enrichment subagent on that id
  → writes incidents/.drafts/<id>.yaml + log + vocab proposals

$ uv run scripts/promote_drafts.py 2023-08-14_db-schenker
  → atomic validate-all + move-all (existing tool)
  → stub moves from incidents/drafts/ to incidents/
```

Makefile targets:

```make
discover:         ## Full discover: fetch + stub
	uv run scripts/fetch_candidates.py
	uv run scripts/stub_candidates.py

discover-fetch:   ## Stage 1 only — refresh candidates.json
	uv run scripts/fetch_candidates.py

discover-stub:    ## Stage 2 only — re-run LLM on existing candidates.json
	uv run scripts/stub_candidates.py
```

The split lets prompt iteration happen without re-hammering aggregators.

## Cost dashboard

Every `claude -p` call returns `total_cost_usd`. `stub_candidates.py`
sums these, prints a per-run bill, and appends to
`dist/.discover-cost.log`. A `--max-cost 1.00` flag warns and halts if
a run crosses the ceiling — tripwire against a runaway prompt bug.

## Fallback (news search, opt-in)

`scripts/fetch_candidates.py --gap 2024-01:2024-12` runs GDELT / news
search only, scoped to a date window. Only used when curated aggregator
coverage looks thin for a specific window. Not wired into the default
`make discover` target.

## Testing strategy

All test layers are offline; no live LLM or network calls in CI.

1. **Adapter parsing** — committed fixtures under `tests/discover/fixtures/`
   (sample HTML, JSON, PDFs). One test per adapter: fixture in, expected
   `Candidate` list out. Catches silent aggregator layout changes.
2. **Dedup logic** — unit tests for exact URL hit, ambiguous near-date
   same-org, and pass-through cases. Fixture incidents under
   `tests/discover/fixtures/incidents/`.
3. **Stub writer** — monkeypatch the `claude -p` subprocess to return
   canned JSON. Assert written YAML: filename stem = id, enums null,
   `needs_review: true`, ISO dates, absolute source URL. Run real
   `scripts/validate.py` against the output directory.
4. **Validator compatibility** — regression test: broken YAML in
   `incidents/drafts/` must not fail `scripts/validate.py`. Same for
   `scripts/build_release.py` (drafts must not appear in `dist/*.csv`).
5. **Prompt snapshot** — load each prompt template, substitute a fixture
   candidate, snapshot exact text. Prompt edits force a deliberate
   snapshot update. Zero LLM calls.

**Deliberately out of scope**: live `claude -p` integration tests and
live-aggregator fetch tests. Fixtures cover what we need, keep CI fast.

## Dependencies to add

- `httpx` (if not present) — async-capable, better than `requests` for
  adapter isolation.
- `beautifulsoup4` — HTML parsing.
- `pypdf` — PDF text extraction for ENISA and BSI.
- No LLM SDK.

Check `pyproject.toml` before adding; some may already be vendored.

## Risks and mitigations

| risk | mitigation |
|------|------------|
| Aggregator HTML changes silently break an adapter | Fixture-based tests; per-adapter isolation so one failure doesn't kill the run. |
| Haiku classifier false-positives flood drafts dir | Confidence floor 0.6; per-run report prints top "almost passed" for sanity; `needs_review: true` means nothing leaks into `incidents/` without human review. |
| Haiku hallucinates `event_date` / country | Prefer-null prompt; enrichment flow re-checks on promotion; `confirmation_status` hard-coded to `reported` for stubs. |
| `claude` CLI auth not available | Clear error message pointing to `claude login`; the CI suite has no live LLM calls, so CI is unaffected. |
| Prompt drift over time | Prompt-snapshot tests force deliberate updates. |
| Runaway token spend | Per-call cost returned by `claude -p`; summed per run; `--max-cost` halt flag. |

## Resolved decisions

1. `provenance.discovered_by` / `provenance.aggregator` /
   `provenance.haiku_classify_confidence` → added as optional fields in
   a MINOR schema bump at the start of implementation.
2. Rail keyword list lives at `vocabularies/rail_keywords.yaml`, not
   under a new `config/` directory.
3. `scripts/enrich.py` (thin wrapper around the existing enrichment
   subagent flow) is in scope for this pipeline's first implementation.

## Success criteria

- `make discover` completes in under 5 minutes on the full backfill.
- <$2 total LLM spend for the full backfill.
- ≥80% of the stubs produced are genuine railway cyber incidents (by
  maintainer spot-check of a random 20-stub sample).
- No duplicates vs the existing 30 incidents.
- All existing tests (`ruff`, `validate`, `pytest`, `build`,
  `frictionless`) stay green.
