from __future__ import annotations

import hashlib
import os
from pathlib import Path

_CHUNK_BYTES = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_fd(artifact_fd: int) -> str:
    digest = hashlib.sha256()
    duplicate = os.dup(artifact_fd)
    with os.fdopen(duplicate, "rb", closefd=True) as source:
        source.seek(0)
        for chunk in iter(lambda: source.read(_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()
