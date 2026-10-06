import json
from typing import Any

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
MINIMUM_SIMILARITY = 0.15
_embedding_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    vectors = _get_embedding_model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32).reshape(len(texts), EMBEDDING_DIMENSION).tolist()


def embed_chunk_text(text: str) -> list[float]:
    if not text or not text.strip():
        return []
    return embed_texts([text])[0]


def _chunk_embedding(chunk: Any) -> list[float] | None:
    raw = getattr(chunk, "embedding", None)
    if not raw and isinstance(chunk, dict):
        raw = chunk.get("embedding")
    if not raw:
        return None
    try:
        vector = json.loads(raw) if isinstance(raw, str) else raw
        if len(vector) != EMBEDDING_DIMENSION:
            return None
        return [float(value) for value in vector]
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def retrieve_relevant_chunks(
    question: str,
    chunks: list[Any],
    top_k: int = 4,
    minimum_similarity: float = MINIMUM_SIMILARITY,
) -> list[tuple[float, Any]]:
    if not question or not question.strip() or not chunks or top_k < 1:
        return []

    valid_vectors = [_chunk_embedding(chunk) for chunk in chunks]
    missing_indices = [index for index, vector in enumerate(valid_vectors) if vector is None]
    if missing_indices:
        missing_texts = [
            getattr(chunks[index], "chunk_text", None)
            or (chunks[index].get("text", "") if isinstance(chunks[index], dict) else "")
            for index in missing_indices
        ]
        regenerated = embed_texts(missing_texts)
        for index, vector in zip(missing_indices, regenerated):
            valid_vectors[index] = vector
            if hasattr(chunks[index], "embedding"):
                chunks[index].embedding = serialize_embedding(vector)
            elif isinstance(chunks[index], dict):
                chunks[index]["embedding"] = serialize_embedding(vector)

    usable = [(index, vector) for index, vector in enumerate(valid_vectors) if vector is not None]
    if not usable:
        return []

    matrix = np.ascontiguousarray([vector for _, vector in usable], dtype=np.float32)
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(EMBEDDING_DIMENSION)
    index.add(matrix)

    query_vector = np.ascontiguousarray(embed_texts([question]), dtype=np.float32)
    faiss.normalize_L2(query_vector)
    scores, positions = index.search(query_vector, min(top_k, len(usable)))

    ranked: list[tuple[float, Any]] = []
    for score, position in zip(scores[0], positions[0]):
        if position < 0 or float(score) < minimum_similarity:
            continue
        original_index = usable[int(position)][0]
        ranked.append((float(score), chunks[original_index]))
    return ranked


def serialize_embedding(values: list[float]) -> str | None:
    if not values:
        return None
    return json.dumps([float(value) for value in values])
