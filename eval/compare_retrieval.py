"""Compare retrieval methods and chunk sizes on the dev split.

Only retrieval is measured, so no answers are generated. Usage:
    python -m eval.compare_retrieval
"""
import json
import math
import re
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from eval.run_eval import RESULTS_DIR, git_state, load_questions, normalize, recall, reciprocal_rank
from mevzuat_rag.embedding import embed_text, format_document, format_query, get_client
from mevzuat_rag.index import document_title, load_chunks

EMBEDDINGS_CACHE = Path("data/experiments/embeddings.json")
SPLIT_THRESHOLD = 1500  # articles longer than this many characters are divided
SPLIT_TARGET = 1200
CUTOFFS = (3, 5, 8)
RRF_K = 60
BM25_K1 = 1.5
BM25_B = 0.75
# Turkish adds suffixes to words, so "izni" and "iznin" would never match exactly.
# Keeping the first letters is a simple way to treat them as the same word.
STEM_LENGTH = 5

Ranker = Callable[[str], list[str]]


def tokenize(text: str) -> list[str]:
    return [word[:STEM_LENGTH] for word in re.findall(r"[a-zçğıöşü0-9]+", normalize(text))]


def split_article(chunk: dict) -> list[dict]:
    """Divide a long article at sentence ends, repeating one sentence for context."""
    if len(chunk["text"]) <= SPLIT_THRESHOLD:
        return [{"piece_id": chunk["id"], "parent": chunk, "text": chunk["text"]}]

    sentences = re.split(r"(?<=[.:;])\s+", chunk["text"])
    groups: list[list[str]] = [[]]
    for sentence in sentences:
        if groups[-1] and sum(map(len, groups[-1])) + len(sentence) > SPLIT_TARGET:
            groups.append([groups[-1][-1]])
        groups[-1].append(sentence)
    return [
        {"piece_id": f"{chunk['id']}#{index}", "parent": chunk, "text": " ".join(group)}
        for index, group in enumerate(groups)
    ]


def embed_cached(texts: dict[str, str]) -> dict[str, list[float]]:
    """Reuse saved vectors so that repeating the experiment costs no extra API calls."""
    cache = json.loads(EMBEDDINGS_CACHE.read_text()) if EMBEDDINGS_CACHE.exists() else {}
    client = get_client()
    for key, text in texts.items():
        if key not in cache:
            cache[key] = embed_text(client, text)
    EMBEDDINGS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    EMBEDDINGS_CACHE.write_text(json.dumps(cache))
    return cache


def dedupe_parents(piece_ids: list[str]) -> list[str]:
    """Several pieces of one article count once, at the rank of the best piece."""
    return list(dict.fromkeys(piece_id.split("#")[0] for piece_id in piece_ids))


def dense_ranker(pieces: list[dict], vectors: dict) -> Ranker:
    def rank(question: str) -> list[str]:
        query = vectors[f"query:{question}"]
        scored = [
            (sum(a * b for a, b in zip(query, vectors[f"doc:{p['piece_id']}"])), p["piece_id"])
            for p in pieces
        ]
        return dedupe_parents([piece_id for _, piece_id in sorted(scored, reverse=True)])

    return rank


def bm25_ranker(pieces: list[dict]) -> Ranker:
    documents = {
        p["piece_id"]: Counter(tokenize(f"{document_title(p['parent'])} {p['text']}"))
        for p in pieces
    }
    lengths = {key: sum(counts.values()) for key, counts in documents.items()}
    average_length = sum(lengths.values()) / len(lengths)
    document_frequency = Counter(word for counts in documents.values() for word in counts)

    def score(key: str, query_words: list[str]) -> float:
        total = 0.0
        for word in query_words:
            frequency = documents[key][word]
            matches = document_frequency[word]
            idf = math.log(1 + (len(documents) - matches + 0.5) / (matches + 0.5))
            norm = BM25_K1 * (1 - BM25_B + BM25_B * lengths[key] / average_length)
            total += idf * frequency * (BM25_K1 + 1) / (frequency + norm)
        return total

    def rank(question: str) -> list[str]:
        query_words = tokenize(question)
        ordered = sorted(documents, key=lambda key: score(key, query_words), reverse=True)
        return dedupe_parents(ordered)

    return rank


def hybrid_ranker(first: Ranker, second: Ranker) -> Ranker:
    """Reciprocal Rank Fusion: reward articles ranked high by either method."""

    def rank(question: str) -> list[str]:
        scores: Counter[str] = Counter()
        for ranking in (first(question), second(question)):
            for position, chunk_id in enumerate(ranking, start=1):
                scores[chunk_id] += 1 / (RRF_K + position)
        return [chunk_id for chunk_id, _ in scores.most_common()]

    return rank


def evaluate(rank: Ranker, questions: list[dict]) -> dict:
    rankings = {row["id"]: rank(row["question"]) for row in questions}
    metrics: dict = {}
    for cutoff in CUTOFFS:
        scores = [recall(r["expected_ids"], rankings[r["id"]][:cutoff]) for r in questions]
        metrics[f"recall_at_{cutoff}"] = round(sum(scores) / len(scores), 3)
    reciprocal = [reciprocal_rank(r["expected_ids"], rankings[r["id"]]) for r in questions]
    metrics["mrr"] = round(sum(reciprocal) / len(reciprocal), 3)
    metrics["not_first"] = [
        row["id"]
        for row, value in zip(questions, reciprocal)
        if value < 1
    ]
    return metrics


def main() -> None:
    questions = [row for row in load_questions("dev") if row["answerable"]]
    chunks = load_chunks()
    whole = [{"piece_id": c["id"], "parent": c, "text": c["text"]} for c in chunks]
    split = [piece for chunk in chunks for piece in split_article(chunk)]

    texts = {
        f"doc:{piece['piece_id']}": format_document(document_title(piece["parent"]), piece["text"])
        for piece in [*whole, *split]
    }
    texts |= {f"query:{row['question']}": format_query(row["question"]) for row in questions}
    vectors = embed_cached(texts)

    dense_whole, bm25_whole = dense_ranker(whole, vectors), bm25_ranker(whole)
    dense_split, bm25_split = dense_ranker(split, vectors), bm25_ranker(split)
    methods = {
        "dense_whole_articles": dense_whole,
        "bm25_whole_articles": bm25_whole,
        "hybrid_whole_articles": hybrid_ranker(dense_whole, bm25_whole),
        "dense_split_articles": dense_split,
        "bm25_split_articles": bm25_split,
        "hybrid_split_articles": hybrid_ranker(dense_split, bm25_split),
    }
    results = {name: evaluate(rank, questions) for name, rank in methods.items()}

    created_at = datetime.now().astimezone()
    report = {
        "split": "dev",
        "created_at": created_at.isoformat(timespec="seconds"),
        "questions": len(questions),
        "pieces": {"whole": len(whole), "split": len(split)},
        "split_settings": {"threshold": SPLIT_THRESHOLD, "target": SPLIT_TARGET},
        "git": git_state(),
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    target = RESULTS_DIR / f"{created_at:%Y%m%d-%H%M%S}-dev-retrieval-comparison.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, metrics in results.items():
        print(f"{name:24} {metrics}")
    print(f"pieces: {report['pieces']}\nSaved to {target}")


if __name__ == "__main__":
    main()
