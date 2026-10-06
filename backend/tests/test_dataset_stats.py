import os

os.environ.setdefault("TESTING", "1")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from fastapi.testclient import TestClient

from app.dataset_service import DATASET_PATH
from main import app


client = TestClient(app)


def test_dataset_stats_returns_streamed_csv_metadata():
    response = client.get("/dataset/stats")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["row_count"] > 0
    assert payload["columns"] == [
        "id",
        "title",
        "context",
        "question",
        "answer",
        "answer_start",
        "is_impossible",
    ]
    assert DATASET_PATH.is_file()
