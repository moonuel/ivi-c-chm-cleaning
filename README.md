# IVI-C CHM Cleaning

Parse and search the already-extracted Keysight IVI-C help pages in `data/extracted/Html/`.

## Purpose

This repo turns the vendor HTML pages into structured records that are easier to search and reuse from code.

The workflow is:

1. Read a page from `data/extracted/Html/`.
2. Parse it into fields like `symbol`, `path_id`, `abstract`, `keywords`, `prototype`, `parameters`, and `see_also`.
3. Build a local SQLite index over the extracted pages.
4. Query that index with exact-first lookup, normalized aliases, and deterministic text fallback.

## Requirements

- Python 3.12+
- The existing `.venv`
- The extracted HTML corpus in `data/extracted/Html/`

The project assumes the HTML has already been extracted. It does not depend on CHM extraction at runtime.

## Redistributable Artifacts

- The SQLite index file produced by `ivi-chm index`, defaulting to `./.ivi-chm-index.sqlite3`
- The optional Windows executable in `dist\ivi-chm.exe`

These artifacts can be copied and shared independently of the source tree.

## Installation

Install the package in editable mode:

```bash
./.venv/bin/pip install -e .
```

Install the build extra only if you want the standalone executable:

```bash
./.venv/bin/pip install -e .[build]
```

## CLI Usage

### Parse One Page

```bash
./.venv/bin/ivi-chm parse data/extracted/Html/KtNA_AFRStandardGetDataFilePath.html
```

This prints JSON with the normalized record.

### Build an Index

```bash
./.venv/bin/ivi-chm index data/extracted/Html
```

This scans every `*.html` file in `data/extracted/Html/` and writes a portable SQLite database file to `./.ivi-chm-index.sqlite3` in the repo.

### Search the Index

```bash
./.venv/bin/ivi-chm search KtNA_AFRStandardGetDataFilePath ./.ivi-chm-index.sqlite3
```

This returns matching documents as JSON.

The second argument is the index file path for both `index` and `search`. If omitted, both commands use `./.ivi-chm-index.sqlite3`.

## Optional Executable

This is only for packaging the CLI into a single Windows executable.

Build it with:

```powershell
./build_exe.ps1
```

The executable is written to `dist\ivi-chm.exe`.

## Output Fields

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
- `search` takes the query first and the index file second.
