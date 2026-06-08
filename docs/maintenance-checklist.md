# Maintenance Checklist

Use this checklist when the user asks for a wiki lint, audit, or cleanup.

## Index Integrity

- Every page under `wiki/` is listed in `wiki/index.md` or a category index.
- Every source summary is listed in `wiki/sources/index.md`.
- Links in indexes point to existing pages.

## Source Grounding

- Medical claims link to source pages.
- Claims needing current verification are marked.
- Drug and guideline pages include publication/version dates when known.

## Cross-Linking

- Important mentioned topics have pages or are listed as open gaps.
- Related conditions, drugs, diagnostics, and mechanisms link to each other.
- Orphan pages are intentional or fixed.

## Contradictions

- Conflicts between sources are listed on affected pages.
- Superseded claims are marked `stale` or moved to `Conflicts and updates`.

## Log

- `wiki/log.md` has append-only entries.
- Each entry starts with `## [YYYY-MM-DD] type | Title`.

