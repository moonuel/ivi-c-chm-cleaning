from __future__ import annotations

import argparse
import json
from pathlib import Path

from .indexer import DEFAULT_INDEX_FILE, build_index, search
from .benchmark import DEFAULT_BENCHMARK_FILE, format_report, run_benchmark, write_benchmark_questions
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

    p_bench = sub.add_parser("benchmark")
    p_bench.add_argument("html_dir", nargs="?", default=str(Path(__file__).resolve().parents[2] / "data" / "extracted" / "Html"))
    p_bench.add_argument("index_file", nargs="?", default=str(DEFAULT_INDEX_FILE))
    p_bench.add_argument("--cases", default=str(DEFAULT_BENCHMARK_FILE))
    p_bench.add_argument("--refresh-cases", action="store_true")
    p_bench.add_argument("--systems", choices=["skill", "grep", "both"], default="both")

    args = parser.parse_args()
    if args.cmd == "parse":
        print(json.dumps(parse_document(args.path).to_dict(), indent=2))
    elif args.cmd == "index":
        build_index(args.html_dir, args.index_file)
    elif args.cmd == "search":
        print(json.dumps(search(args.index_file, args.query), indent=2))
    elif args.cmd == "benchmark":
        cases_file = Path(args.cases)
        if args.refresh_cases or not cases_file.exists():
            write_benchmark_questions(args.html_dir, cases_file)
        systems = ("skill", "grep") if args.systems == "both" else (args.systems,)
        report = run_benchmark(args.html_dir, args.index_file, cases_file, systems=systems)
        print(format_report(report))
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
