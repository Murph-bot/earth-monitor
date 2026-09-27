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
