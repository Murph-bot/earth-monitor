"""Settings validation — the database URL is pasted by hand into hosting
dashboards, so bad pastes must fail loudly without echoing the secret."""

import pytest
from pydantic import ValidationError

from app.config import Settings

SECRET = "hunter2-not-in-logs"


@pytest.mark.parametrize(
    "pasted",
    [
        f"psql 'postgresql://owner:{SECRET}@ep-x-pooler.neon.tech/neondb?sslmode=require'",
        f"'postgresql://owner:{SECRET}@ep-x-pooler.neon.tech/neondb?sslmode=require'",
        "",
    ],
)
def test_bad_database_url_rejected_without_leaking(pasted: str) -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(database_url=pasted)
    message = str(exc.value)
    assert SECRET not in message
    assert "postgresql://" in message


def test_database_url_whitespace_trimmed() -> None:
    url = f"postgresql://owner:{SECRET}@ep-x-pooler.neon.tech/neondb?sslmode=require"
    assert Settings(database_url=f"  {url}\n").database_url == url


PAGES = "https://earth-monitor.pages.dev"


@pytest.mark.parametrize(
    "pasted",
    [
        f'["{PAGES}"]',
        PAGES,
        f"{PAGES}/",
        f"[“{PAGES}”]",
        f"[{PAGES}]",
        f"'{PAGES}'",
    ],
)
def test_cors_origins_accepts_dashboard_pastes(
    pasted: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("EM_CORS_ORIGINS", pasted)
    assert Settings().cors_origins == [PAGES]


def test_cors_origins_comma_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EM_CORS_ORIGINS", f"{PAGES}, http://localhost:5173")
    assert Settings().cors_origins == [PAGES, "http://localhost:5173"]


def test_dev_user_email_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    # a deploy that forgets to set EM_DEV_USER_EMAIL must not get a tokenless
    # fallback user for free — it must be opted into explicitly
    monkeypatch.delenv("EM_DEV_USER_EMAIL", raising=False)
    assert Settings().dev_user_email is None


def test_prod_refuses_default_jwt_secret() -> None:
    from app.config import InsecureConfigError, ensure_safe_to_start

    with pytest.raises(InsecureConfigError):
        ensure_safe_to_start(Settings(environment="prod", database_url="postgresql://x/x"))


@pytest.mark.parametrize("env", ["dev", "test"])
def test_dev_and_test_allow_default_jwt_secret(env: str) -> None:
    from app.config import ensure_safe_to_start

    ensure_safe_to_start(Settings(environment=env))  # must not raise


def test_prod_with_real_secret_is_fine() -> None:
    from app.config import ensure_safe_to_start

    ensure_safe_to_start(
        Settings(environment="prod", database_url="postgresql://x/x", jwt_secret="a-real-secret")
    )
