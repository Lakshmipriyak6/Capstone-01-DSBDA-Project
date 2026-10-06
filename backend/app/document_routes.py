import json
import io
import os
import re
from datetime import datetime
import time
from collections import Counter

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage, Document, DocumentChunk, User
from app.rag.answering import generate_answer, generate_document_summary, generate_suggested_questions
from app.rag.chunking import build_document_chunks
from app.rag.embeddings import embed_texts, retrieve_relevant_chunks, serialize_embedding
from app.schemas import AskRequest, AskResponse, ChatMessageOut, DashboardStats, DocumentChunkOut, DocumentDetailOut, DocumentOut, SourceReference, SummaryResponse
from app.security import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

BASE_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(10 * 1024 * 1024)))
os.makedirs(BASE_UPLOAD_DIR, exist_ok=True)


def extract_pdf_text(file_path: str) -> tuple[str, list[str]]:
    reader = PdfReader(file_path)
    page_texts = []
    text_parts = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        cleaned_page = clean_text(page_text)
        page_texts.append(cleaned_page)
        if cleaned_page:
            text_parts.append(cleaned_page)
    return "\n\n".join(text_parts), page_texts


def clean_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_document_by_id(db: Session, current_user: User, document_id: int):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return None
    if document.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this document")
    return document


def _serialize_chunk(chunk: DocumentChunk):
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "text": chunk.chunk_text,
        "created_at": chunk.created_at,
    }


def _index_document_chunks(db: Session, document: Document) -> list[DocumentChunk]:
    if not document.extracted_text:
        document.processing_status = "empty"
        db.commit()
        return []
    start_ts = time.perf_counter()
    page_texts = json.loads(document.page_texts) if document.page_texts else [document.extracted_text]
    chunk_definitions = build_document_chunks(page_texts, chunk_size=700, overlap=120)
    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    chunk_embeddings = embed_texts([chunk["text"] for chunk in chunk_definitions])

    stored_chunks: list[DocumentChunk] = []
    for chunk_index, (chunk, embedding) in enumerate(zip(chunk_definitions, chunk_embeddings)):
        chunk_model = DocumentChunk(
            document_id=document.id,
            page_number=chunk["page_number"],
            chunk_index=chunk_index,
            chunk_text=chunk["text"],
            embedding=serialize_embedding(embedding),
            created_at=datetime.utcnow(),
        )
        db.add(chunk_model)
        stored_chunks.append(chunk_model)

    document.processing_status = "processed"
    # document-level analytics
    text = document.extracted_text or ""
    paragraphs = [p for p in re.split(r"\n{2,}", text) if p.strip()]
    paragraph_count = len(paragraphs)
    # sentence stats
    from app.rag.chunking import split_sentences
    sentences = split_sentences(text)
    avg_sentence_length = 0.0
    if sentences:
        lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences]
        avg_sentence_length = float(sum(lengths)) / max(1, len(lengths))

    # top terms (simple frequency, exclude stopwords)
    tokens = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower())
    stop_words = {"the","and","for","with","that","this","from","are","was","were","will","have","has","had","not","but","you","your","about","can","all","which","when","what","where","who","why","how","document","documents"}
    filtered = [t for t in tokens if t not in stop_words]
    term_counts = Counter(filtered)
    top_terms = [t for t, _ in term_counts.most_common(20)]

    # simple category heuristic
    category = None
    lowered = text.lower()
    if any(word in lowered for word in ["abstract", "introduction", "method", "results", "discussion"]):
        category = "Research Paper"
    elif any(word in lowered for word in ["resume", "curriculum vitae", "cv", "experience"]):
        category = "Resume"
    elif any(word in lowered for word in ["report", "project", "conclusion", "recommendation"]):
        category = "Project Report"
    else:
        category = "Other"

    end_ts = time.perf_counter()
    processing_time_ms = int((end_ts - start_ts) * 1000)

    summary_data = generate_document_summary(document.extracted_text)
    document.summary = summary_data["executive_summary"]
    document.paragraph_count = paragraph_count
    document.avg_sentence_length = avg_sentence_length
    document.top_terms = json.dumps(top_terms)
    document.category = category
    document.processing_time_ms = processing_time_ms
    db.commit()
    return stored_chunks


@router.get("", response_model=list[DocumentOut])
def list_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = db.query(Document).filter(Document.user_id == current_user.id).order_by(Document.upload_date.desc()).all()
    return documents


