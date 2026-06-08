# Medical LLM Wiki

This Obsidian vault is set up as a medical LLM-maintained wiki.

- Put immutable source material in `raw/`.
- Let Codex maintain structured pages in `wiki/`.
- Use `AGENTS.md` as the operating schema for future Codex sessions.

Start by adding a book, article, chapter, lecture note, or guideline into `raw/books/`, `raw/articles/`, or `raw/notes/`, then ask Codex:

```text
Ingest raw/books/<filename> into the medical wiki.
```

Codex should create a source summary, update topic pages, update `wiki/index.md`, and append to `wiki/log.md`.

