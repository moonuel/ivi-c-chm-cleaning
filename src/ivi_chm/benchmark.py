from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .indexer import search
from .parser import DocRecord, parse_document


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_FILE = ROOT / "benchmarks" / "ivi_docs_benchmark.json"
SECTION_ORDER = ("remarks", "requirements", "commands", "parameters")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "use",
    "what",
    "which",
    "with",
}


@dataclass(slots=True)
class BenchmarkSpan:
    file: str
    start: int
    end: int


@dataclass(slots=True)
class BenchmarkGold:
    source_files: list[str]
    answer_spans: list[BenchmarkSpan]


@dataclass(slots=True)
class BenchmarkQuestion:
    id: str
    category: str
    question: str
    gold: BenchmarkGold
    acceptance: dict[str, list[str]]


@dataclass(slots=True)
class CorpusSnapshot:
    root: str
    file_count: int
    sha256: str


@dataclass(slots=True)
class RunResult:
    question_id: str
    system: str
    timestamp: float
    runtime_ms: float
    tool_calls: int
    retrieved_sources: list[str]
    final_answer_text: str
    evidence_snippets: list[str]
    failure_reason: str
    score: int
    source_precision: float
    source_recall: float
    evidence_overlap: bool


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token and token not in STOPWORDS]


def _first_words(text: str, limit: int) -> str:
    words = [word for word in re.findall(r"[A-Za-z0-9']+", text) if word]
    return " ".join(words[:limit]).strip()


def _window(lines: list[str], line_no: int, size: int = 1) -> tuple[int, int]:
    start = max(1, line_no - size)
    end = min(len(lines), line_no + size)
    return start, end


def _locate_span(path: Path, needles: list[str]) -> BenchmarkSpan:
    lines = path.read_text(encoding="utf-8").splitlines()
    lowered = [line.lower() for line in lines]
    for needle in needles:
        needle = needle.strip().lower()
        if not needle:
            continue
        for idx, line in enumerate(lowered, start=1):
            if needle in line:
                start, end = _window(lines, idx)
                return BenchmarkSpan(file=str(path), start=start, end=end)
    return BenchmarkSpan(file=str(path), start=1, end=min(len(lines), 3))


def _iter_html_paths(html_dir: str | Path) -> list[Path]:
    html_dir = Path(html_dir)
    return sorted(html_dir.glob("*.html"))


def freeze_corpus(html_dir: str | Path) -> CorpusSnapshot:
    paths = _iter_html_paths(html_dir)
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return CorpusSnapshot(root=str(Path(html_dir)), file_count=len(paths), sha256=digest.hexdigest())


def _doc_text(record: DocRecord) -> str:
    parts = [record.title, record.summary, record.abstract, record.prototype, record.remarks, record.commands, record.requirements, record.function_tree_node, " ".join(record.keywords)]
    return " ".join(part for part in parts if part)


def _load_docs(html_dir: str | Path) -> list[tuple[Path, DocRecord]]:
    docs: list[tuple[Path, DocRecord]] = []
    for path in _iter_html_paths(html_dir):
        docs.append((path, parse_document(path)))
    return docs


def _section_candidates(record: DocRecord) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    if record.remarks:
        candidates.append(("remarks", record.remarks))
    if record.requirements:
        candidates.append(("requirements", record.requirements))
    if record.commands:
        candidates.append(("commands", record.commands))
    if record.parameters:
        first = record.parameters[0].description.strip()
        if first:
            candidates.append(("parameters", first))
    return candidates


def _related_symbol_map(docs: list[tuple[Path, DocRecord]]) -> dict[str, tuple[Path, DocRecord]]:
    mapping: dict[str, tuple[Path, DocRecord]] = {}
    for path, record in docs:
        mapping[path.stem] = (path, record)
        mapping[record.symbol] = (path, record)
        mapping[_normalize(record.symbol)] = (path, record)
        mapping[_normalize(path.stem)] = (path, record)
    return mapping


