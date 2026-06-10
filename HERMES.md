# Hermes Query Rules

Use this vault as an LLM wiki with topic pages for retrieval and raw-source strings for citations.

## Source Policy

- Do not search or open `raw/`, `/mnt/llm-wiki-med/raw`, or `raw/books/md`; remote deployments may not have raw files.
- Do not cite topic pages as sources: `[[drugs/...]]`, `[[conditions/...]]`, `[[anatomy/...]]`, `[[diagnostics/...]]`, `[[procedures/...]]`, `[[guidelines/...]]`, `[[physiology/...]]`, `[[concepts/...]]`.
- Use topic pages only as consulted notes.
- Final citations must be raw chapter/page strings copied from topic-page `Source:` lines or from `wiki/sources/*` `canonical_citation`.

Good citation:

```markdown
醫(六)第4冊麻醉耳鼻喉_第一篇、麻醉科_戊、靜脈麻醉劑 Page 59-72
```

Bad citation:

```markdown
[[drugs/ketamine]]
```

## Query Flow

1. Read `wiki/index.md`.
2. Search topic pages.
3. Answer from topic-page content.
4. For each claim, collect source strings after `Source:`.
5. If raw source strings are missing, open the linked `wiki/sources/<slug>.md` page and use `canonical_citation`.
