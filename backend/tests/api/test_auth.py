"""Auth endpoints — register/login/me plus the Bearer seam.

The no-header dev fallback keeps existing tests untouched; these exercise
the real token path. All on the real test DB.
"""

import pytest
from starlette.testclient import TestClient

USER = {"email": "clara@example.com", "password": "hunter22-long", "display_name": "Clara"}


def _register(client: TestClient) -> str:
    r = client.post("/v1/auth/register", json=USER)
    assert r.status_code == 201, r.text
    return r.json()["token"]  # type: ignore[no-any-return]


def test_register_login_me(client: TestClient) -> None:
    token = _register(client)
    auth = {"Authorization": f"Bearer {token}"}

    me = client.get("/v1/auth/me", headers=auth)
    assert me.status_code == 200
    assert me.json()["email"] == "clara@example.com"
    assert me.json()["display_name"] == "Clara"

    # the token drives ownership: aois created under it list under it
    created = client.post(
        "/v1/aois",
        headers=auth,
        json={
            "name": "clara field",
            "geojson": {
                "type": "Polygon",
                "coordinates": [
                    [[22.7, 40.55], [22.72, 40.55], [22.72, 40.57], [22.7, 40.57], [22.7, 40.55]]
                ],
            },
        },
    )
    assert created.status_code == 201
    listing = client.get("/v1/aois", headers=auth).json()
    assert listing["total"] == 1

    r = client.post("/v1/auth/login", json={"email": USER["email"], "password": USER["password"]})
    assert r.status_code == 200 and r.json()["token"]


def test_register_duplicate_and_validation(client: TestClient) -> None:
    _register(client)
    r = client.post("/v1/auth/register", json=USER)
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_TAKEN"

    r = client.post("/v1/auth/register", json={"email": "x@y.z", "password": "short"})
    assert r.status_code == 422
    r = client.post("/v1/auth/register", json={"email": "not-an-email", "password": "long-enough"})
    assert r.status_code == 422


def test_login_failures(client: TestClient) -> None:
    _register(client)
    for body in (
        {"email": USER["email"], "password": "wrong-password"},
        {"email": "ghost@example.com", "password": USER["password"]},
    ):
        r = client.post("/v1/auth/login", json=body)
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "UNAUTHENTICATED"


def test_bad_token_rejected(client: TestClient) -> None:
    r = client.get("/v1/aois", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "UNAUTHENTICATED"

    # expired/forged signature
    import jwt

    forged = jwt.encode({"sub": "00000000-0000-0000-0000-000000000000"}, "wrong", "HS256")
    r = client.get("/v1/aois", headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


def test_dev_fallback_disabled_in_prod(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    # an EM_DEV_USER_EMAIL left set in prod must not open the API
    from app.api import deps
    from app.config import Settings

    prod = Settings(
        environment="prod",
        dev_user_email="dev@earth-monitor.local",
        database_url="postgresql://unused/unused",
    )
    monkeypatch.setattr(deps, "get_settings", lambda: prod)
    r = client.get("/v1/aois")
    assert r.status_code == 401
