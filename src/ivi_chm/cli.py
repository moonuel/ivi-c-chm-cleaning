from __future__ import annotations

import argparse
import json
from pathlib import Path

from .indexer import DEFAULT_INDEX_DIR, build_index, search
from .parser import parse_document


def main() -> None:
    parser = argparse.ArgumentParser(prog="ivi-chm")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse")
    p_parse.add_argument("path")

    p_index = sub.add_parser("index")
    p_index.add_argument("html_dir")
    p_index.add_argument("index_dir", nargs="?", default=str(DEFAULT_INDEX_DIR))

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("index_dir", nargs="?", default=str(DEFAULT_INDEX_DIR))

    args = parser.parse_args()
    if args.cmd == "parse":
        print(json.dumps(parse_document(args.path).to_dict(), indent=2))
    elif args.cmd == "index":
        build_index(args.html_dir, args.index_dir)
    elif args.cmd == "search":
        print(json.dumps(search(args.index_dir, args.query), indent=2))


if __name__ == "__main__":
    main()
