# Codex Instructions for This Medical LLM Wiki

This vault is a medical knowledge wiki maintained by Codex. Follow the LLM Wiki pattern:

- `raw/` contains immutable source material supplied by the user.
- `wiki/` contains Codex-generated markdown pages, summaries, indexes, syntheses, and query answers.
- `AGENTS.md` is the operating schema for future Codex sessions.

Codex may edit `wiki/`, `docs/`, and this file when maintaining the system. Do not edit `raw/` source files except to rename or move files when the user explicitly asks.

## Safety Scope

This is a study and knowledge-management vault, not a clinical decision system.

- Do not give personal diagnosis, treatment, dosing, or triage advice unless the user explicitly asks for general educational information, and still label it educational.
- Prefer source-grounded statements with citations to source summary pages.
- Preserve uncertainty. Mark conflicts, weak evidence, outdated claims, and jurisdiction-specific guidance.
- When sources disagree, do not silently merge them. Add a `Conflicts and updates` section to affected pages.
- For drug dosing, contraindications, pregnancy/lactation, pediatrics, renal/hepatic adjustment, and emergency care, require high-quality recent sources before making strong claims.
- If user asks for current clinical guidelines, drug labels, prices, availability, laws, or recommendations, verify with current official sources before answering.

## Directory Contract

```text
raw/
  books/       # PDFs, EPUBs, OCR text, chapter markdown, book-derived files
  articles/    # clipped articles, papers, guidelines, web pages
  notes/       # user notes, transcripts, lecture notes
  assets/      # local images and attachments

wiki/
  index.md     # content catalog, updated on every ingest/query/lint
  log.md       # append-only chronological activity log
  overview.md  # top-level map and synthesis
  sources/     # one page per source or chapter
  concepts/    # mechanisms, definitions, frameworks
  conditions/  # diseases and syndromes
  drugs/       # medications, classes, pharmacology
  anatomy/     # organs, structures, regions
  physiology/  # normal function and pathways
  diagnostics/ # tests, criteria, imaging, labs
  procedures/  # interventions, operations, clinical workflows
  guidelines/  # guideline comparisons and recommendations
  questions/   # filed answers from useful queries
  templates/   # page templates

docs/
  tools-and-skills.md
  maintenance-checklist.md
```

## Naming

Use lowercase kebab-case filenames:

- Source summary: `wiki/sources/<source-title-or-book-chapter>.md`
- Topic page: `wiki/conditions/heart-failure.md`, `wiki/drugs/metformin.md`
- Query answer: `wiki/questions/<question-slug>.md`

Use Obsidian links for internal pages: `[[heart-failure]]`, `[[metformin]]`.

## Page Metadata

Every Codex-generated wiki page should start with YAML frontmatter:

```yaml
---
type: concept
status: draft
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources:
  - "[[source-page]]"
tags:
  - medicine
---
```

Allowed `type` values:

- `overview`
- `source`
- `concept`
- `condition`
- `drug`
- `anatomy`
- `physiology`
- `diagnostic`
- `procedure`
- `guideline`
- `question`
- `index`
- `log`

Allowed `status` values:

- `draft`
- `reviewed`
- `needs-source`
- `conflict`
- `stale`

## Citation Style

Use source-page links rather than raw bibliographic sprawl inside topic pages.

Example:

```markdown
Loop diuretics reduce congestion in symptomatic heart failure, but do not provide the same mortality benefit as core disease-modifying therapy. Source: [[example-heart-failure-chapter]].
```

When exact page numbers or section labels are available, include them:

```markdown
Source: [[harrison-heart-failure-chapter]], section "Diuretic Therapy", p. 1842.
```

Never invent page numbers, DOI values, publication dates, or source metadata.

## Ingest Workflow

When the user asks to ingest a source:

1. Identify the source file in `raw/`.
2. Read the source. For long books, ingest by chapter or user-selected section.
3. Create or update one source summary in `wiki/sources/`.
4. Extract entities and topics: conditions, drugs, anatomy, physiology, diagnostics, procedures, guidelines.
5. Update relevant topic pages across `wiki/`.
6. Add cross-links between related pages.
7. Add contradictions, updates, and open questions where appropriate.
8. Update `wiki/index.md`.
9. Append one entry to `wiki/log.md`.

For each source summary include:

- Bibliographic metadata if present.
- Scope and reliability.
- Key claims.
- Clinical caveats.
- Topics/entities extracted.
- Links to affected wiki pages.
- Open questions or follow-up sources needed.

## Query Workflow

When answering questions:

1. Read `wiki/index.md` first.
2. Search the wiki with `rg` for key terms.
3. Read relevant pages before answering.
4. Synthesize with citations to wiki source/topic pages.
5. If the answer is durable and useful, ask whether to file it, or file it directly when the user asks.
6. If filed, create `wiki/questions/<slug>.md`, update `wiki/index.md`, and append to `wiki/log.md`.

## Lint Workflow

When the user asks to lint, audit, or health-check the wiki:

Check for:

- Contradictions between pages.
- Pages marked `needs-source`, `conflict`, or `stale`.
- Topic mentions that lack pages.
- Orphan pages with no inbound links.
- Source summaries not listed in `index.md`.
- Index entries pointing to missing files.
- Medical claims without source links.
- Old guideline claims needing current verification.

Write findings to chat unless user asks for a file. If a lint pass produces durable improvements, update the pages and append to `wiki/log.md`.

## Tool Preferences

- Use `rg` and `rg --files` for search.
- Use `apply_patch` for edits.
- Use Obsidian markdown links.
- Use local images from `raw/assets/` when relevant and available.
- For current medical guidelines, drug labels, or high-stakes recent claims, browse current official sources and cite them.

## Log Entry Format

Append entries to `wiki/log.md` using this parseable header:

```markdown
## [YYYY-MM-DD] ingest | Source Title
## [YYYY-MM-DD] query | Question Title
## [YYYY-MM-DD] lint | Scope
## [YYYY-MM-DD] maintenance | Change
```

Keep log append-only. Do not rewrite old log entries except to fix broken markdown when necessary.

