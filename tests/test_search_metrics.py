from __future__ import annotations

from pathlib import Path

from ivi_chm.indexer import search

from tests._support import find_hit, load_cases


CASES = load_cases()


def _evaluate_case(index_dir: Path, case: dict[str, object]) -> tuple[bool, int | None, int]:
    results = search(index_dir, str(case["query"]), limit=int(case.get("limit", 10)))
    if case["category"] == "negative":
        return results == [], None, len(results)

    match = find_hit(results, str(case["expected_symbol"]))
    if match is None:
        return False, None, len(results)

    rank, _hit = match
    return rank < int(case["max_rank"]), rank, len(results)


def _threshold_ratio(passes: int, total: int) -> float:
    return passes / total if total else 1.0


def test_lookup_quality_thresholds(real_index_file: Path, mini_index_file: Path) -> None:
    by_corpus = {"real": real_index_file, "mini": mini_index_file}
    evaluated: list[dict[str, object]] = []

    for case in CASES:
        index_dir = by_corpus[case["corpus"]]
        passed, rank, result_count = _evaluate_case(index_dir, case)
        evaluated.append({"case": case, "passed": passed, "rank": rank, "result_count": result_count})

    exact = [item for item in evaluated if item["case"]["category"] == "exact"]
    alias = [item for item in evaluated if item["case"]["category"] in {"alias", "normalized_alias"}]
    fulltext = [item for item in evaluated if item["case"]["category"] == "fulltext"]
    ambiguous = [item for item in evaluated if item["case"]["category"] == "ambiguous"]
    negative = [item for item in evaluated if item["case"]["category"] == "negative"]

    assert _threshold_ratio(sum(1 for item in exact if item["passed"]), len(exact)) == 1.0
    assert _threshold_ratio(sum(1 for item in alias if item["passed"]), len(alias)) == 1.0
    assert _threshold_ratio(sum(1 for item in fulltext if item["passed"]), len(fulltext)) >= 0.9
    assert _threshold_ratio(sum(1 for item in ambiguous if item["passed"]), len(ambiguous)) >= 0.9
    assert _threshold_ratio(sum(1 for item in negative if item["passed"]), len(negative)) == 1.0
