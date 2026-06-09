from __future__ import annotations

import json
from pathlib import Path

import pytest

from ivi_chm.benchmark import format_report, generate_benchmark_questions, run_benchmark

from tests._support import REAL_HTML_DIR


pytestmark = pytest.mark.skip(reason="deprecated benchmark tests are disabled for now")


def test_generate_benchmark_questions_has_four_categories(tmp_path: Path) -> None:
    payload = generate_benchmark_questions(REAL_HTML_DIR, per_category=1)

    assert payload["question_count"] == 4
    assert payload["corpus"]["file_count"] > 0
    assert len(payload["corpus"]["sha256"]) == 64
    assert {item["category"] for item in payload["questions"]} == {
        "exact_lookup",
        "section_location",
        "multi_hop_synthesis",
        "paraphrase_semantic_match",
    }

    out = tmp_path / "benchmark.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["question_count"] == 4


def test_run_benchmark_reports_both_systems(real_index_file: Path, tmp_path: Path) -> None:
    questions_file = tmp_path / "benchmark.json"
    payload = generate_benchmark_questions(REAL_HTML_DIR, per_category=1)
    questions_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = run_benchmark(REAL_HTML_DIR, real_index_file, questions_file, systems=("skill", "grep"))

    assert report["question_count"] == 4
    assert set(report["systems"].keys()) == {"skill", "grep"}
    assert "corpus_hash" in format_report(report)
