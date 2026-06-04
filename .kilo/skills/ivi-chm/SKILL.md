---
name: ivi-chm-docs
description: How coding agents should access and cite the extracted Keysight IVI-C documentation.
---

# IVI-C Docs Access

Use the extracted HTML corpus in this repo as the source of truth.

## Canonical paths

- HTML source: `data/extracted/Html/`
- Search index: `./.ivi-chm-index/`

## Recommended workflow

1. Build or refresh the local index with `./.venv/bin/ivi-chm index data/extracted/Html`.
2. Search by exact symbol or keyword with `./.venv/bin/ivi-chm search <query>`.
3. Use the returned `source_path` to open the exact HTML page when more detail is needed.
4. Parse that page with `./.venv/bin/ivi-chm parse <source_path>` to get structured fields.

## How to reference docs in code work

- Prefer exact symbol lookup first.
- Use keyword search only when the exact symbol is unknown.
- Cite the original `source_path` in explanations and changes.
- Treat the parsed JSON fields as the canonical extracted record, not the rendered page text.

## Parsed fields

The parser returns:

- `symbol`
- `kind`
- `title`
- `summary`
- `prototype`
- `parameters`
- `returns`
- `remarks`
- `commands`
- `requirements`
- `defined_values`
- `see_also`
- `source_path`

## What not to do

- Do not rely on the raw `.chm` file during normal coding tasks.
- Do not paste large HTML pages into prompts.
- Do not assume TOC, index, or project metadata files exist in `data/extracted/`.
