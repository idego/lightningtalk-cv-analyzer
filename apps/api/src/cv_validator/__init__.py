"""CV Analyzer shared application and strategy contracts."""

from cv_validator.analysis import AnalysisInput, AnalysisStrategy
from cv_validator.pipeline import analyze_cv_bytes

__all__ = ["AnalysisInput", "AnalysisStrategy", "analyze_cv_bytes"]

__version__ = "0.1.0"
