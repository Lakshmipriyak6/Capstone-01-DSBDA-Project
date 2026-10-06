from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DocumentOut(BaseModel):
    id: int
    user_id: int
    filename: str
    title: str
    page_count: int
    word_count: int
    char_count: int
    paragraph_count: int
    avg_sentence_length: float
    top_terms: Optional[str] = None
    category: Optional[str] = None
    processing_time_ms: int
    document_type: Optional[str] = None
    file_size_bytes: int
    processing_status: str
    upload_date: datetime
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentDetailOut(DocumentOut):
    extracted_text: Optional[str] = None
    page_texts: Optional[str] = None


class DocumentChunkOut(BaseModel):
    id: int
    document_id: int
    page_number: int
    chunk_index: int
    text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceReference(BaseModel):
    document_name: str
    page_number: int
    snippet: str
    chunk_index: int
    similarity_score: Optional[float] = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str
    question: str
    document_id: int
    sources: list[SourceReference] = []


class ChatMessageOut(BaseModel):
    id: int
    user_id: int
    document_id: int
    question: str
    answer: str
    created_at: datetime
    sources: list[SourceReference] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SummaryResponse(BaseModel):
    executive_summary: str
    key_points: list[str]
    important_information: list[str]


class DashboardStats(BaseModel):
    total_documents: int
    total_pages: int
    total_words: int
    total_questions: int
