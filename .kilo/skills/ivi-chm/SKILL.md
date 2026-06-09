---
name: ivi-chm-docs
description: How coding agents should use the raw extracted Keysight IVI-C HTML corpus as the source of truth.
---

# IVI-C Docs Access

Use the extracted HTML corpus in this repo as the source of truth.

## Canonical paths

- HTML source: `data/extracted/Html/`

## Recommended workflow

1. Find the relevant HTML file directly under `data/extracted/Html/`.
2. Open that raw HTML page and read the exact source content.
3. Prefer the page title, headings, and nearby text over any derived index.
4. If needed, search within `data/extracted/Html/` for filenames or terms, then open the matching page.
5. Cite the original `source_path` or HTML file path in explanations and changes.

## How to reference docs in code work

- Prefer exact filename or symbol-page lookup first.
- Use keyword search only when the exact page is unknown.
- Treat the raw HTML content as the canonical record, not a parsed summary or search result.
- When a page is ambiguous, open the page directly and inspect the surrounding HTML.
- For user-facing answers, cite the canonical page path, not the query string.

## What to extract from pages

When reading raw HTML pages, focus on:

- page title
- section headings
- prototypes and syntax blocks
- parameter tables
- remarks and command sections
- see-also links

## Validation habits

- Verify exact pages such as `KtNA_AFRStandardGetDataFilePath.html` and `KTNA_ATTR_SIMULATE.html` by opening the raw HTML.
- Use concept queries like `simulation` only to find the right page, not as the final citation.
- Confirm the answer is grounded in the original HTML page and not a rewritten summary.

## What not to do

- Do not rely on the SQLite index for normal doc lookup work.
- Do not assume parsed JSON fields are available or required.
- Do not paste large HTML pages into prompts.
- Do not assume TOC, index, or project metadata files exist in `data/extracted/`.
