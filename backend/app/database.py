import os

from sqlalchemy import StaticPool, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'documind.db')}")

engine_kwargs = {"connect_args": {"check_same_thread": False}}
if DATABASE_URL.startswith("sqlite://") and os.getenv("TESTING") == "1":
    engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_database_schema():
    inspector = inspect(engine)
    required_tables = {"users", "documents", "document_chunks", "chat_messages"}
    existing_tables = set(inspector.get_table_names())
    if not required_tables.issubset(existing_tables):
        Base.metadata.create_all(bind=engine)
        return

    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    required_columns = {
        "char_count": "INTEGER",
        "file_size_bytes": "INTEGER",
        "processing_status": "VARCHAR(50)",
        "extracted_text": "TEXT",
        "page_texts": "TEXT",
        "summary": "TEXT",
        "paragraph_count": "INTEGER",
        "avg_sentence_length": "FLOAT",
        "top_terms": "TEXT",
        "category": "VARCHAR(100)",
        "processing_time_ms": "INTEGER",
        "document_type": "VARCHAR(100)",
    }

    with engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in document_columns:
                connection.execute(text(f"ALTER TABLE documents ADD COLUMN {column_name} {column_type}"))

        chat_columns = {column["name"] for column in inspector.get_columns("chat_messages")}
        if "source_references" not in chat_columns:
            connection.execute(text("ALTER TABLE chat_messages ADD COLUMN source_references TEXT"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
