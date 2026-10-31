"""Build the Qdrant vector index and search it."""
import json
import uuid
from pathlib import Path

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from mevzuat_rag.chunking import CHUNKS_PATH
from mevzuat_rag.embedding import (
    EMBEDDING_DIMENSIONS,
    embed_text,
    format_document,
    format_query,
    get_client,
)

QDRANT_PATH = Path("data/qdrant")
COLLECTION = "labour_law"


def load_chunks(path: Path = CHUNKS_PATH) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file]


def point_id(chunk_id: str) -> str:
    # Qdrant ids must be integers or UUIDs; uuid5 keeps them stable between runs.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def document_title(chunk: dict) -> str:
    return f"{chunk['citation']} {chunk['title']}".strip()


def build_index(gemini: genai.Client, qdrant: QdrantClient) -> int:
    """Rebuild from scratch so the index always matches the chunk file."""
    chunks = load_chunks()
    points = []
    for number, chunk in enumerate(chunks, start=1):
        text = format_document(document_title(chunk), chunk["text"])
        points.append(
            PointStruct(id=point_id(chunk["id"]), vector=embed_text(gemini, text), payload=chunk)
        )
        if number % 25 == 0:
            print(f"embedded {number}/{len(chunks)}", flush=True)

    if qdrant.collection_exists(COLLECTION):
        qdrant.delete_collection(COLLECTION)
    qdrant.create_collection(
        COLLECTION,
        vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
    )
    qdrant.upsert(COLLECTION, points)
    return qdrant.count(COLLECTION).count


def search(
    gemini: genai.Client, qdrant: QdrantClient, question: str, limit: int = 5
) -> list[tuple[float, dict]]:
    vector = embed_text(gemini, format_query(question))
    hits = qdrant.query_points(COLLECTION, query=vector, limit=limit).points
    return [(hit.score, hit.payload) for hit in hits]


def main() -> None:
    qdrant = QdrantClient(path=str(QDRANT_PATH))
    try:
        print(f"{build_index(get_client(), qdrant)} points stored in {QDRANT_PATH}")
    finally:
        qdrant.close()


if __name__ == "__main__":
    main()
