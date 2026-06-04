# IVI-C CHM Cleaning

Parse and search the already-extracted Keysight IVI-C help pages in `data/extracted/Html/`.

## What this is for

This repo is meant to turn the vendor HTML pages into structured records that are easier to search and reuse from code.

The normal workflow is:

1. Read a page from `data/extracted/Html/`.
2. Parse it into fields like `symbol`, `path_id`, `abstract`, `keywords`, `prototype`, `parameters`, and `see_also`.
3. Build a local Whoosh index over the extracted pages.
4. Query that index with exact-first lookup and boosted full-text fallback.

## Requirements

- Python 3.12+
- The existing `.venv`

The project already assumes the HTML has been extracted. It does not depend on CHM extraction at runtime.

## Installation

Install the package in editable mode:

```bash
./.venv/bin/pip install -e .
```

## Usage

### Parse one page

```bash
./.venv/bin/ivi-chm parse data/extracted/Html/KtNA_AFRStandardGetDataFilePath.html
```

This prints JSON with the normalized record.

### Build an index

```bash
./.venv/bin/ivi-chm index data/extracted/Html
```

This scans every `*.html` file in `data/extracted/Html/` and writes a local search index to `./.ivi-chm-index/` in the repo.

### Search the index

```bash
./.venv/bin/ivi-chm search KtNA_AFRStandardGetDataFilePath
```

This returns matching documents as JSON.

If you want a different location, pass an explicit path as the second argument to `index` or the first argument to `search`.

## Output fields

Parsed documents currently include:

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

## Notes

- The parser is tuned for Microsoft Help-style HTML pages in the extracted corpus.
- It is designed around the existing extracted pages, not the raw `.chm` file.
- The `ivi-chm` CLI is the main entry point for both parsing and search.
