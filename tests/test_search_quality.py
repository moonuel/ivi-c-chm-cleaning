from __future__ import annotations

from pathlib import Path

import pytest

from ivi_chm.indexer import search

from tests._support import find_hit, load_cases, MINI_HTML_DIR, REAL_HTML_DIR


CASES = load_cases()


def _run_case(index_dir: Path, case: dict[str, object]) -> list[dict[str, str]]:
    return search(index_dir, str(case["query"]), limit=int(case.get("limit", 10)))


def _assert_result_shape(hit: dict[str, str]) -> None:
    assert hit["symbol"]
    assert hit["title"]
    assert hit["source_path"]
    assert hit["summary"]
    assert hit["snippet"]
    assert hit["matched_on"] in {"exact", "alias", "fulltext"}


@pytest.mark.parametrize(
    "case",
    [pytest.param(case, id=case["id"]) for case in CASES if case["corpus"] == "real"],
)
def test_real_corpus_lookup_quality(real_index_dir: Path, case: dict[str, object]) -> None:
    results = _run_case(real_index_dir, case)
    category = str(case["category"])

    if category == "negative":
        assert results == []
        return

    match = find_hit(results, str(case["expected_symbol"]))
    assert match is not None, f"missing expected symbol for {case['id']}: {results!r}"
    rank, hit = match

    assert rank < int(case["max_rank"])
    assert hit["matched_on"] == str(case["expected_matched_on"])
    assert hit["source_path"].endswith(str(case["expected_source_suffix"]))
    _assert_result_shape(hit)

    for term in case.get("must_contain_terms", []):
        term = str(term).lower()
        assert term in hit["summary"].lower() or term in hit["title"].lower()

    if category == "ambiguous":
        assert len(results) >= int(case["min_results"])


@pytest.mark.parametrize(
    "case",
    [pytest.param(case, id=case["id"]) for case in CASES if case["corpus"] == "mini"],
)
def test_mini_corpus_lookup_quality(mini_index_dir: Path, case: dict[str, object]) -> None:
    results = _run_case(mini_index_dir, case)
    category = str(case["category"])

    if category == "negative":
        assert results == []
        return

    match = find_hit(results, str(case["expected_symbol"]))
    assert match is not None, f"missing expected symbol for {case['id']}: {results!r}"
    rank, hit = match

    assert rank < int(case["max_rank"])
    assert hit["matched_on"] == str(case["expected_matched_on"])
    assert hit["source_path"].endswith(str(case["expected_source_suffix"]))
    _assert_result_shape(hit)

    for term in case.get("must_contain_terms", []):
        term = str(term).lower()
        assert term in hit["summary"].lower() or term in hit["title"].lower()

    if category == "ambiguous":
        assert len(results) >= int(case["min_results"])


def test_mini_fulltext_ranking(mini_index_dir: Path) -> None:
    results = search(mini_index_dir, "sharedterm", limit=10)
    assert [hit["symbol"] for hit in results[:2]] == ["Mini_FulltextAlpha", "Mini_FulltextBeta"]
    assert results[0]["matched_on"] == "fulltext"
