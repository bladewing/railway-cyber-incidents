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
