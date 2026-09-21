import pytest
from pydantic import ValidationError

from app.config import Settings


def test_demo_limits_default_above_the_old_fixed_cap(monkeypatch):
    monkeypatch.delenv("DEMO_MAX_SESSIONS", raising=False)
    monkeypatch.delenv("DEMO_MAX_SESSIONS_PER_HOUR", raising=False)
    settings = Settings(environment="test")
    assert settings.demo_max_sessions == 60
    assert settings.demo_max_sessions_per_hour == 60


def test_demo_limits_are_set_from_railway_style_env_vars(monkeypatch):
    monkeypatch.setenv("DEMO_MAX_SESSIONS", "150")
    monkeypatch.setenv("DEMO_MAX_SESSIONS_PER_HOUR", "90")
    settings = Settings()
    assert settings.demo_max_sessions == 150
    assert settings.demo_max_sessions_per_hour == 90


def test_demo_limits_reject_nonsense_values():
    with pytest.raises(ValidationError):
        Settings(environment="test", demo_max_sessions=0)
    with pytest.raises(ValidationError):
        Settings(environment="test", demo_max_sessions_per_hour=5000)