def _build_exact_questions(docs: list[tuple[Path, DocRecord]], count: int) -> list[BenchmarkQuestion]:
    questions: list[BenchmarkQuestion] = []
    for path, record in docs:
        if not record.symbol:
            continue
        question = f"Which page documents {record.symbol}?"
        questions.append(
            BenchmarkQuestion(
                id=f"exact-{len(questions) + 1:03d}",
                category="exact_lookup",
                question=question,
                gold=BenchmarkGold(
                    source_files=[str(path)],
                    answer_spans=[_locate_span(path, [record.symbol, record.title])],
                ),
                acceptance={"must_contain": [record.symbol], "must_not_contain": ["unsupported speculation"]},
            )
        )
        if len(questions) == count:
            return questions
    raise ValueError("not enough exact lookup candidates in corpus")


def _build_section_questions(docs: list[tuple[Path, DocRecord]], count: int) -> list[BenchmarkQuestion]:
    questions: list[BenchmarkQuestion] = []
    for path, record in docs:
        for section_name, section_text in _section_candidates(record):
            phrase = _first_words(section_text, 8)
            if not phrase:
                continue
            question = f"Which page explains {section_name} guidance about {phrase}?"
            questions.append(
                BenchmarkQuestion(
                    id=f"section-{len(questions) + 1:03d}",
                    category="section_location",
                    question=question,
                    gold=BenchmarkGold(
                        source_files=[str(path)],
                        answer_spans=[_locate_span(path, [phrase, section_name])],
                    ),
                    acceptance={"must_contain": [term for term in _tokens(phrase)[:3]], "must_not_contain": ["unsupported speculation"]},
                )
            )
            if len(questions) == count:
                return questions
    raise ValueError("not enough section-location candidates in corpus")


def _build_multi_hop_questions(docs: list[tuple[Path, DocRecord]], count: int) -> list[BenchmarkQuestion]:
    by_symbol = _related_symbol_map(docs)
    questions: list[BenchmarkQuestion] = []
    for path, record in docs:
        for ref in record.see_also:
            related = by_symbol.get(Path(ref.get("href", "")).stem)
            if not related:
                continue
            related_path, related_record = related
            related_symbol = related_record.symbol or related_path.stem
            question = f"Which page documents {record.symbol} and also points to {related_symbol}?"
            questions.append(
                BenchmarkQuestion(
                    id=f"multi-hop-{len(questions) + 1:03d}",
                    category="multi_hop_synthesis",
                    question=question,
                    gold=BenchmarkGold(
                        source_files=[str(path), str(related_path)],
                        answer_spans=[_locate_span(path, [record.symbol, record.title]), _locate_span(related_path, [related_symbol, related_record.title])],
                    ),
                    acceptance={"must_contain": [record.symbol, related_symbol], "must_not_contain": ["unsupported speculation"]},
                )
            )
            if len(questions) == count:
                return questions
    raise ValueError("not enough multi-hop candidates in corpus")


def _build_paraphrase_questions(docs: list[tuple[Path, DocRecord]], count: int) -> list[BenchmarkQuestion]:
    questions: list[BenchmarkQuestion] = []
    for path, record in docs:
        source_text = record.summary or record.abstract or record.title
        phrase = _first_words(source_text, 10)
        if not phrase:
            continue
        question = f"Which page discusses {phrase}?"
        questions.append(
            BenchmarkQuestion(
                id=f"paraphrase-{len(questions) + 1:03d}",
                category="paraphrase_semantic_match",
                question=question,
                gold=BenchmarkGold(
                    source_files=[str(path)],
                    answer_spans=[_locate_span(path, [phrase, record.title])],
                ),
                acceptance={"must_contain": [term for term in _tokens(phrase)[:4]], "must_not_contain": ["unsupported speculation"]},
            )
        )
        if len(questions) == count:
            return questions
    raise ValueError("not enough paraphrase candidates in corpus")


def generate_benchmark_questions(html_dir: str | Path, per_category: int = 25) -> dict[str, Any]:
    docs = _load_docs(html_dir)
    snapshot = freeze_corpus(html_dir)
    questions = (
        _build_exact_questions(docs, per_category)
        + _build_section_questions(docs, per_category)
        + _build_multi_hop_questions(docs, per_category)
        + _build_paraphrase_questions(docs, per_category)
    )
    payload = {
        "corpus": asdict(snapshot),
        "question_count": len(questions),
        "questions": [
            {
                "id": item.id,
                "category": item.category,
                "question": item.question,
                "gold": {
                    "source_files": item.gold.source_files,
                    "answer_spans": [asdict(span) for span in item.gold.answer_spans],
                },
                "acceptance": item.acceptance,
            }
            for item in questions
        ],
    }
    return payload


