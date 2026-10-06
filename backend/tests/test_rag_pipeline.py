import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_rag_pipeline_upload_and_question_flow():
    register_response = client.post(
        "/auth/register",
        json={
            "email": "rag-user@example.com",
            "username": "raguser",
            "password": "StrongPass!123",
            "full_name": "RAG User",
        },
    )
    assert register_response.status_code == 201, register_response.text

    login_response = client.post(
        "/auth/login",
        json={"email": "rag-user@example.com", "password": "StrongPass!123"},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with open(os.path.join(os.path.dirname(__file__), "..", "test_upload.pdf"), "rb") as file_handle:
        upload_response = client.post(
            "/documents/upload",
            headers=headers,
            files={"file": ("test_upload.pdf", file_handle, "application/pdf")},
        )

    assert upload_response.status_code == 201, upload_response.text
    document_id = upload_response.json()["id"]

    process_response = client.post(f"/documents/{document_id}/process", headers=headers)
    assert process_response.status_code == 200, process_response.text

    chunks_response = client.get(f"/documents/{document_id}/chunks", headers=headers)
    assert chunks_response.status_code == 200, chunks_response.text
    chunks = chunks_response.json()
    assert len(chunks) > 0

    ask_response = client.post(
        f"/documents/{document_id}/ask",
        headers=headers,
        json={"question": "What is the main topic described in this document?"},
    )
    assert ask_response.status_code == 200, ask_response.text
    payload = ask_response.json()
    assert "answer" in payload
    assert "sources" in payload
    assert payload["sources"]
    assert all("similarity_score" in source for source in payload["sources"])

    history_response = client.get(f"/documents/{document_id}/chat", headers=headers)
    assert history_response.status_code == 200, history_response.text
    history = history_response.json()
    assert len(history) >= 1
    assert history[0]["sources"] == payload["sources"]


def test_unauthorized_document_access_is_blocked():
    first_user = client.post(
        "/auth/register",
        json={
            "email": "owner@example.com",
            "username": "owneruser",
            "password": "StrongPass!123",
            "full_name": "Owner User",
        },
    )
    second_user = client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "username": "otheruser",
            "password": "StrongPass!123",
            "full_name": "Other User",
        },
    )

    owner_login = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": "StrongPass!123"},
    )
    other_login = client.post(
        "/auth/login",
        json={"email": "other@example.com", "password": "StrongPass!123"},
    )

    owner_token = owner_login.json()["access_token"]
    other_token = other_login.json()["access_token"]

    with open(os.path.join(os.path.dirname(__file__), "..", "test_upload.pdf"), "rb") as file_handle:
        upload_response = client.post(
            "/documents/upload",
            headers={"Authorization": f"Bearer {owner_token}"},
            files={"file": ("doc.pdf", file_handle, "application/pdf")},
        )

    document_id = upload_response.json()["id"]
    unauthorized = client.post(
        f"/documents/{document_id}/ask",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"question": "What is this document about?"},
    )

    assert unauthorized.status_code == 403, unauthorized.text
