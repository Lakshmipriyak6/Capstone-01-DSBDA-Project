from app.rag.chunking import build_document_chunks, normalize_text


def _merge_overlapping_words(chunks):
    merged = chunks[0]["text"].split()
    for chunk in chunks[1:]:
        words = chunk["text"].split()
        overlap = max(
            (
                size
                for size in range(1, min(len(merged), len(words)) + 1)
                if merged[-size:] == words[:size]
            ),
            default=0,
        )
        merged.extend(words[overlap:])
    return merged


def _merge_overlapping_text(chunks):
    merged = chunks[0]["text"]
    for chunk in chunks[1:]:
        text = chunk["text"]
        overlap = max(
            (
                size
                for size in range(1, min(len(merged), len(text)) + 1)
                if merged[-size:] == text[:size]
            ),
            default=0,
        )
        merged += text[overlap:]
    return merged


def test_normal_text_chunks_preserve_content_and_size():
    text = "Alpha starts here. Beta follows next. Gamma finishes the passage."

    chunks = build_document_chunks([text], chunk_size=32, overlap=8)

    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 32 for chunk in chunks)
    assert _merge_overlapping_words(chunks) == normalize_text(text).split()


def test_oversized_sentence_is_split_without_losing_words():
    words = [f"token{index}" for index in range(35)]
    text = " ".join(words) + "."

    chunks = build_document_chunks([text], chunk_size=40, overlap=12)

    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 40 for chunk in chunks)
    assert _merge_overlapping_words(chunks) == normalize_text(text).split()


def test_chunks_retain_overlap_between_adjacent_windows():
    text = "one two three four five six seven eight nine ten eleven twelve"

    chunks = build_document_chunks([text], chunk_size=25, overlap=8)

    assert len(chunks) > 1
    for previous, following in zip(chunks, chunks[1:]):
        previous_words = previous["text"].split()
        following_words = following["text"].split()
        assert any(
            previous_words[-size:] == following_words[:size]
            for size in range(1, min(len(previous_words), len(following_words)) + 1)
        )


def test_long_unbroken_token_is_split_without_stalling():
    text = "abcdefghijklmnopqrstuvwxyz0123456789" * 3

    chunks = build_document_chunks([text], chunk_size=24, overlap=6)

    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 24 for chunk in chunks)
    assert _merge_overlapping_text(chunks) == text