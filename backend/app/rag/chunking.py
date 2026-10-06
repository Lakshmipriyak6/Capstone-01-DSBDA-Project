import re
from typing import Any


def normalize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = text.replace("\r", "\n")
    cleaned = cleaned.replace("\t", " ")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned.strip()


def split_sentences(text: str):
    normalized = normalize_text(text)
    if not normalized:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", normalized)
    return [sentence.strip() for sentence in sentences if sentence.strip()]


def build_document_chunks(page_texts: list[str], chunk_size: int = 700, overlap: int = 120) -> list[dict[str, Any]]:
    if not page_texts:
        return []
    if chunk_size < 1:
        raise ValueError("chunk_size must be greater than zero")

    overlap = max(0, min(overlap, chunk_size - 1))

    final_chunks: list[dict[str, Any]] = []
    for page_number, page_text in enumerate(page_texts, start=1):
        page_content = normalize_text(page_text or "")
        if not page_content:
            continue

        start = 0
        while start < len(page_content):
            limit = min(start + chunk_size, len(page_content))
            end = limit

            if limit < len(page_content):
                window = page_content[start:limit]
                sentence_boundaries = list(re.finditer(r"[.!?](?:\s+|$)", window))
                if sentence_boundaries and sentence_boundaries[-1].end() >= chunk_size // 2:
                    end = start + sentence_boundaries[-1].end()
                else:
                    whitespace = window.rfind(" ")
                    if whitespace > 0:
                        end = start + whitespace + 1

            final_chunks.append({
                "page_number": page_number,
                "text": page_content[start:end],
            })
            if end == len(page_content):
                break

            next_start = end - overlap
            if overlap and next_start > start:
                word_boundary = page_content.rfind(" ", start + 1, next_start + 1)
                if word_boundary >= start + 1:
                    next_start = word_boundary + 1
            start = max(start + 1, next_start)

    cleaned_chunks: list[dict[str, Any]] = []
    for index, chunk in enumerate(final_chunks):
        text = normalize_text(chunk["text"])
        if not text:
            continue
        cleaned_chunks.append({
            "chunk_index": index,
            "page_number": chunk["page_number"],
            "text": text,
        })

    return cleaned_chunks
