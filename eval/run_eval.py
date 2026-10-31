"""Measure retrieval and answer quality on the hand-written question set.

Usage (from the project root):
    python -m eval.run_eval                 # development split
    python -m eval.run_eval --split test --final

The test split stays locked until improvements are finished; looking at it
earlier would turn it into tuning data and inflate the reported numbers.
"""
import argparse
import json
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from qdrant_client import QdrantClient

from mevzuat_rag.answer import GENERATION_MODEL, RETRIEVAL_LIMIT, Answer, answer_question
from mevzuat_rag.embedding import EMBEDDING_MODEL, get_client
from mevzuat_rag.index import QDRANT_PATH

QUESTIONS_PATH = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")


def normalize(text: str) -> str:
    # str.lower() mishandles Turkish: "I" must become "ı" and "İ" must become "i".
    return text.replace("İ", "i").replace("I", "ı").lower()


def load_questions(split: str) -> list[dict]:
    with QUESTIONS_PATH.open(encoding="utf-8") as file:
        rows = [json.loads(line) for line in file]
    return [row for row in rows if row["split"] == split]


def recall(expected: list[str], found: list[str]) -> float:
    return sum(chunk_id in found for chunk_id in expected) / len(expected)


def reciprocal_rank(expected: list[str], retrieved: list[str]) -> float:
    for rank, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in expected:
            return 1 / rank
    return 0.0


def facts_correct(
    must_include: list[list[str]], must_not_include: list[str], answer_text: str
) -> bool:
    """Every group needs one match ("dört hafta" or "4 hafta"); no banned phrase may appear."""
    text = normalize(answer_text)
    has_facts = all(any(normalize(variant) in text for variant in group) for group in must_include)
    return has_facts and not any(normalize(phrase) in text for phrase in must_not_include)


def score_question(row: dict, answer: Answer) -> dict:
    record = {
        "id": row["id"],
        "category": row["category"],
        "question": row["question"],
        "expected_answerable": row["answerable"],
        "expected_ids": row["expected_ids"],
        "retrieved_ids": answer.retrieved_ids,
        "cited_ids": answer.cited_ids,
        "system_answered": answer.answerable,
        "answer": answer.text,
        "unanswered_parts": answer.unanswered_parts,
        # Filled in by a human: phrase checks cannot catch a distorted rule.
        "manual_grade": None,
        "manual_note": "",
    }
    if row["answerable"]:
        expected = row["expected_ids"]
        record["recall_at_k"] = recall(expected, answer.retrieved_ids)
        record["reciprocal_rank"] = reciprocal_rank(expected, answer.retrieved_ids)
        record["citation_recall"] = recall(expected, answer.cited_ids)
        record["facts_correct"] = answer.answerable and facts_correct(
            row["must_include"], row.get("must_not_include", []), answer.text
        )
    else:
        record["correctly_refused"] = not answer.answerable
    return record


def mean(values: list[float]) -> float | None:
    # None, not 0: an empty group has no score, which is different from scoring zero.
    return round(sum(values) / len(values), 3) if values else None


def summarize(records: list[dict]) -> dict:
    answerable = [r for r in records if r["expected_answerable"]]
    unanswerable = [r for r in records if not r["expected_answerable"]]
    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in answerable:
        by_category[record["category"]].append(record)

    return {
        "questions": len(records),
        "answerable_questions": len(answerable),
        "unanswerable_questions": len(unanswerable),
        f"recall_at_{RETRIEVAL_LIMIT}": mean([r["recall_at_k"] for r in answerable]),
        "mrr": mean([r["reciprocal_rank"] for r in answerable]),
        "fact_accuracy": mean([r["facts_correct"] for r in answerable]),
        "citation_recall": mean([r["citation_recall"] for r in answerable]),
        "false_refusal_rate": mean([not r["system_answered"] for r in answerable]),
        "correct_refusal_rate": mean([r["correctly_refused"] for r in unanswerable]),
        "fact_accuracy_by_category": {
            category: mean([r["facts_correct"] for r in rows])
            for category, rows in sorted(by_category.items())
        },
    }


def review_summary(path: Path) -> dict:
    """Count hand-written grades (correct, incomplete, wrong) in a result file."""
    report = json.loads(path.read_text(encoding="utf-8"))
    grades = [record["manual_grade"] for record in report["records"]]
    return {
        grade or "ungraded": grades.count(grade)
        for grade in sorted(set(grades), key=lambda value: value or "")
    }


def git_state() -> dict:
    """Record the code version so a result can be traced back to what produced it."""

    def run(*args: str) -> str:
        return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()

    return {
        "commit": run("git", "rev-parse", "--short", "HEAD"),
        "uncommitted_changes": bool(run("git", "status", "--porcelain", "--", "mevzuat_rag", "eval")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--final", action="store_true", help="unlock the test split")
    parser.add_argument("--label", default="baseline", help="name of the configuration")
    parser.add_argument("--review", type=Path, help="print the manual grades of a result file")
    args = parser.parse_args()
    if args.review:
        print(json.dumps(review_summary(args.review), ensure_ascii=False, indent=2))
        return
    if args.split == "test" and not args.final:
        parser.error("the test split is locked; pass --final only for the final measurement")

    questions = load_questions(args.split)
    gemini = get_client()
    qdrant = QdrantClient(path=str(QDRANT_PATH))
    records = []
    try:
        for number, row in enumerate(questions, start=1):
            records.append(score_question(row, answer_question(gemini, qdrant, row["question"])))
            print(f"{number}/{len(questions)} {row['id']}", flush=True)
    finally:
        qdrant.close()

    created_at = datetime.now().astimezone()
    report = {
        "label": args.label,
        "split": args.split,
        "created_at": created_at.isoformat(timespec="seconds"),
        "config": {
            "embedding_model": EMBEDDING_MODEL,
            "generation_model": GENERATION_MODEL,
            "retrieval_limit": RETRIEVAL_LIMIT,
        },
        "git": git_state(),
        "summary": summarize(records),
        "records": records,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    target = RESULTS_DIR / f"{created_at:%Y%m%d-%H%M%S}-{args.split}-{args.label}.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Saved to {target}")


if __name__ == "__main__":
    main()
