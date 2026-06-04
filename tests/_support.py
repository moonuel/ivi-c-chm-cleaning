from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CASES_PATH = FIXTURES_DIR / "lookup_cases.json"
REAL_HTML_DIR = ROOT / "data" / "extracted" / "Html"
MINI_HTML_DIR = FIXTURES_DIR / "mini_html"


def load_cases() -> list[dict[str, object]]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def load_cases_for_corpus(corpus: str) -> list[dict[str, object]]:
    return [case for case in load_cases() if case["corpus"] == corpus]


def find_hit(results: list[dict[str, str]], symbol: str) -> tuple[int, dict[str, str]] | None:
    for index, hit in enumerate(results):
        if hit.get("symbol") == symbol:
            return index, hit
    return None
