# Railway Cyber Incidents

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19646516.svg)](https://doi.org/10.5281/zenodo.19646516)

An open, machine-readable dataset of publicly reported cyber incidents against
railway systems worldwide. Intended as a citable research resource, with
structured data suitable for journalism and public-interest analysis.

**Latest release:** v0.1.0 (pending) · **Data license:** CC-BY 4.0 ·
**Code license:** MIT · **Living dataset — contributions welcome.**

## What's in the box

- `incidents/*.yaml` — one file per incident (the source of truth).
- `schema/incident.schema.json` — JSON Schema, validates every entry.
- `vocabularies/*.yaml` — controlled values for systems, vectors, sectors, etc.
- `dist/` *(generated, not checked in)* — flat CSV, long-format CSVs, JSONL,
  and a Frictionless Data Package.

## Quick start

### Load the data in Python

```python
import pandas as pd
df = pd.read_csv("dist/incidents.csv")
```

### Load all affected systems (long format)

```python
sys = pd.read_csv("dist/affected_systems.csv")
top = sys.groupby("system").size().sort_values(ascending=False)
```

### Validate the whole package

```bash
uvx frictionless validate dist/datapackage.json
```

## Contributing

Read `CONTRIBUTING.md` and copy `incidents/TEMPLATE.yaml`. Then open a PR.

## Discovering new incidents

`make discover` runs a two-stage pipeline that harvests candidates from
curated aggregators (konbriefing, EuRepoC, ENISA, BSI, ransomware.live)
and writes `needs_review: true` stubs to `incidents/drafts/`. Stage 1
(`scripts/fetch_candidates.py`) is deterministic Python; Stage 2
(`scripts/stub_candidates.py`) calls Haiku four times per candidate
(classify → dedup → extract → summarise) via the `claude` CLI subscription.
Stubs are ignored by `validate.py`/`build_release.py` until promoted.
Promotion path: enrich with `uv run python scripts/enrich.py <id>`, review
the filled YAML, then atomically move into `incidents/` via
`scripts/promote_drafts.py`.

## Field definitions

See `CODEBOOK.md`.

## Citation

See `CITATION.cff` — GitHub renders a "Cite this repository" button, and
Zenodo mints a DOI per tagged release.

## Schema evolution

- MINOR bumps: backward-compatible (new optional field, new vocab value).
- MAJOR bumps: breaking; a migration script ships with the release.

## Data provenance

v0.1.0 ports the corpus of DZSF project 2020-23-S-1202
("Identifikation bestehender Angriffspotentiale") published 2023. Imported
entries are marked `provenance.needs_review: true` until manually verified.

## Acknowledgements

Built on prior work in DZSF project 2020-23-S-1202 and the publication
"Cyberangriffe auf das Bahnsystem" (2023). Schema vocabulary inspired by
VERIS (Verizon) and the CISSM Cyber Events Database.

## Maintainer: connecting Zenodo

To mint a DOI per tagged release:

1. Sign in to <https://zenodo.org> with your GitHub account.
2. Open <https://zenodo.org/account/settings/github/>.
3. Toggle ON the switch next to this repository.
4. Push a tag matching `v*` (e.g. `git tag v0.1.0 && git push --tags`).
5. Zenodo archives the GitHub Release and returns a DOI. Paste the DOI into
   `CITATION.cff` under `identifiers` and commit.
