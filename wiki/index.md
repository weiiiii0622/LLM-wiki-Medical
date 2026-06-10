---
type: index
status: draft
created: 2026-06-07
updated: 2026-06-09
sources: []
tags:
  - medicine
  - index
---

# Index

Content catalog for this medical LLM wiki. Update this file on every ingest, durable query, or maintenance pass.

## Query Citation Rule

- Use topic pages for retrieval only; they are not sources.
- Final answer sources must be raw chapter/page strings, for example `醫(六)第4冊麻醉耳鼻喉_第一篇、麻醉科_戊、靜脈麻醉劑 Page 59-72`.
- Do not cite `[[drugs/...]]`, `[[conditions/...]]`, `[[anatomy/...]]`, `[[diagnostics/...]]`, `[[procedures/...]]`, `[[guidelines/...]]`, `[[physiology/...]]`, or `[[concepts/...]]` as sources.
- Remote Hermes deployments may not have `raw/`; do not search `raw/books/md` to answer queries. Use raw citation strings already present in topic pages after `Source:` or `canonical_citation` in `wiki/sources/*`.

## Core Pages

- [[overview]] - Top-level map and current synthesis of the vault.
- [[log]] - Append-only chronology of ingests, queries, lints, and maintenance.

## Sources

- [[sources/index]] - Source summaries catalog. Latest ingest: `醫(六)第4冊麻醉耳鼻喉`.

## Topic Categories

- [[conditions/index|Conditions]] - 1020 topic pages
- [[drugs/index|Drugs]] - 145 topic pages
- [[diagnostics/index|Diagnostics]] - 144 topic pages
- [[procedures/index|Procedures]] - 183 topic pages
- [[guidelines/index|Guidelines]] - 24 topic pages
- [[physiology/index|Physiology]] - 37 topic pages
- [[anatomy/index|Anatomy]] - 44 topic pages
- [[concepts/index|Concepts]] - 38 topic pages

## Questions

- [[questions/index]] - Durable answers filed from useful queries.

## Maintenance Notes

- Latest textbook ingested topic-first on 2026-06-09: `醫(六)第4冊麻醉耳鼻喉`.
- Topic nodes are organized by medical entity or concept, not chapter title. Source chapter pages remain only as citation anchors.
