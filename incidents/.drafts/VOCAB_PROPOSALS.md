# Proposed vocabulary additions — 2026-04-19

Consolidated list of vocabulary values proposed by enrichment subagents.
Maintainer triages: accept (keep), rename, or reject before incident drafts
referencing the value are promoted to `incidents/`.

Proposals are appended in the order batches complete. Duplicates across
batches are deduplicated by the post-batch vocab-merge step.

## Proposed: attack_vectors.ddos

- **Surfaced by:** 2025-07-24_transdev-hannover-s-bahn-hannover
- **Also useful for:** 2025-07-09_transdev-hannover-s-bahn-hannover, 2023-09-20_elron, 2024-01-18_nmbs-sncb, 2025-01-27_metronom, 2023-07-05_rzd, 2025-04-01_rzd, 2024-05-07_wmata, 2022-04-18_ceske-drahy (all website-only availability attacks currently coded as `attack_vector: unknown` with `mitre_attack_techniques: [T1498]`)

### Problem
The 24 July 2025 and 9 July 2025 S-Bahn Hannover incidents are reported across ≥10 German outlets as "Überlastungs-Attacken" / DDoS attacks against the public website. The DSGVO-Portal Sicherheitsvorfalls-Datenbank classifies the event explicitly as "DDoS-Angriff: Transdev Hannover". The project's `attack_vectors` vocabulary currently offers: `exploit`, `phishing`, `supply_chain`, `insider`, `physical`, `credential_theft`, `unknown`. None fits a volumetric availability attack. Forcing `unknown` loses information consistent across multiple independent sources.

### Proposal
Add one value to `vocabularies/attack_vectors.yaml`:
```yaml
- id: ddos
  label: Distributed denial-of-service / availability attack
```

### Rationale
- Pure availability attacks against public-facing web infrastructure are a recurring pattern in this corpus.
- Distinguishing DDoS from `unknown` improves downstream analytics (e.g. filtering hacktivist availability ops from intrusion-based events).
- Term is well understood in both German ("DDoS", "Überlastungs-Attacke") and English reporting.

### Scope
Non-blocking for current drafts — subagents kept `attack_vector: unknown` and noted the DDoS mechanism in descriptions/notes + `mitre_attack_techniques: [T1498]`. Adoption would allow a follow-up pass to set `attack_vector: ddos` for ~8 entries.

### Maintainer action
- [x] Accept and add `ddos` to `vocabularies/attack_vectors.yaml` — merged 2026-04-23
- [ ] Reject (keep `unknown`)
- [ ] Defer pending broader vocab review

### Follow-up
Nine enrichment drafts updated to `attack_vector: ddos` (were `unknown` + `T1498`):
2022-04-18_ceske-drahy, 2023-07-05_rzd, 2023-09-20_elron, 2024-01-18_nmbs-sncb,
2024-05-07_wmata, 2025-01-27_metronom, 2025-04-01_rzd,
2025-07-09_transdev-hannover-s-bahn-hannover,
2025-07-24_transdev-hannover-s-bahn-hannover.

Live (main-branch) incidents with `attack_vector: unknown` + `T1498` should be
updated in a separate follow-up pass — out of scope for this enrichment PR.
