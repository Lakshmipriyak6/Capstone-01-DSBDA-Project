from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.auth_routes import router as auth_router
from app.database import Base, ensure_database_schema, engine
from app.document_routes import router as document_router
from app.analytics_routes import router as analytics_router

ensure_database_schema()
Base.metadata.create_all(bind=engine)

app = FastAPI(title="DocuMind AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(document_router)
app.include_router(analytics_router)


@app.get("/")
def home():
    return {
        "message": "DocuMind AI Backend is running!",
        "features": ["authentication", "document-library", "rag-document-qa"],
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/upload")
async def upload_document_legacy(file: UploadFile = File(...)):
    return {
        "message": "Use the document library upload endpoint for document-specific processing.",
        "filename": file.filename,
    }


@app.post("/ask_question")
async def ask_question_legacy(question: str):
    return {
        "answer": "This legacy endpoint is deprecated. Use the selected-document RAG endpoint: POST /documents/{document_id}/ask.",
    }


@app.post("/ask")
async def ask_legacy(question: str):
    return await ask_question_legacy(question)