@router.get("/stats", response_model=DashboardStats)
def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    documents = db.query(Document).filter(Document.user_id == current_user.id).all()
    total_documents = len(documents)
    total_pages = sum(doc.page_count for doc in documents)
    total_words = sum(doc.word_count for doc in documents)
    total_questions = db.query(ChatMessage).filter(ChatMessage.user_id == current_user.id).count()

    return {
        "total_documents": total_documents,
        "total_pages": total_pages,
        "total_words": total_words,
        "total_questions": total_questions,
    }


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document_detail(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    extracted_text = document.extracted_text or ""
    if document.extracted_text_path and os.path.exists(document.extracted_text_path):
        with open(document.extracted_text_path, "r", encoding="utf-8") as file:
            extracted_text = file.read()

    return {
        "id": document.id,
        "user_id": document.user_id,
        "filename": document.filename,
        "title": document.title,
        "page_count": document.page_count,
        "word_count": document.word_count,
        "char_count": document.char_count,
        "file_size_bytes": document.file_size_bytes,
        "processing_status": document.processing_status,
        "upload_date": document.upload_date,
        "summary": document.summary,
        "extracted_text": extracted_text,
        "page_texts": document.page_texts,
    }


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    original_filename = os.path.basename(file.filename.replace("\\", "/"))
    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_content = await file.read(MAX_UPLOAD_SIZE_BYTES + 1)
    if len(file_content) > MAX_UPLOAD_SIZE_BYTES:
        maximum_size_mib = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"PDF exceeds the maximum upload size of {maximum_size_mib:g} MiB",
        )
    if not file_content:
        raise HTTPException(status_code=400, detail="PDF file is empty")
    if b"%PDF-" not in file_content[:1024]:
        raise HTTPException(status_code=400, detail="Uploaded file does not have a valid PDF signature")

    try:
        pdf_reader = PdfReader(io.BytesIO(file_content))
        if len(pdf_reader.pages) == 0:
            raise HTTPException(status_code=400, detail="PDF contains no pages")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="PDF file is malformed or unreadable") from exc

    user_upload_dir = os.path.join(BASE_UPLOAD_DIR, str(current_user.id))
    os.makedirs(user_upload_dir, exist_ok=True)

    safe_filename = f"{int(datetime.utcnow().timestamp())}_{original_filename}"
    file_path = os.path.join(user_upload_dir, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)

        extracted_text, page_texts = extract_pdf_text(file_path)
        cleaned_text = clean_text(extracted_text)

        text_path = os.path.join(user_upload_dir, safe_filename.replace(".pdf", ".txt"))
        with open(text_path, "w", encoding="utf-8") as output_file:
            output_file.write(cleaned_text)

        reader = PdfReader(file_path)
        document = Document(
            user_id=current_user.id,
            filename=safe_filename,
            title=original_filename,
            file_path=file_path,
            extracted_text_path=text_path,
            page_count=len(reader.pages),
            word_count=len(re.findall(r"\b\w+\b", cleaned_text)),
            char_count=len(cleaned_text),
            file_size_bytes=os.path.getsize(file_path),
            processing_status="processed",
            upload_date=datetime.utcnow(),
            extracted_text=cleaned_text,
            page_texts=json.dumps(page_texts),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        _index_document_chunks(db, document)
        return document
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not process PDF file: {exc}") from exc


@router.post("/{document_id}/process")
def process_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = _index_document_chunks(db, document)
    return {
        "message": "Document processed successfully",
        "document_id": document.id,
        "chunk_count": len(chunks),
        "status": document.processing_status,
    }


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkOut])
def get_document_chunks(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index).all()
    if not chunks:
        chunks = _index_document_chunks(db, document)
    return [_serialize_chunk(chunk) for chunk in chunks]


