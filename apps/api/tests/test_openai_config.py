import pytest

from cv_validator.openai_config import (
    OpenAIConfigurationError,
    load_openai_settings,
)


def test_ai_is_enabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("CV_VALIDATOR_AI_ENABLED", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    settings = load_openai_settings()

    assert settings.enabled is True


def test_default_ai_requires_an_api_key(monkeypatch) -> None:
    monkeypatch.delenv("CV_VALIDATOR_AI_ENABLED", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY"):
        load_openai_settings()


def test_ai_can_still_be_disabled_explicitly(monkeypatch) -> None:
    monkeypatch.setenv("CV_VALIDATOR_AI_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    settings = load_openai_settings()

    assert settings.enabled is False
