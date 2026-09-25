import psycopg
from fastapi.testclient import TestClient

from app.main import app


def test_health(db: psycopg.Connection) -> None:
    # `with` runs the lifespan (opens the DB pool) — the production path.
    with TestClient(app) as c:
        r = c.get("/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}
