from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class _ResearchLockEntry:
    lock: threading.Lock
    users: int = 0


class _ResearchLockLease:
    def __init__(
        self,
        registry: "ResearchLockRegistry",
        key: str,
        entry: _ResearchLockEntry,
    ) -> None:
        self._registry = registry
        self._key = key
        self._entry = entry

    def __enter__(self) -> "_ResearchLockLease":
        try:
            self._entry.lock.acquire()
        except BaseException:
            self._registry.release(self._key, self._entry)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self._entry.lock.release()
        self._registry.release(self._key, self._entry)


class AnalysisCancellationRegistry:
    """Remembers cancel requests by (access token, client request id).

    The model call is synchronous and cannot be interrupted, so a cancel takes
    effect at the next checkpoint: before the run starts or before its report is
    persisted. Entries are bounded and dropped once consumed or superseded.
    """

    _MAX_ENTRIES = 256

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], None] = {}
        self._guard = threading.Lock()

    def request(self, access_token: str, request_id: str) -> None:
        with self._guard:
            self._entries.pop((access_token, request_id), None)
            self._entries[(access_token, request_id)] = None
            while len(self._entries) > self._MAX_ENTRIES:
                self._entries.pop(next(iter(self._entries)))

    def is_cancelled(self, access_token: str, request_id: str | None) -> bool:
        if request_id is None:
            return False
        with self._guard:
            return (access_token, request_id) in self._entries

    def discard(self, access_token: str, request_id: str | None) -> None:
        if request_id is None:
            return
        with self._guard:
            self._entries.pop((access_token, request_id), None)


class ResearchLockRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, _ResearchLockEntry] = {}
        self._guard = threading.Lock()

    def acquire(self, key: str) -> _ResearchLockLease:
        with self._guard:
            entry = self._entries.get(key)
            if entry is None:
                entry = _ResearchLockEntry(threading.Lock())
                self._entries[key] = entry
            entry.users += 1
        return _ResearchLockLease(self, key, entry)

    def release(self, key: str, entry: _ResearchLockEntry) -> None:
        with self._guard:
            entry.users -= 1
            if entry.users == 0 and self._entries.get(key) is entry:
                del self._entries[key]

    def clear(self) -> None:
        with self._guard:
            self._entries.clear()

    def __len__(self) -> int:
        with self._guard:
            return len(self._entries)
