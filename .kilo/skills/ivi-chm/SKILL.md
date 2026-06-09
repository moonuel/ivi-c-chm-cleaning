---
name: ivi-chm-docs
description: How coding agents should access and cite the extracted Keysight IVI-C documentation for programming a hardware Vector Network Analyzer (VNA).
---

# IVI-C Docs Access

Use the extracted HTML corpus in this repo as the source of truth.

## Canonical paths

- HTML source: `data/extracted/Html/`
- Search index: `./.ivi-chm-index.sqlite3`

## Recommended workflow

1. Build or refresh the local index with `./.venv/bin/ivi-chm index data/extracted/Html`.
2. Search by exact symbol first with `./.venv/bin/ivi-chm search <query>`.
3. If the query is partial or normalized, rely on the alias result before broad full-text hits.
4. Use the returned `source_path` to open the exact HTML page when more detail is needed.
5. Parse that page with `./.venv/bin/ivi-chm parse <source_path>` to get the full structured record.

## How to reference docs in code work

- Prefer exact symbol lookup first.
- Use keyword search only when the exact symbol is unknown.
- Cite the original `source_path` in explanations and changes.
- Treat the parsed JSON fields as the canonical extracted record, not the rendered page text.
- Search now prefers exact symbol/path matches, then normalized aliases, then FTS5 full-text results.
- When a search result is ambiguous, prefer the one whose `matched_on` is `exact` or `alias` before opening additional pages.
- For user-facing answers, cite the canonical `symbol` and `source_path`, not the query string.

## Parsed fields

The parser returns:

- `symbol`
- `kind`
- `path_id`
- `title`
- `summary`
- `abstract`
- `prototype`
- `keywords`
- `function_tree_node`
- `aliases`
- `parameters`
- `returns`
- `remarks`
- `commands`
- `requirements`
- `defined_values`
- `see_also`
- `source_path`

## Validation habits

- Verify exact symbols such as `KtNA_AFRStandardGetDataFilePath` and `KTNA_ATTR_SIMULATE` with search before opening pages.
- Use concept queries like `simulation` only to find the right symbol, not as the final citation.
- Confirm result shape includes `symbol`, `kind`, `title`, `summary`, `snippet`, `source_path`, and `matched_on`.

## What not to do

- Do not rely on the raw `.chm` file during normal coding tasks.
- Do not paste large HTML pages into prompts.
- Do not assume TOC, index, or project metadata files exist in `data/extracted/`.
