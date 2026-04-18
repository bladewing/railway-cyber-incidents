# Contributing

Thanks for wanting to improve this dataset. Every entry is reviewed both
automatically (JSON Schema) and manually (factual accuracy).

## Adding a new incident

1. **Fork and clone** this repository.
2. **Copy the template:**
   ```bash
   cp incidents/TEMPLATE.yaml incidents/YYYY-MM-DD_slug.yaml
   ```
   Choose `YYYY-MM-DD` as the `event_date` and a short, lowercase `slug`.
3. **Fill in the fields** guided by `CODEBOOK.md`.
   - Required: `id`, `schema_version`, `event_date`, `event_date_precision`,
     `countries_impacted`, `confirmation_status`, `description_en`,
     `sources` (≥1), `last_updated`.
   - **When in doubt, leave a field `null`.** Do not invent values.
   - Add at least one source. CERT advisories, official statements, and
     technical reports are strongly preferred over news aggregators.
4. **Validate locally:**
   ```bash
   make validate
   ```
5. **Open a pull request** with a short summary of the incident and why the
   sources are trustworthy.

## Reviewing incidents marked `needs_review: true`

Entries imported in bulk (e.g. from the original DZSF corpus) carry
`provenance.needs_review: true`. To promote such an entry to a regular record:

1. Read the narrative description in the DZSF reports and any public sources.
2. Fill in `target_organization`, `description_en` (and optionally
   `description_de`), `impact.*`, and any other fields you can support with
   sources.
3. Add the source URLs to `sources`.
4. Set `provenance.needs_review: false`.
5. Bump `last_updated`.
6. Open a PR.

## Updating the schema or vocabularies

Non-breaking changes (new optional field, new vocab value) bump the MINOR
version. Breaking changes bump MAJOR and require a migration script for all
existing incidents. Open an issue first.

## Commit messages

We follow conventional-commits loosely:
- `feat:` new incident, new field, new script
- `fix:` correction to existing incident or tooling
- `docs:` README/codebook/contributor docs
- `test:` test additions
- `chore:` tooling

## Running tests

```bash
make install   # once
make test
```
