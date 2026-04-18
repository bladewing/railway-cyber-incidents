# Codebook

This document defines every field in the incident schema.
Controlled vocabularies live in `vocabularies/` and are enforced by `schema/incident.schema.json`.

## Identity

- **`id`** — stable identifier; equals the filename stem. Format: `YYYY-MM-DD_slug`, slug lowercased, words separated by `-`.
- **`schema_version`** — current version: `"1.0"`. See `README.md` for the evolution policy.

## Dates

- **`event_date`** — ISO 8601 date (`YYYY-MM-DD`). Always a full date; when precision is coarser, day and/or month are `01` placeholders.
- **`event_date_precision`** — `day` | `month` | `year`. Respect this, not the literal placeholder day.
- **`reported_date`** — when the incident was first publicly reported. May be `null`.

## Geography

- **`countries_impacted`** — non-empty list of ISO 3166-1 alpha-2 codes. Use `UN` for unknown in a list context only; prefer `null` in single-value fields.
- **`region`** — free text (e.g., state, city, region name).
- **`coordinates`** — `{lat, lon}` or `null`.

## Victim

- **`target_organization`** — name of the affected entity; `null` if not publicly known.
- **`industry_sector`** — one value from `vocabularies/industry_sectors.yaml`.
- **`operator_type`** — one value from `vocabularies/operator_types.yaml`.

## Attack

- **`attack_vector`** — one value from `vocabularies/attack_vectors.yaml`.
- **`supply_chain`** — boolean; `null` if unknown.
- **`malware`** — list of objects `{name, family, mitre_software_id}`. `mitre_software_id` matches `/^S\d{4}$/`.
- **`extortion`** — boolean.
- **`motive`** — one value from `vocabularies/motives.yaml`.
- **`mitre_attack_techniques`** — list of MITRE ATT&CK technique IDs (`T1486`, `T1059.003`).

## Actor

- **`threat_actor`** — group or actor name; `null` if unknown.
- **`threat_actor_country`** — ISO 3166-1 alpha-2; `null` if unknown.
- **`attribution_confidence`** — one value from `vocabularies/confidence_levels.yaml`.

## Verification

- **`confirmation_status`** — **required**. How well-supported is the claim that the incident happened at all?
  - `confirmed`: affected organisation, investigating authority, or court has confirmed.
  - `reported`: primary source (CERT advisory, official statement, technical report).
  - `suspected`: circumstantial evidence only.
  - `rumored`: alleged, no strong source — include only if historically important.

## Affected Systems

Multi-select from `vocabularies/affected_systems.yaml`. Include a value if *any* reasonable source describes the system as affected.

## Data Disclosure

- **`data_published`** — were exfiltrated data publicly leaked?

## Impact

All subfields optional and nullable. Leave `null` when unknown — do not invent values.

- **`impact.scope`** — `local | regional | national | international | unknown`.
- **`impact.duration_hours`** — integer hours. Multi-day values are fine (72 = 3 days).
- **`impact.magnitude.affected_trains`**, **`.affected_passengers`**, **`.monetary_damage_eur`** — integers or `null`.
- **`impact.data_compromise.intellectual_property` / `.organizational_data` / `.customer_data`** — booleans.

## Description

- **`description_en`** — **required**, 1–3 sentences.
- **`description_de`** — optional German description.

## Sources

List of `{url, type, publisher, published_date, language, accessed_date}`. At least one source is required.
- `type` ∈ `vocabularies/source_types.yaml`.
- `language` is ISO 639-1 (e.g., `de`, `en`).
- `accessed_date` documents when the maintainer last confirmed the URL worked.

## Provenance

- **`contributors`** — list of names/handles of the maintainers who added or edited the entry.
- **`last_updated`** — date of the most recent edit.
- **`notes`** — free-text caveats.
- **`provenance`** — lineage metadata for bulk imports. `origin` identifies the originating project; `imported_from` names the source artefact; `needs_review: true` marks entries that have not yet been manually verified.
