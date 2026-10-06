from fastapi.testclient import TestClient

from main import app
from app.security import get_current_user


class FakeUser:
    def __init__(self):
        self.id = 1
        self.username = "testuser"


def override_get_current_user():
    return FakeUser()


def run_test():
    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    resp = client.get("/dataset/search", params={"q": "Beyonce", "top_k": 5})
    print("Status code:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)


if __name__ == '__main__':
    run_test()