def write_benchmark_questions(html_dir: str | Path, output_file: str | Path = DEFAULT_BENCHMARK_FILE) -> dict[str, Any]:
    payload = generate_benchmark_questions(html_dir)
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_benchmark_questions(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _word_match_ratio(text: str, terms: list[str]) -> float:
    if not terms:
        return 1.0
    haystack = _normalize(text)
    return sum(1 for term in terms if term and term in haystack) / len(terms)


def _match_source(gold_sources: list[str], retrieved_sources: list[str]) -> tuple[float, float, int]:
    gold = set(gold_sources)
    if not retrieved_sources:
        return 0.0, 0.0, 0
    hits = sum(1 for source in retrieved_sources if source in gold)
    precision = hits / len(retrieved_sources)
    recall = hits / len(gold) if gold else 1.0
    return precision, recall, hits


def _span_overlaps(gold_spans: list[dict[str, Any]], candidate: BenchmarkSpan) -> bool:
    for span in gold_spans:
        if span["file"] != candidate.file:
            continue
        if candidate.end >= int(span["start"]) and candidate.start <= int(span["end"]):
            return True
    return False


def _candidate_span(result: dict[str, Any]) -> BenchmarkSpan:
    source_path = Path(result.get("source_path", ""))
    snippet = str(result.get("snippet", "")).strip()
    if source_path.exists() and snippet:
        lines = source_path.read_text(encoding="utf-8").splitlines()
        lowered = [line.lower() for line in lines]
        needle = snippet.lower()[:80]
        for idx, line in enumerate(lowered, start=1):
            if needle and needle in line:
                start, end = _window(lines, idx, size=1)
                return BenchmarkSpan(file=str(source_path), start=start, end=end)
    if source_path.exists():
        return _locate_span(source_path, [str(result.get("title", "")), str(result.get("symbol", ""))])
    return BenchmarkSpan(file=str(source_path), start=1, end=1)


def _run_skill(index_file: str | Path, question: BenchmarkQuestion) -> tuple[list[dict[str, Any]], str, int, str]:
    start = time.perf_counter()
    results = search(index_file, question.question, limit=10)
    runtime_ms = (time.perf_counter() - start) * 1000
    answer = results[0]["summary"] if results else ""
    failure = "" if results else "no results"
    return results, answer, 1, failure, runtime_ms


def _run_grep(html_dir: str | Path, question: BenchmarkQuestion) -> tuple[list[dict[str, Any]], str, int, str, float]:
    start = time.perf_counter()
    docs = _load_docs(html_dir)
    terms = _tokens(question.question)
    scored: list[tuple[int, Path, DocRecord]] = []
    for path, record in docs:
        haystack = _normalize(_doc_text(record) + " " + path.read_text(encoding="utf-8"))
        score = sum(haystack.count(term) for term in terms)
        if score:
            scored.append((score, path, record))
    scored.sort(key=lambda item: (-item[0], item[2].symbol, item[1].name))
    results: list[dict[str, Any]] = []
    for _score, path, record in scored[:10]:
        snippet = record.summary or record.abstract or record.title or path.name
        results.append(
            {
                "symbol": record.symbol,
                "kind": record.kind,
                "title": record.title,
                "summary": record.summary or record.abstract,
                "source_path": str(path),
                "snippet": snippet[:220],
                "matched_on": "grep",
            }
        )
    answer = results[0]["snippet"] if results else ""
    failure = "" if results else "no results"
    runtime_ms = (time.perf_counter() - start) * 1000
    return results, answer, 1, failure, runtime_ms


def _score_run(question: BenchmarkQuestion, result: dict[str, Any], retrieved_sources: list[str]) -> tuple[int, float, float, bool]:
    gold_sources = question.gold.source_files
    precision, recall, hits = _match_source(gold_sources, retrieved_sources)
    if hits == 0:
        return 0, precision, recall, False

    top_source = retrieved_sources[0] if retrieved_sources else ""
    top_match = top_source in set(gold_sources)
    candidate_text = " ".join([str(result.get("title", "")), str(result.get("summary", "")), str(result.get("snippet", ""))])
    acceptance_terms = question.acceptance.get("must_contain", [])
    acceptance_ok = _word_match_ratio(candidate_text, acceptance_terms) == 1.0
    evidence_overlap = _span_overlaps([asdict(span) for span in question.gold.answer_spans], _candidate_span(result))

    score = 1
    if top_match:
        score = 2
    if evidence_overlap:
        score = 3
    if acceptance_ok:
        score = 4
    if top_match and evidence_overlap and acceptance_ok and recall == 1.0:
        score = 5
    return score, precision, recall, evidence_overlap


def _build_run_result(question: BenchmarkQuestion, system: str, results: list[dict[str, Any]], answer: str, tool_calls: int, failure_reason: str, runtime_ms: float) -> RunResult:
    retrieved_sources = [str(hit.get("source_path", "")) for hit in results if hit.get("source_path")]
    top_hit = results[0] if results else {"source_path": "", "snippet": "", "title": "", "summary": ""}
    score, precision, recall, evidence_overlap = _score_run(question, top_hit, retrieved_sources)
    return RunResult(
        question_id=question.id,
        system=system,
        timestamp=time.time(),
        runtime_ms=runtime_ms,
        tool_calls=tool_calls,
        retrieved_sources=retrieved_sources,
        final_answer_text=answer,
        evidence_snippets=[str(hit.get("snippet", "")) for hit in results[:3] if hit.get("snippet")],
        failure_reason=failure_reason,
        score=score,
        source_precision=precision,
        source_recall=recall,
        evidence_overlap=evidence_overlap,
    )


def run_benchmark(html_dir: str | Path, index_file: str | Path, questions_file: str | Path = DEFAULT_BENCHMARK_FILE, systems: tuple[str, ...] = ("skill", "grep")) -> dict[str, Any]:
    payload = load_benchmark_questions(questions_file)
    questions = [
        BenchmarkQuestion(
            id=item["id"],
            category=item["category"],
            question=item["question"],
            gold=BenchmarkGold(
                source_files=list(item["gold"]["source_files"]),
                answer_spans=[BenchmarkSpan(**span) for span in item["gold"]["answer_spans"]],
            ),
            acceptance={key: list(value) for key, value in item.get("acceptance", {}).items()},
        )
        for item in payload["questions"]
    ]
    runs: list[RunResult] = []
    for question in questions:
        if "skill" in systems:
            results, answer, tool_calls, failure_reason, runtime_ms = _run_skill(index_file, question)
            runs.append(_build_run_result(question, "skill", results, answer, tool_calls, failure_reason, runtime_ms))
        if "grep" in systems:
            results, answer, tool_calls, failure_reason, runtime_ms = _run_grep(html_dir, question)
            runs.append(_build_run_result(question, "grep", results, answer, tool_calls, failure_reason, runtime_ms))

    grouped: dict[str, list[RunResult]] = {system: [run for run in runs if run.system == system] for system in systems}
    summary: dict[str, Any] = {
        "corpus": payload["corpus"],
        "question_count": len(questions),
        "systems": {},
    }
    for system, system_runs in grouped.items():
        if not system_runs:
            continue
        summary["systems"][system] = {
            "average_score": sum(run.score for run in system_runs) / len(system_runs),
            "median_latency_ms": sorted(run.runtime_ms for run in system_runs)[len(system_runs) // 2],
            "source_precision": sum(run.source_precision for run in system_runs) / len(system_runs),
            "source_recall": sum(run.source_recall for run in system_runs) / len(system_runs),
            "failure_rate": sum(1 for run in system_runs if run.failure_reason) / len(system_runs),
        }
    summary["runs"] = [asdict(run) for run in runs]
    return summary


def format_report(report: dict[str, Any]) -> str:
    lines = [
        f"corpus_hash: {report['corpus']['sha256']}",
        f"questions: {report['question_count']}",
    ]
    for system, stats in report.get("systems", {}).items():
        lines.append(
            f"{system}: score={stats['average_score']:.2f} precision={stats['source_precision']:.2f} recall={stats['source_recall']:.2f} latency_ms={stats['median_latency_ms']:.1f} failure_rate={stats['failure_rate']:.2%}"
        )
    return "\n".join(lines)
