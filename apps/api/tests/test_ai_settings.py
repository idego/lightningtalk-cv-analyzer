import pytest

from cv_validator.ai.config import (
    AIConfigurationError,
    load_ai_settings,
)
from cv_validator.api.app import create_app


AI_ENV_NAMES = (
    "CV_VALIDATOR_AI_ENABLED",
    "OPENAI_API_KEY",
)


def _clear_ai_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in AI_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_ai_is_disabled_by_default_without_requiring_a_secret(monkeypatch) -> None:
    _clear_ai_env(monkeypatch)

    settings = load_ai_settings()

    assert settings.enabled is False
    assert settings.api_key is None
    assert settings.model == "gpt-5.6-luna"
    assert settings.reasoning_effort == "medium"
    assert settings.timeout_seconds == 120.0
    assert settings.max_retries == 0
    assert settings.store is False
    assert settings.max_output_tokens == 4096


def test_enabled_ai_without_api_key_fails_fast_during_app_creation(
    monkeypatch,
    tmp_path,
) -> None:
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("CV_VALIDATOR_AI_ENABLED", "true")

    with pytest.raises(AIConfigurationError, match="OPENAI_API_KEY"):
        create_app(db_path=tmp_path / "missing-key.db")


def test_enabled_ai_settings_keep_the_secret_out_of_repr(monkeypatch) -> None:
    _clear_ai_env(monkeypatch)
    monkeypatch.setenv("CV_VALIDATOR_AI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "private-test-secret")

    settings = load_ai_settings()

    assert settings.enabled is True
    assert settings.api_key == "private-test-secret"
    assert "private-test-secret" not in repr(settings)
