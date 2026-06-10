# Tools and Skills for Future Codex Sessions

This vault uses plain markdown plus Obsidian. `tools/ingest_topic_book.py` is the reusable deterministic ingest helper for chapter-split textbooks.
Use `tools/update_raw_citations.py` whenever source pages or topic citations need to resolve to raw chapter/page provenance.

## Required Habits

- Read `AGENTS.md` before maintaining the wiki.
- Read `wiki/index.md` before answering questions.
- Use `rg` and `rg --files` to search.
- Use `apply_patch` for edits.
- Keep `raw/` immutable.
- Update `wiki/index.md` and append `wiki/log.md` after every ingest or durable query.
- Final answer sources must cite raw source chapters with page ranges, not LLM-generated topic pages.

## Obsidian Setup

Recommended Obsidian settings:

- Set attachment folder path to `raw/assets/`.
- Use Obsidian Web Clipper for articles and guidelines.
- After clipping web pages with images, download attachments locally into `raw/assets/`.
- Use graph view to inspect orphan pages and clusters.

Useful optional Obsidian plugins:

- Dataview: dynamic tables from frontmatter.
- Marp: slide decks from markdown.

## Optional Search Tool

At small scale, `wiki/index.md` plus `rg` is enough.

At larger scale, consider adding a local markdown search tool such as `qmd` for BM25/vector search over `wiki/`. If added, document install and query commands here.

## Medical Source Priorities

For high-stakes or current claims, prefer:

- Official guideline organizations.
- Drug labels and regulator pages.
- Recent systematic reviews and high-quality textbooks.
- Primary studies when needed for mechanism or evidence details.

Do not treat old notes or unsourced summaries as final authority.

## Query Citation Policy

Read `docs/query-citation-policy.md` before building query-answer behavior for Codex, Hermes, or other agents.

Short rule:

- Use topic pages for retrieval and synthesis.
- Use `wiki/sources/*` `canonical_citation` fields for final answer source lists.
- Do not cite `[[conditions/...]]`, `[[anatomy/...]]`, `[[concepts/...]]`, or other topic nodes as sources.
- If a topic page says `Source: 醫(三)... Page 133-138`, cite that raw chapter/page text directly.

Refresh raw citations after ingest or source edits:

```bash
python3 tools/update_raw_citations.py --dry-run
python3 tools/update_raw_citations.py
```

## Textbook Ingest Tool

Use this when a textbook folder under `raw/books/md/` contains one full-book markdown file plus chapter-split markdown files.

```bash
python3 tools/ingest_topic_book.py '醫(三)第1冊心胸內' --book-key med3-book1
```

For the next books, choose a stable `--book-key` such as `med3-book3`, `med3-book4`, `med4-book1`, etc. The source page slugs should stay stable after commit.

What it does:

- Reads only chapter-split `.md` files and ignores the full-book `.md`.
- Creates one source summary per chapter under `wiki/sources/`.
- Creates topic-first nodes under `wiki/conditions/`, `wiki/drugs/`, `wiki/diagnostics/`, `wiki/procedures/`, `wiki/guidelines/`, `wiki/physiology/`, `wiki/anatomy/`, and `wiki/concepts/`.
- Updates existing topic nodes when a later textbook overlaps earlier knowledge; avoid duplicate nodes for the same disease, drug, diagnostic, procedure, guideline, anatomy, physiology, or concept.
- Creates new topic nodes only for concrete medical entities or workflows that are not already represented.
- Uses source pages as internal citation anchors; final answer citations should resolve to raw chapter/page provenance.
- Keeps `wiki/sources/index.md` and category indexes cumulative across all ingested textbooks.
- Updates `wiki/index.md`, `wiki/sources/index.md`, category indexes, `wiki/overview.md`, and `wiki/log.md`.
- Writes a health-check file under `docs/`.

Style rules for generated content:

- Body content should be Mandarin-first.
- Medical terms should include English when available, especially in page titles and aliases.
- Any dosing, contraindication, pregnancy/lactation, renal/hepatic adjustment, emergency care, or current guideline claim needs official current verification before clinical use.

## Textbook Ingest Workflow

Use this checklist for every remaining textbook:

1. Confirm the target folder under `raw/books/md/` and list chapter-split `.md` files.
2. Review current `wiki/index.md` and relevant category indexes so overlapping topics update existing nodes.
3. Expand `tools/ingest_topic_book.py` only with necessary concrete topic seeds for the textbook domain.
4. Prefer existing nodes over new nodes. New nodes should be specific diseases, drugs/classes, diagnostics, procedures, guideline/criteria pages, anatomy, physiology, or concrete clinical workflows.
5. Avoid abstract node titles such as `clinical`, `diagnosis`, `treatment`, `other`, `misc`, or chapter names.
6. Run the ingest command for one textbook.
7. Inspect representative overlap pages and new high-yield pages.
8. Run or verify the generated health check. It must report zero missing wiki links before commit unless the issue is intentionally documented.
9. Stage only `wiki/`, `docs/`, and relevant tool/schema updates. Do not stage Obsidian UI state such as `.obsidian/graph.json`.
10. Commit with `Ingest <book folder name>`.
11. If the user requested approval between books, stop and wait.

## Node Policy

Good nodes:

- `diabetes-mellitus`
- `hepatitis-b`
- `child-pugh-score`
- `proton-pump-inhibitors`
- `endoscopic-band-ligation`
- `hpa-axis`

Bad nodes:

- `diabetes-chapter`
- `treatment`
- `clinical`
- `diagnosis`
- `other`
- `chapter-3`

Overlap rule:

- If a later textbook mentions an existing topic, update the existing topic page with new source coverage and source-grounded details.
- Create a new page only when the later textbook introduces a distinct concrete topic not already represented.
- If two pages become synonyms, merge or alias them in frontmatter rather than letting both remain graph nodes.

After each committed ingest, the minimum acceptance checks are:

- Health-check file exists under `docs/`.
- `wiki/log.md` has one new ingest entry.
- `wiki/sources/index.md` includes all source chapter pages from all ingested books.
- Category indexes reflect total topic pages, not only the latest book.
- `git status --short` shows no uncommitted wiki/docs/tool changes; Obsidian local state may remain unstaged.
