#!/usr/bin/env python3
"""Resolve wiki source links to raw textbook chapter/page citations.

This keeps topic pages useful for retrieval while making answer citations point
at immutable raw source chapters.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKI = ROOT / "wiki"
SOURCE_DIR = WIKI / "sources"
TOPIC_DIRS = (
    "conditions",
    "drugs",
    "diagnostics",
    "procedures",
    "guidelines",
    "physiology",
    "anatomy",
    "concepts",
)

SOURCE_LINK_RE = re.compile(r"Source: \[\[sources/([^|\]\n]+)(?:\|[^\]\n]*)?\]\]")
PAGE_MARKER_RE = re.compile(r"^\{(\d+)\}-+", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


@dataclass(frozen=True)
class CitationInfo:
    slug: str
    source_file: str
    raw_source_title: str
    page_start: int | None
    page_end: int | None
    canonical_citation: str


def yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse_frontmatter(text: str) -> tuple[str, str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return "", "", text
    return match.group(0), match.group(1), text[match.end() :]


def get_scalar(frontmatter: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    return value


def upsert_scalar(frontmatter: str, key: str, value: str) -> str:
    line = f"{key}: {value}"
    pattern = re.compile(rf"^{re.escape(key)}:\s*.*$", re.MULTILINE)
    if pattern.search(frontmatter):
        return pattern.sub(line, frontmatter)
    source_file_match = re.search(r"^source_file:\s*.*$", frontmatter, re.MULTILINE)
    if source_file_match:
        insert_at = source_file_match.end()
        return frontmatter[:insert_at] + "\n" + line + frontmatter[insert_at:]
    return frontmatter.rstrip() + "\n" + line + "\n"


def upsert_provenance_block(frontmatter: str, info: CitationInfo) -> str:
    keys = (
        "raw_source_title",
        "raw_source_file",
        "page_start",
        "page_end",
        "canonical_citation",
    )
    cleaned = frontmatter
    for key in keys:
        cleaned = re.sub(rf"^{re.escape(key)}:\s*.*$\n?", "", cleaned, flags=re.MULTILINE)

    block = "\n".join(
        (
            f"raw_source_title: {yaml_quote(info.raw_source_title)}",
            f"raw_source_file: {yaml_quote(info.source_file)}",
            f"page_start: {info.page_start if info.page_start is not None else 'null'}",
            f"page_end: {info.page_end if info.page_end is not None else 'null'}",
            f"canonical_citation: {yaml_quote(info.canonical_citation)}",
        )
    )
    source_file_match = re.search(r"^source_file:\s*.*$", cleaned, re.MULTILINE)
    if source_file_match:
        insert_at = source_file_match.end()
        return cleaned[:insert_at] + "\n" + block + cleaned[insert_at:]
    return cleaned.rstrip() + "\n" + block + "\n"


def build_citation(source_path: Path) -> tuple[CitationInfo | None, str | None]:
    if source_path.name == "index.md":
        return None, None
    text = source_path.read_text(encoding="utf-8")
    _, frontmatter, _ = parse_frontmatter(text)
    source_file = get_scalar(frontmatter, "source_file")
    if not source_file:
        return None, f"{source_path}: missing source_file"

    raw_path = ROOT / source_file
    raw_source_title = raw_path.stem
    page_start: int | None = None
    page_end: int | None = None
    if raw_path.exists():
        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        pages = [int(page) for page in PAGE_MARKER_RE.findall(raw_text)]
        if pages:
            page_start, page_end = min(pages), max(pages)
    else:
        return None, f"{source_path}: raw file missing: {source_file}"

    if page_start is None or page_end is None:
        canonical = f"{raw_source_title} Page unknown"
    elif page_start == page_end:
        canonical = f"{raw_source_title} Page {page_start}"
    else:
        canonical = f"{raw_source_title} Page {page_start}-{page_end}"

    return (
        CitationInfo(
            slug=source_path.stem,
            source_file=source_file,
            raw_source_title=raw_source_title,
            page_start=page_start,
            page_end=page_end,
            canonical_citation=canonical,
        ),
        None,
    )


def update_source_page(source_path: Path, info: CitationInfo) -> bool:
    text = source_path.read_text(encoding="utf-8")
    full_fm, frontmatter, body = parse_frontmatter(text)
    if not full_fm:
        return False

    updated = upsert_provenance_block(frontmatter, info)

    new_text = "---\n" + updated.rstrip() + "\n---\n" + body
    new_text = upsert_metadata_line(new_text, "Canonical citation", info.canonical_citation)
    new_text = upsert_metadata_line(
        new_text,
        "Pages covered",
        "unknown" if info.page_start is None else f"{info.page_start}-{info.page_end}",
    )
    if new_text != text:
        source_path.write_text(new_text, encoding="utf-8")
        return True
    return False


def upsert_metadata_line(text: str, label: str, value: str) -> str:
    line = f"- {label}: {value}"
    pattern = re.compile(rf"^- {re.escape(label)}:\s*.*$", re.MULTILINE)
    if pattern.search(text):
        return pattern.sub(line, text)

    chapter_match = re.search(r"^- Chapter file:.*$", text, re.MULTILINE)
    if chapter_match:
        insert_at = chapter_match.end()
        return text[:insert_at] + "\n" + line + text[insert_at:]

    metadata_match = re.search(r"^## Source Metadata\s*$", text, re.MULTILINE)
    if metadata_match:
        line_start = text.find("\n", metadata_match.end())
        if line_start != -1:
            return text[: line_start + 1] + line + "\n" + text[line_start + 1 :]
    return text


def rewrite_topic_citations(citations: dict[str, CitationInfo], dry_run: bool) -> tuple[int, int, set[str]]:
    files_changed = 0
    citations_changed = 0
    unresolved: set[str] = set()

    for dirname in TOPIC_DIRS:
        for path in sorted((WIKI / dirname).glob("*.md")):
            text = path.read_text(encoding="utf-8")

            def replace(match: re.Match[str]) -> str:
                nonlocal citations_changed
                slug = match.group(1)
                info = citations.get(slug)
                if not info:
                    unresolved.add(slug)
                    return match.group(0)
                citations_changed += 1
                return f"Source: {info.canonical_citation}"

            new_text = SOURCE_LINK_RE.sub(replace, text)
            if new_text != text:
                files_changed += 1
                if not dry_run:
                    path.write_text(new_text, encoding="utf-8")

    return files_changed, citations_changed, unresolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    citations: dict[str, CitationInfo] = {}
    source_errors: list[str] = []
    for source_path in sorted(SOURCE_DIR.glob("*.md")):
        info, error = build_citation(source_path)
        if error:
            source_errors.append(error)
        if info:
            citations[info.slug] = info

    source_pages_changed = 0
    if not args.dry_run:
        for source_path in sorted(SOURCE_DIR.glob("*.md")):
            info = citations.get(source_path.stem)
            if info and update_source_page(source_path, info):
                source_pages_changed += 1

    topic_files_changed, topic_citations_changed, unresolved = rewrite_topic_citations(citations, args.dry_run)

    print(f"source_pages_seen={len(citations)}")
    print(f"source_pages_changed={source_pages_changed}")
    print(f"topic_files_changed={topic_files_changed}")
    print(f"topic_citations_changed={topic_citations_changed}")
    print(f"source_errors={len(source_errors)}")
    for error in source_errors[:40]:
        print(f"ERROR {error}")
    if len(source_errors) > 40:
        print(f"ERROR ... {len(source_errors) - 40} more")
    print(f"unresolved_source_slugs={len(unresolved)}")
    for slug in sorted(unresolved)[:40]:
        print(f"UNRESOLVED {slug}")
    if len(unresolved) > 40:
        print(f"UNRESOLVED ... {len(unresolved) - 40} more")
    return 1 if source_errors or unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
