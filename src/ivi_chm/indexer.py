from __future__ import annotations

from pathlib import Path

from whoosh import index
from whoosh.fields import ID, TEXT, Schema
from whoosh.qparser import MultifieldParser

from .parser import parse_document


DEFAULT_INDEX_DIR = Path(__file__).resolve().parents[2] / ".ivi-chm-index"


SCHEMA = Schema(
    symbol=ID(stored=True, unique=True),
    title=TEXT(stored=True),
    summary=TEXT(stored=True),
    prototype=TEXT(stored=True),
    source_path=ID(stored=True),
)


def build_index(html_dir: str | Path, index_dir: str | Path) -> None:
    html_dir = Path(html_dir)
    index_dir = Path(index_dir)
    index_dir.mkdir(parents=True, exist_ok=True)
    if index.exists_in(index_dir):
        ix = index.open_dir(index_dir)
    else:
        ix = index.create_in(index_dir, SCHEMA)
    writer = ix.writer()
    for path in html_dir.glob("*.html"):
        doc = parse_document(path)
        writer.update_document(
            symbol=doc.symbol,
            title=doc.title,
            summary=doc.summary,
            prototype=doc.prototype,
            source_path=doc.source_path,
        )
    writer.commit()


def search(index_dir: str | Path, query: str, limit: int = 10) -> list[dict[str, str]]:
    ix = index.open_dir(index_dir)
    with ix.searcher() as searcher:
        parser = MultifieldParser(["symbol", "title", "summary", "prototype"], schema=ix.schema)
        results = searcher.search(parser.parse(query), limit=limit)
        return [dict(hit) for hit in results]
