from __future__ import annotations

import os
from dataclasses import dataclass, field


PINNED_OPENAI_MODEL = "gpt-5.6-luna"
OPENAI_REASONING_EFFORT = "medium"
OPENAI_REQUEST_TIMEOUT_SECONDS = 120.0
OPENAI_MAX_RETRIES = 0
OPENAI_STORE_RESPONSES = False
OPENAI_MAX_OUTPUT_TOKENS = 4096


class AIConfigurationError(ValueError):
    """Raised before startup when enabled AI configuration is unsafe."""


@dataclass(frozen=True)
class AISettings:
    enabled: bool = False
    api_key: str | None = field(default=None, repr=False)
    model: str = PINNED_OPENAI_MODEL
    reasoning_effort: str = OPENAI_REASONING_EFFORT
    timeout_seconds: float = OPENAI_REQUEST_TIMEOUT_SECONDS
    max_retries: int = OPENAI_MAX_RETRIES
    store: bool = OPENAI_STORE_RESPONSES
    max_output_tokens: int = OPENAI_MAX_OUTPUT_TOKENS

    def __post_init__(self) -> None:
        if self.enabled and not self.api_key:
            raise AIConfigurationError(
                "OPENAI_API_KEY is required when CV_VALIDATOR_AI_ENABLED=true"
            )
        if self.model != PINNED_OPENAI_MODEL:
            raise AIConfigurationError(
                f"AI model must remain pinned to {PINNED_OPENAI_MODEL}"
            )
        if self.timeout_seconds != OPENAI_REQUEST_TIMEOUT_SECONDS:
            raise AIConfigurationError("AI request timeout must remain 120 seconds")
        if self.max_retries != 0:
            raise AIConfigurationError("automatic OpenAI retries must remain disabled")
        if self.store:
            raise AIConfigurationError("OpenAI response storage must remain disabled")
        if self.max_output_tokens < 1:
            raise AIConfigurationError("AI max_output_tokens must be positive")


def load_ai_settings() -> AISettings:
    return AISettings(
        enabled=_read_bool("CV_VALIDATOR_AI_ENABLED", default=False),
        api_key=os.environ.get("OPENAI_API_KEY") or None,
    )


def _read_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().casefold()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise AIConfigurationError(f"{name} must be true or false")
