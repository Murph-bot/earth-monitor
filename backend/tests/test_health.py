from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    response = TestClient(app).get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
