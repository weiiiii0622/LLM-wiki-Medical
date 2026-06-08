# Tools and Skills for Future Codex Sessions

This vault uses plain markdown plus Obsidian. No custom tool is required.

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

