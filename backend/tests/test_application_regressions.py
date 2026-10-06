import io
import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import jwt
from fastapi.testclient import TestClient
from pypdf import PdfWriter

from main import app
from app.security import ALGORITHM, SECRET_KEY


client = TestClient(app)


def _authenticated_headers():
    suffix = uuid.uuid4().hex
    credentials = {
        "email": f"audit-{suffix}@example.com",
        "username": f"audit-{suffix}",
        "password": "StrongPass!123",
    }
    register = client.post("/auth/register", json=credentials)
    assert register.status_code == 201, register.text
    login = client.post(
        "/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _blank_pdf_bytes():
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_malformed_token_subject_returns_unauthorized():
    token = jwt.encode(
        {"sub": "not-an-integer", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_empty_text_document_does_not_break_analytics():
    headers = _authenticated_headers()
    upload = client.post(
        "/documents/upload",
        headers=headers,
        files={"file": ("blank.pdf", _blank_pdf_bytes(), "application/pdf")},
    )
    assert upload.status_code == 201, upload.text

    for endpoint in (
        "/analytics/overview",
        "/analytics/topics",
        "/analytics/similarity",
        "/analytics/clusters",
        "/analytics/knowledge-graph",
        "/analytics/trends",
        "/analytics/outliers",
        "/analytics/activity",
    ):
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 200, f"{endpoint}: {response.text}"