from __future__ import annotations

import sqlite3
from pathlib import Path
import re
import json
import shutil

from .parser import parse_document


DEFAULT_INDEX_FILE = Path(__file__).resolve().parents[2] / ".ivi-chm-index.sqlite3"
SCHEMA_VERSION = 1


DOCUMENT_FIELDS = (
    "symbol",
    "kind",
    "path_id",
    "title",
    "summary",
    "abstract",
    "prototype",
    "remarks",
    "keywords",
    "function_tree_node",
    "see_also",
    "source_path",
)


def _normalize_query(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _connect(index_file: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(index_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def _has_fts5(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(value)")
        conn.execute("DROP TABLE IF EXISTS __fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            symbol TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            path_id TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            abstract TEXT NOT NULL,
            prototype TEXT NOT NULL,
            remarks TEXT NOT NULL,
            keywords TEXT NOT NULL,
            function_tree_node TEXT NOT NULL,
            see_also TEXT NOT NULL,
            source_path TEXT NOT NULL,
            normalized_symbol TEXT NOT NULL,
            normalized_path_id TEXT NOT NULL,
            aliases_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_documents_normalized_symbol ON documents(normalized_symbol);
        CREATE INDEX IF NOT EXISTS idx_documents_normalized_path_id ON documents(normalized_path_id);
        """
    )
    if not _has_fts5(conn):
        raise RuntimeError("SQLite FTS5 is required for portable search indexes")
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
            symbol,
            path_id,
            title,
            summary,
            abstract,
            prototype,
            remarks,
            keywords,
            function_tree_node,
            see_also,
            source_path,
            content='documents_fts_content'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents_fts_content (
            rowid INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            path_id TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            abstract TEXT NOT NULL,
            prototype TEXT NOT NULL,
            remarks TEXT NOT NULL,
            keywords TEXT NOT NULL,
            function_tree_node TEXT NOT NULL,
            see_also TEXT NOT NULL,
            source_path TEXT NOT NULL
        )
        """
    )


def _replace_document(conn: sqlite3.Connection, doc: object) -> None:
    aliases_json = json.dumps(list(doc.aliases), ensure_ascii=False, separators=(",", ":"))
    summary = doc.summary or doc.abstract or ""
    conn.execute(
        """
        INSERT INTO documents (
            symbol, kind, path_id, title, summary, abstract, prototype, remarks,
            keywords, function_tree_node, see_also, source_path,
            normalized_symbol, normalized_path_id, aliases_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol) DO UPDATE SET
            kind=excluded.kind,
            path_id=excluded.path_id,
            title=excluded.title,
            summary=excluded.summary,
            abstract=excluded.abstract,
            prototype=excluded.prototype,
            remarks=excluded.remarks,
            keywords=excluded.keywords,
            function_tree_node=excluded.function_tree_node,
            see_also=excluded.see_also,
            source_path=excluded.source_path,
            normalized_symbol=excluded.normalized_symbol,
            normalized_path_id=excluded.normalized_path_id,
            aliases_json=excluded.aliases_json
        """,
        (
            doc.symbol,
            doc.kind,
            doc.path_id,
            doc.title,
            summary,
            doc.abstract,
            doc.prototype,
            doc.remarks,
            " ".join(doc.keywords),
            doc.function_tree_node,
            " ".join(item["text"] for item in doc.see_also),
            doc.source_path,
            _normalize_query(doc.symbol),
            _normalize_query(doc.path_id),
            aliases_json,
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO documents_fts_content(rowid, symbol, path_id, title, summary, abstract, prototype, remarks, keywords, function_tree_node, see_also, source_path) VALUES ((SELECT rowid FROM documents WHERE symbol = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            doc.symbol,
            doc.symbol,
            doc.path_id,
            doc.title,
            summary,
            doc.abstract,
            doc.prototype,
            doc.remarks,
            " ".join(doc.keywords),
            doc.function_tree_node,
            " ".join(item["text"] for item in doc.see_also),
            doc.source_path,
        ),
    )
    conn.execute(
        "INSERT OR REPLACE INTO documents_fts(rowid, symbol, path_id, title, summary, abstract, prototype, remarks, keywords, function_tree_node, see_also, source_path) VALUES ((SELECT rowid FROM documents WHERE symbol = ?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            doc.symbol,
            doc.symbol,
            doc.path_id,
            doc.title,
            summary,
            doc.abstract,
            doc.prototype,
            doc.remarks,
            " ".join(doc.keywords),
            doc.function_tree_node,
            " ".join(item["text"] for item in doc.see_also),
            doc.source_path,
        ),
    )


def build_index(html_dir: str | Path, index_file: str | Path) -> None:
    html_dir = Path(html_dir)
    index_file = Path(index_file)
    if index_file.exists():
        index_file.unlink()
    index_file.parent.mkdir(parents=True, exist_ok=True)
    with _connect(index_file) as conn:
        _ensure_schema(conn)
        for path in sorted(html_dir.glob("*.html")):
            _replace_document(conn, parse_document(path))
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", str(SCHEMA_VERSION)),
                ("build_timestamp", ""),
            ],
        )
        conn.commit()


def _ranked_hit(hit: sqlite3.Row | dict[str, str], matched_on: str) -> dict[str, str]:
    summary = hit["summary"] if isinstance(hit, sqlite3.Row) else hit.get("summary") or hit.get("abstract") or ""
    snippet = summary[:220]
    return {
        "symbol": hit["symbol"] if isinstance(hit, sqlite3.Row) else hit.get("symbol", ""),
        "kind": hit["kind"] if isinstance(hit, sqlite3.Row) else hit.get("kind", ""),
        "title": hit["title"] if isinstance(hit, sqlite3.Row) else hit.get("title", ""),
        "summary": summary,
        "source_path": hit["source_path"] if isinstance(hit, sqlite3.Row) else hit.get("source_path", ""),
        "snippet": snippet,
        "matched_on": matched_on,
    }


def _fetch_by_exact_or_alias(conn: sqlite3.Connection, query: str) -> tuple[list[sqlite3.Row], list[sqlite3.Row]]:
    normalized = _normalize_query(query)
    exact = conn.execute(
        "SELECT * FROM documents WHERE symbol = ? OR path_id = ? ORDER BY symbol",
        (query, query),
    ).fetchall()
    alias_matches = conn.execute(
        "SELECT * FROM documents WHERE normalized_symbol = ? OR normalized_path_id = ? OR instr(aliases_json, ?) > 0 ORDER BY symbol",
        (normalized, normalized, json.dumps(query, ensure_ascii=False)),
    ).fetchall()
    alias_filtered = [row for row in alias_matches if row not in exact and normalized in {
        row["normalized_symbol"],
        row["normalized_path_id"],
        *(_normalize_query(alias) for alias in json.loads(row["aliases_json"])),
    }]
    return exact, alias_filtered


def search(index_file: str | Path, query: str, limit: int = 10) -> list[dict[str, str]]:
    with _connect(index_file) as conn:
        _ensure_schema(conn)
        exact_results, alias_results = _fetch_by_exact_or_alias(conn, query)
        if exact_results:
            return [_ranked_hit(hit, "exact") for hit in exact_results[:limit]]
        if alias_results:
            return [_ranked_hit(hit, "alias") for hit in alias_results[:limit]]

        rows = conn.execute(
            """
            SELECT d.*
            FROM documents_fts f
            JOIN documents d ON d.rowid = f.rowid
            WHERE documents_fts MATCH ?
            ORDER BY bm25(documents_fts)
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [_ranked_hit(row, "fulltext") for row in rows]
