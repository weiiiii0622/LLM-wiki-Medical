# Query Citation Policy

This vault has two citation layers:

- Topic pages such as `wiki/conditions/dumping-syndrome.md` are LLM-generated synthesis nodes.
- Source pages such as `wiki/sources/med3-book3-ch08.md` map wiki knowledge back to immutable raw files and page ranges.

## Required Rule

When answering a query, use topic pages for retrieval and synthesis, but cite raw source chapters in final sources.

Bad final source:

```markdown
[[conditions/dumping-syndrome]]
[[anatomy/small-intestine]]
```

Good final source:

```markdown
醫(三)第3冊腎內感染_第一篇、腎臟內科_辛、多囊性腎病 Page 133-138
```

## How To Resolve Sources

1. Read `wiki/index.md`.
2. Search/read relevant topic pages.
3. For each claim, use the topic page `Source: ...` raw citation if already present.
4. If only a `[[sources/<slug>]]` internal link is present, open that source page and use `canonical_citation`.
5. Never cite topic-node paths such as `conditions/`, `anatomy/`, `concepts/`, `drugs/`, or `diagnostics/` as final sources.

## Maintenance

Run this after source ingestion or citation-policy changes:

```bash
python3 tools/update_raw_citations.py --dry-run
python3 tools/update_raw_citations.py
```

If the tool reports `Page unknown`, inspect the raw markdown for missing page markers before relying on that citation.
