from __future__ import annotations

import argparse
import json
from pathlib import Path

from .indexer import DEFAULT_INDEX_FILE, build_index, search
from .parser import parse_document


def main() -> None:
    parser = argparse.ArgumentParser(prog="ivi-chm")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse")
    p_parse.add_argument("path")

    p_index = sub.add_parser("index")
    p_index.add_argument("html_dir")
    p_index.add_argument("index_file", nargs="?", default=str(DEFAULT_INDEX_FILE))

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("index_file", nargs="?", default=str(DEFAULT_INDEX_FILE))

    args = parser.parse_args()
    if args.cmd == "parse":
        print(json.dumps(parse_document(args.path).to_dict(), indent=2))
    elif args.cmd == "index":
        build_index(args.html_dir, args.index_file)
    elif args.cmd == "search":
        print(json.dumps(search(args.index_file, args.query), indent=2))


if __name__ == "__main__":
    main()
