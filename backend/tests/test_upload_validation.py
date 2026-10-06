import io
import os
import uuid

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from main import app
from app.document_routes import MAX_UPLOAD_SIZE_BYTES


client = TestClient(app)


def _authenticated_headers():
    suffix = uuid.uuid4().hex
    register_response = client.post(
        "/auth/register",
        json={
            "email": f"upload-{suffix}@example.com",
            "username": f"upload-{suffix}",
            "password": "StrongPass!123",
        },
    )
    assert register_response.status_code == 201, register_response.text
    login_response = client.post(
        "/auth/login",
        json={
            "email": f"upload-{suffix}@example.com",
            "password": "StrongPass!123",
        },
    )
    assert login_response.status_code == 200, login_response.text
    return {"Authorization": f"Bearer {login_response.json()['access_token']}"}


def _valid_pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_upload_accepts_valid_pdf():
    response = client.post(
        "/documents/upload",
        headers=_authenticated_headers(),
        files={"file": ("../valid.pdf", _valid_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 201, response.text
    assert response.json()["processing_status"] == "empty"
    assert response.json()["title"] == "valid.pdf"


def test_upload_rejects_wrong_file_type():
    response = client.post(
        "/documents/upload",
        headers=_authenticated_headers(),
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are allowed"


def test_upload_rejects_empty_pdf():
    response = client.post(
        "/documents/upload",
        headers=_authenticated_headers(),
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "PDF file is empty"


def test_upload_rejects_malformed_pdf():
    response = client.post(
        "/documents/upload",
        headers=_authenticated_headers(),
        files={"file": ("broken.pdf", b"%PDF-1.7\nnot a PDF structure", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "PDF file is malformed or unreadable"


def test_upload_rejects_oversized_pdf():
    response = client.post(
        "/documents/upload",
        headers=_authenticated_headers(),
        files={
            "file": (
                "oversized.pdf",
                b"%PDF-1.7\n" + b"x" * MAX_UPLOAD_SIZE_BYTES,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "PDF exceeds the maximum upload size of 10 MiB"