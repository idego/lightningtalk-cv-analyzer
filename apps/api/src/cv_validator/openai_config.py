from __future__ import annotations

import os
from dataclasses import dataclass, field


PINNED_OPENAI_MODEL = "gpt-5.6-luna"
OPENAI_REQUEST_TIMEOUT_SECONDS = 120.0


class OpenAIConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class OpenAISettings:
    enabled: bool = False
    api_key: str | None = field(default=None, repr=False)
    model: str = PINNED_OPENAI_MODEL
    timeout_seconds: float = OPENAI_REQUEST_TIMEOUT_SECONDS
    store: bool = False

    def __post_init__(self) -> None:
        if self.enabled and not self.api_key:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY is required when CV_VALIDATOR_AI_ENABLED=true"
            )
        if self.model != PINNED_OPENAI_MODEL:
            raise OpenAIConfigurationError(
                f"OpenAI model must remain pinned to {PINNED_OPENAI_MODEL}"
            )
        if self.timeout_seconds <= 0:
            raise OpenAIConfigurationError("OpenAI timeout must be positive")
        if self.store:
            raise OpenAIConfigurationError("OpenAI response storage must remain disabled")


def load_openai_settings() -> OpenAISettings:
    return OpenAISettings(
        enabled=_read_bool("CV_VALIDATOR_AI_ENABLED", default=True),
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
    raise OpenAIConfigurationError(f"{name} must be true or false")
