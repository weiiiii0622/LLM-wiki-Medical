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

Use raw-source citations in claim text and final answers. Topic pages are retrieval/synthesis nodes, not primary sources.

Each `wiki/sources/*.md` page should carry canonical raw provenance fields:

```yaml
raw_source_title: "醫(三)第3冊腎內感染_第一篇、腎臟內科_辛、多囊性腎病"
raw_source_file: "raw/books/md/醫(三)第3冊腎內感染/醫(三)第3冊腎內感染_第一篇、腎臟內科_辛、多囊性腎病.md"
page_start: 133
page_end: 138
canonical_citation: "醫(三)第3冊腎內感染_第一篇、腎臟內科_辛、多囊性腎病 Page 133-138"
```

Topic-page frontmatter and `Source Coverage` may keep `[[sources/...]]` links for graph and audit purposes, but these are internal anchors only. Do not present `[[conditions/...]]`, `[[anatomy/...]]`, `[[concepts/...]]`, or other LLM-generated topic pages as sources in final answers.

Example:

```markdown
ADPKD 多為 autosomal dominant，並可合併高血壓、肝囊腫與腎功能下降。 Source: 醫(三)第3冊腎內感染_第一篇、腎臟內科_辛、多囊性腎病 Page 133-134.
```

If page markers are absent, use `Page unknown` and mark the affected source page `needs-source` until provenance can be improved.

Never invent page numbers, DOI values, publication dates, or source metadata. Use `tools/update_raw_citations.py` after ingest or citation-policy changes to refresh canonical source fields and topic-page citation tails.

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

### Textbook Ingest Requirements

For chapter-split medical textbooks under `raw/books/md/`, use a topic-first graph workflow:

- Ingest the chapter-split markdown files; ignore the full-book markdown unless the user explicitly asks for it.
- Do not use chapter titles as the main knowledge graph nodes. Chapter pages belong in `wiki/sources/` only as citation anchors.
- Make or update nodes for concrete medical knowledge: diseases/syndromes, treatments, drugs/classes, diagnostics/tests/criteria, procedures/workflows, guidelines, physiology, anatomy, and other specific high-yield concepts.
- Avoid abstract or overly broad nodes. Prefer `liver-cirrhosis`, `child-pugh-score`, `metformin`, and `upper-endoscopy` over vague titles like `clinical`, `treatment`, `diagnosis`, or `other`.
- Control graph size. Create a new topic node only when it represents a distinct concrete entity or workflow not already covered.
- Maintain overlap by updating existing nodes rather than creating duplicates. Add new source coverage and source-grounded details to the existing page.
- Keep each topic page as independent as practical: summary, source coverage, key source details, clinical caveats, related pages, and follow-up should make sense without reading the chapter page first.
- Body content should be Mandarin-first. Use English for specialized medical terms, with Mandarin translation when available, especially in titles and aliases.
- Keep `wiki/sources/index.md`, category indexes, `wiki/index.md`, and `wiki/overview.md` cumulative across books.
- After each textbook, run a health check for missing links and source/index consistency, write a health-check file under `docs/`, then commit with a message naming the ingested book, e.g. `Ingest 醫(三)第2冊肝內新陳代謝`.
- If the user asks to wait for approval after a book, stop after the health check and commit.

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
4. Synthesize from topic pages, then resolve their `sources:` entries to raw chapter/page citations via `wiki/sources/*` `canonical_citation`.
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
