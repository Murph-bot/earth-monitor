"""DB-free API tests: a fake connection feeds canned rows, so these run
without Postgres. SQL itself is exercised by the DB-backed tests in
test_api.py (skipped when `docker compose up -d db` isn't running)."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import requests
from starlette.testclient import TestClient

from app.api.deps import get_backfill_runner, get_current_user, get_db
from app.api.v1 import public
from app.api.v1.aois import next_pass_estimate
from app.config import get_settings
from app.ingest import backfill as backfill_mod
from app.main import create_app
from app.regions import REGIONS

USER = uuid.uuid4()
AOI_ID = uuid.uuid4()
NOW = datetime(2026, 10, 23, 12, 0, tzinfo=UTC)


class _Cursor:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._row


class FakeDb:
    """execute() pops the next canned row."""

    def __init__(self, rows: list[tuple[Any, ...] | None]) -> None:
        self.rows = list(rows)
        self.sql: list[str] = []

    def execute(self, sql: str, params: Any = None) -> _Cursor:
        self.sql.append(sql)
        return _Cursor(self.rows.pop(0))


def _app(db: FakeDb, scheduled: list[uuid.UUID]) -> TestClient:
    app = create_app()

    def _db() -> Iterator[FakeDb]:
        yield db

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[get_backfill_runner] = lambda: scheduled.append
    return TestClient(app)  # no lifespan: no pool needed


AOI_ROW = (AOI_ID, "field", False, 1e6, NOW, 22.0, 39.0, 22.1, 39.1)


# --- public summary ----------------------------------------------------------


@pytest.fixture(autouse=True)
def _fresh_state() -> Iterator[None]:
    public.clear_cache()
    yield
    public.clear_cache()


def test_summary_real_rows_and_delta() -> None:
    db = FakeDb(
        [
            (0.41, 0.44, 5),  # greenness: this week, last week, areas
            (12.0, 5),  # rain: mean mm, areas
            (3, 2, NOW - timedelta(days=2)),  # scenes: clear, cloudy, newest
        ]
    )
    r = _app(db, []).get("/v1/public/region/thessaly/summary")
    assert r.status_code == 200
    assert "public" in r.headers["cache-control"]
    body = r.json()
    assert body["greenness"]["mean"] == 0.41
    assert body["greenness"]["delta"] == pytest.approx(-0.03)
    assert body["rain"] == {"mean_mm": 12.0, "areas": 5}
    assert body["scenes"]["clear"] == 3 and body["scenes"]["cloudy"] == 2
    assert body["bounds"] == list(REGIONS["thessaly"].bbox)


def test_summary_no_data_is_null_not_zero() -> None:
    db = FakeDb([(None, None, 0), (None, 0), (0, 0, None)])
    body = _app(db, []).get("/v1/public/region/thessaly/summary").json()
    assert body["greenness"] == {"mean": None, "previous_mean": None, "delta": None, "areas": 0}
    assert body["rain"]["mean_mm"] is None
    assert body["scenes"]["latest_scene_at"] is None


def test_summary_needs_no_auth_and_is_cached() -> None:
    db = FakeDb([(0.4, None, 1), (1.0, 1), (0, 0, None)])
    app = _app(db, [])
    app.app.dependency_overrides.pop(get_current_user)  # type: ignore[attr-defined]
    first = app.get("/v1/public/region/thessaly/summary").json()
    second = app.get("/v1/public/region/thessaly/summary").json()  # would pop an empty list
    assert first == second and len(db.sql) == 3
    assert first["greenness"]["delta"] is None  # no previous week -> no delta


# --- next pass ---------------------------------------------------------------


def test_next_pass_steps_last_scene_by_whole_cycles() -> None:
    last = NOW - timedelta(days=7)
    est = next_pass_estimate(last, 5.0, NOW)
    assert est == (last + timedelta(days=10), "last_scene_cadence")
    assert est[0] > NOW


def test_next_pass_without_scenes_is_an_upper_bound() -> None:
    assert next_pass_estimate(None, 5.0, NOW) == (NOW + timedelta(days=5), "revisit_upper_bound")


def test_next_pass_unknown_revisit() -> None:
    assert next_pass_estimate(NOW, None, NOW) is None


# --- backfill ----------------------------------------------------------------


def test_backfill_schedules_for_owner() -> None:
    scheduled: list[uuid.UUID] = []
    r = _app(FakeDb([AOI_ROW]), scheduled).post(f"/v1/aois/{AOI_ID}/backfill")
    assert r.status_code == 202
    assert r.json() == {"aoi_id": str(AOI_ID), "days": 90, "status": "scheduled"}
    assert scheduled == [AOI_ID]


def test_backfill_not_owner_is_404_and_schedules_nothing() -> None:
    scheduled: list[uuid.UUID] = []
    r = _app(FakeDb([None]), scheduled).post(f"/v1/aois/{AOI_ID}/backfill")
    assert r.status_code == 404 and scheduled == []


def test_backfill_conflict_while_running() -> None:
    scheduled: list[uuid.UUID] = []
    assert backfill_mod.claim(str(AOI_ID))
    try:
        r = _app(FakeDb([AOI_ROW]), scheduled).post(f"/v1/aois/{AOI_ID}/backfill")
    finally:
        backfill_mod.release(str(AOI_ID))
    assert r.status_code == 409 and r.json()["error"]["code"] == "BUSY" and scheduled == []


def test_backfill_is_rate_limited() -> None:
    limit = get_settings().rate_backfill_per_minute
    client = _app(FakeDb([AOI_ROW] * (limit + 1)), [])
    codes = [client.post(f"/v1/aois/{AOI_ID}/backfill").status_code for _ in range(limit + 1)]
    assert codes == [202] * limit + [429]


# --- turnstile ---------------------------------------------------------------

REGISTER = {"email": "a@example.com", "password": "longenough1"}


@pytest.fixture
def turnstile_secret(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("EM_TURNSTILE_SECRET", "test-secret")
    get_settings.cache_clear()
    yield
    monkeypatch.undo()
    get_settings.cache_clear()


def test_register_without_token_rejected_when_secret_set(turnstile_secret: None) -> None:
    r = _app(FakeDb([]), []).post("/v1/auth/register", json=REGISTER)
    assert r.status_code == 400 and r.json()["error"]["code"] == "TURNSTILE"


def test_login_with_rejected_token(turnstile_secret: None, monkeypatch: pytest.MonkeyPatch) -> None:
    class Resp:
        def raise_for_status(self) -> None: ...
        def json(self) -> dict[str, Any]:
            return {"success": False, "error-codes": ["invalid-input-response"]}

    sent: dict[str, Any] = {}

    def fake_post(url: str, data: dict[str, str], timeout: int) -> Resp:
        sent.update(data)
        return Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    body = {"email": "a@example.com", "password": "x", "turnstile_token": "tok"}
    r = _app(FakeDb([]), []).post("/v1/auth/login", json=body)
    assert r.status_code == 400 and r.json()["error"]["code"] == "TURNSTILE"
    assert sent["secret"] == "test-secret" and sent["response"] == "tok"


def test_siteverify_outage_fails_closed(
    turnstile_secret: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*_a: Any, **_k: Any) -> None:
        raise requests.ConnectionError

    monkeypatch.setattr(requests, "post", boom)
    body = {**REGISTER, "turnstile_token": "tok"}
    r = _app(FakeDb([]), []).post("/v1/auth/register", json=body)
    assert r.status_code == 503 and r.json()["error"]["code"] == "TURNSTILE_UNAVAILABLE"


def test_no_secret_means_no_verification(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.turnstile import verify_turnstile

    monkeypatch.delenv("EM_TURNSTILE_SECRET", raising=False)
    get_settings.cache_clear()
    verify_turnstile(None, None)  # must not raise or call out
