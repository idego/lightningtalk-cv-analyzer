class AnalysisRuntimeError(RuntimeError):
    """Expected per-document runtime failure safe to isolate at the API boundary."""


class UploadReadError(AnalysisRuntimeError):
    pass


class LocationAnalysisError(AnalysisRuntimeError):
    pass


class PersistenceError(AnalysisRuntimeError):
    pass


class AnalysisNotFoundPersistenceError(PersistenceError):
    """The report parent disappeared before a candidate-owned write."""

    pass