@router.post("/{document_id}/ask", response_model=AskResponse)
def ask_document(document_id: int, payload: AskRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = (
        db.query(DocumentChunk)
        .join(Document)
        .filter(Document.user_id == current_user.id)
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        .all()
    )
    if not chunks:
        chunks = _index_document_chunks(db, document)
        for chunk in chunks:
            chunk.document_name = document.filename

    if not chunks:
        answer_text = "I could not find enough information in the selected document to answer that question."
        return AskResponse(answer=answer_text, question=question, document_id=document.id, sources=[])

    for chunk in chunks:
        chunk.document_name = chunk.document.filename

    ranked_results = retrieve_relevant_chunks(question, chunks, top_k=4)
    db.commit()
    relevant_chunks = [chunk for _, chunk in ranked_results]
    if not relevant_chunks:
        answer_text = "I could not find enough information in the selected document to answer that question."
        return AskResponse(answer=answer_text, question=question, document_id=document.id, sources=[])

    answer_data = generate_answer(question, relevant_chunks)
    similarity_by_source = {}
    source_entries = []
    for score, chunk in ranked_results:
        source_key = (chunk.document_name, chunk.page_number, chunk.chunk_index)
        similarity_by_source[source_key] = score
        source_entries.append(
            SourceReference(
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                snippet=chunk.chunk_text[:220],
                chunk_index=chunk.chunk_index,
                similarity_score=score,
            )
        )

    answer_text = answer_data.get("answer", "I could not find enough information in the selected document to answer that question.")
    if not answer_data.get("sources"):
        sources = source_entries
    else:
        sources = [
            SourceReference(
                document_name=item.get("document_name", document.filename),
                page_number=item.get("page_number", 1),
                snippet=item.get("snippet", ""),
                chunk_index=item.get("chunk_index", 0),
                similarity_score=similarity_by_source.get(
                    (
                        item.get("document_name", document.filename),
                        item.get("page_number", 1),
                        item.get("chunk_index", 0),
                    )
                ),
            )
            for item in answer_data.get("sources", [])
        ]

    message = ChatMessage(
        user_id=current_user.id,
        document_id=document.id,
        question=question,
        answer=answer_text,
        source_references=json.dumps([source.model_dump() for source in sources]),
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return AskResponse(answer=answer_text, question=question, document_id=document.id, sources=sources)


@router.get("/{document_id}/chat", response_model=list[ChatMessageOut])
def get_document_chat(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    messages = db.query(ChatMessage).filter(ChatMessage.document_id == document.id, ChatMessage.user_id == current_user.id).order_by(ChatMessage.created_at.asc()).all()
    response = []
    for message in messages:
        try:
            sources = json.loads(message.source_references or "[]")
        except (TypeError, json.JSONDecodeError):
            sources = []
        response.append({
            "id": message.id,
            "user_id": message.user_id,
            "document_id": message.document_id,
            "question": message.question,
            "answer": message.answer,
            "created_at": message.created_at,
            "sources": sources,
        })
    return response


@router.delete("/{document_id}/chat")
def clear_document_chat(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    db.query(ChatMessage).filter(ChatMessage.document_id == document.id, ChatMessage.user_id == current_user.id).delete()
    db.commit()
    return {"message": "Chat history cleared successfully"}


@router.get("/{document_id}/sources", response_model=list[SourceReference])
def get_document_sources(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index).all()
    if not chunks:
        chunks = _index_document_chunks(db, document)

    return [
        SourceReference(
            document_name=document.filename,
            page_number=chunk.page_number,
            snippet=(chunk.chunk_text[:220]),
            chunk_index=chunk.chunk_index,
        )
        for chunk in chunks
    ]


@router.get("/{document_id}/suggestions")
def get_document_suggestions(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.extracted_text:
        return {"suggestions": ["What is this document about?", "What are the key points?", "What are the important instructions?"]}

    return {"suggestions": generate_suggested_questions(document.extracted_text)}


@router.post("/{document_id}/summary", response_model=SummaryResponse)
def generate_summary(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.extracted_text:
        return SummaryResponse(
            executive_summary="The document appears to be empty or unreadable.",
            key_points=[],
            important_information=[],
        )

    summary_data = generate_document_summary(document.extracted_text)
    document.summary = summary_data["executive_summary"]
    db.commit()
    return SummaryResponse(**summary_data)


@router.delete("/{document_id}")
def delete_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = get_document_by_id(db, current_user, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    db.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete()
    db.query(ChatMessage).filter(ChatMessage.document_id == document.id, ChatMessage.user_id == current_user.id).delete()

    if os.path.exists(document.file_path):
        os.remove(document.file_path)

    if document.extracted_text_path and os.path.exists(document.extracted_text_path):
        os.remove(document.extracted_text_path)

    db.delete(document)
    db.commit()

    return {"message": "Document deleted successfully"}
