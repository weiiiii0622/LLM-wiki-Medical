# Tools and Skills for Future Codex Sessions

This vault uses plain markdown plus Obsidian. `tools/ingest_topic_book.py` is the reusable deterministic ingest helper for chapter-split textbooks.

## Required Habits

- Read `AGENTS.md` before maintaining the wiki.
- Read `wiki/index.md` before answering questions.
- Use `rg` and `rg --files` to search.
- Use `apply_patch` for edits.
- Keep `raw/` immutable.
- Update `wiki/index.md` and append `wiki/log.md` after every ingest or durable query.

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

## Textbook Ingest Tool

Use this when a textbook folder under `raw/books/md/` contains one full-book markdown file plus chapter-split markdown files.

```bash
python3 tools/ingest_topic_book.py '醫(三)第1冊心胸內' --book-key med3-book1
```

What it does:

- Reads only chapter-split `.md` files and ignores the full-book `.md`.
- Creates one source summary per chapter under `wiki/sources/`.
- Creates topic-first nodes under `wiki/conditions/`, `wiki/drugs/`, `wiki/diagnostics/`, `wiki/procedures/`, `wiki/guidelines/`, `wiki/physiology/`, `wiki/anatomy/`, and `wiki/concepts/`.
- Uses source pages as citation anchors; chapter titles should not become the main graph shape.
- Updates `wiki/index.md`, `wiki/sources/index.md`, category indexes, `wiki/overview.md`, and `wiki/log.md`.
- Writes a health-check file under `docs/`.

Style rules for generated content:

- Body content should be Mandarin-first.
- Medical terms should include English when available, especially in page titles and aliases.
- Any dosing, contraindication, pregnancy/lactation, renal/hepatic adjustment, emergency care, or current guideline claim needs official current verification before clinical use.
