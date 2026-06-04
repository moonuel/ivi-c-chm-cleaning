from __future__ import annotations

from pathlib import Path
import re
import shutil

from whoosh import index
from whoosh.fields import ID, KEYWORD, TEXT, Schema
from whoosh.qparser import MultifieldParser

from .parser import parse_document


DEFAULT_INDEX_DIR = Path(__file__).resolve().parents[2] / ".ivi-chm-index"


SCHEMA = Schema(
    symbol=ID(stored=True, unique=True),
    normalized_symbol=ID(stored=True),
    path_id=ID(stored=True),
    normalized_path_id=ID(stored=True),
    aliases=KEYWORD(stored=True, commas=True, lowercase=True, scorable=True),
    kind=ID(stored=True),
    title=TEXT(stored=True),
    summary=TEXT(stored=True),
    abstract=TEXT(stored=True),
    prototype=TEXT(stored=True),
    remarks=TEXT(stored=True),
    keywords=TEXT(stored=True),
    function_tree_node=TEXT(stored=True),
    see_also=TEXT(stored=True),
    source_path=ID(stored=True),
)


def _normalize_query(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _ranked_hit(hit: dict[str, str], matched_on: str) -> dict[str, str]:
    summary = hit.get("summary") or hit.get("abstract") or ""
    snippet = summary[:220]
    return {
        "symbol": hit.get("symbol", ""),
        "kind": hit.get("kind", ""),
        "title": hit.get("title", ""),
        "summary": summary,
        "source_path": hit.get("source_path", ""),
        "snippet": snippet,
        "matched_on": matched_on,
    }


def _match_stored_docs(ix, query: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    normalized = _normalize_query(query)
    exact: list[dict[str, str]] = []
    alias: list[dict[str, str]] = []
    with ix.searcher() as searcher:
        for hit in searcher.all_stored_fields():
            if query in {hit.get("symbol", ""), hit.get("path_id", "")}:  # exact canonical hit
                exact.append(hit)
                continue
            alias_values = {
                _normalize_query(hit.get("symbol", "")),
                _normalize_query(hit.get("path_id", "")),
            }
            raw_aliases = hit.get("aliases", "")
            if raw_aliases:
                alias_values.update(_normalize_query(alias) for alias in raw_aliases.split(","))
            if normalized in alias_values:
                alias.append(hit)
    return exact, alias


def build_index(html_dir: str | Path, index_dir: str | Path) -> None:
    html_dir = Path(html_dir)
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    if index.exists_in(index_dir):
        ix = index.open_dir(index_dir)
        if set(ix.schema.names()) != set(SCHEMA.names()):
            shutil.rmtree(index_dir)
            index_dir.mkdir(parents=True, exist_ok=True)
            ix = index.create_in(index_dir, SCHEMA)
    else:
        ix = index.create_in(index_dir, SCHEMA)
    writer = ix.writer()
    for path in html_dir.glob("*.html"):
        doc = parse_document(path)
        writer.update_document(
            symbol=doc.symbol,
            normalized_symbol=_normalize_query(doc.symbol),
            path_id=doc.path_id,
            normalized_path_id=_normalize_query(doc.path_id),
            aliases=",".join(doc.aliases),
            kind=doc.kind,
            title=doc.title,
            summary=doc.summary,
            abstract=doc.abstract,
            prototype=doc.prototype,
            remarks=doc.remarks,
            keywords=" ".join(doc.keywords),
            function_tree_node=doc.function_tree_node,
            see_also=" ".join(item["text"] for item in doc.see_also),
            source_path=doc.source_path,
        )
    writer.commit()


def search(index_dir: str | Path, query: str, limit: int = 10) -> list[dict[str, str]]:
    ix = index.open_dir(index_dir)
    exact_results, alias_results = _match_stored_docs(ix, query)
    if exact_results:
        return [_ranked_hit(hit, "exact") for hit in exact_results[:limit]]
    if alias_results:
        return [_ranked_hit(hit, "alias") for hit in alias_results[:limit]]

    with ix.searcher() as searcher:
        parser = MultifieldParser([
            "symbol",
            "title",
            "summary",
            "abstract",
            "prototype",
            "remarks",
            "keywords",
            "function_tree_node",
            "see_also",
        ], schema=ix.schema)
        results = searcher.search(parser.parse(query), limit=limit)
        return [_ranked_hit(dict(hit), "fulltext") for hit in results]
