from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .parser import parse_document


DEFAULT_INDEX_FILE = Path(__file__).resolve().parents[2] / ".ivi-chm-index.sqlite3"
SCHEMA_VERSION = 1

SEARCH_FIELDS = ("symbol", "path_id", "title", "summary", "abstract", "prototype", "remarks", "keywords", "function_tree_node", "see_also", "source_path")


def _normalize_query(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _connect(index_file: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(index_file))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
        CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
        CREATE INDEX IF NOT EXISTS idx_documents_summary ON documents(summary);
        CREATE INDEX IF NOT EXISTS idx_documents_source_path ON documents(source_path);
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
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("schema_version", str(SCHEMA_VERSION)))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", ("build_timestamp", ""))
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
    alias_rows = conn.execute("SELECT * FROM documents ORDER BY symbol").fetchall()
    alias_matches: list[tuple[float, sqlite3.Row]] = []
    for row in alias_rows:
        aliases = {_normalize_query(alias) for alias in json.loads(row["aliases_json"])}
        if row in exact:
            continue
        candidates = {row["normalized_symbol"], row["normalized_path_id"], *aliases}
        best_score = 0.0
        for candidate in candidates:
            if not candidate:
                continue
            if candidate == normalized:
                best_score = max(best_score, 3.0)
            elif normalized in candidate:
                best_score = max(best_score, 2.0)
            elif len(candidate) >= 12 and candidate in normalized:
                best_score = max(best_score, 1.0)
        if best_score:
            alias_matches.append((best_score, row))
    alias_matches.sort(key=lambda item: (-item[0], item[1]["symbol"]))
    return exact, [row for _score, row in alias_matches]


def _text_score(row: sqlite3.Row, terms: list[str]) -> int:
    haystack = " ".join(str(row[field]).lower() for field in SEARCH_FIELDS)
    score = 0
    for term in terms:
        score += haystack.count(term)
    return score


def search(index_file: str | Path, query: str, limit: int = 10) -> list[dict[str, str]]:
    with _connect(index_file) as conn:
        _ensure_schema(conn)
        exact_results, alias_results = _fetch_by_exact_or_alias(conn, query)
        if exact_results:
            return [_ranked_hit(hit, "exact") for hit in exact_results[:limit]]
        if alias_results:
            return [_ranked_hit(hit, "alias") for hit in alias_results[:limit]]

        terms = [term for term in re.findall(r"[a-z0-9]+", query.lower()) if term]
        if not terms:
            return []

        rows = conn.execute("SELECT * FROM documents ORDER BY symbol").fetchall()
        scored = [(row, _text_score(row, terms)) for row in rows]
        hits = [row for row, score in sorted(scored, key=lambda item: (-item[1], item[0]["symbol"])) if score > 0]
        return [_ranked_hit(row, "fulltext") for row in hits[:limit]]
