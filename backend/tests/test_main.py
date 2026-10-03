"""create_app refuses to start with an insecure default outside dev/test —
see test_config.py for the underlying ensure_safe_to_start checks."""

import pytest

from app.config import InsecureConfigError, Settings


def test_create_app_refuses_default_jwt_secret_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    prod = Settings(environment="prod", database_url="postgresql://x/x")
    monkeypatch.setattr(main_module, "get_settings", lambda: prod)
    with pytest.raises(InsecureConfigError):
        main_module.create_app()
