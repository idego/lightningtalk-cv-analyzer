"""AI document-analysis contracts.

The package contains only local configuration and pure application boundaries.
It does not perform network requests during import or application startup.
"""

from cv_validator.ai.config import AIConfigurationError, AISettings, load_ai_settings

__all__ = ["AIConfigurationError", "AISettings", "load_ai_settings"]
