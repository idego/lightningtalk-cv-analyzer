"""Scheduled retention maintenance: daily purge, weekly vacuum, health flags.

Purging on request paths alone leaves expired rows in place while the API sits
idle, so the app also runs this loop in the background. The loop never raises:
every failure is recorded here so ``/health`` can report it.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from cv_validator.errors import PersistenceError
from cv_validator.operations import safe_log

SATURDAY = 5
PURGE_INTERVAL = timedelta(days=1)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RetentionMaintenance:
    """Runs retention purges on a fixed interval and vacuums once every Saturday."""

    purgers: Sequence[Callable[[], object]]
    vacuum: Callable[[], None]
    interval: timedelta = PURGE_INTERVAL
    vacuum_weekday: int = SATURDAY
    clock: Callable[[], datetime] = _utc_now
    startup_purge_failed: bool = False
    last_purge_failed: bool = False
    last_vacuum_failed: bool = False
    last_purge_at: datetime | None = None
    last_vacuum_on: date | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def run_startup(self) -> bool:
        """Purge once at boot; a failure stays visible on /health until a purge succeeds."""
        succeeded = self.purge()
        with self._lock:
            self.startup_purge_failed = not succeeded
        return succeeded

    def purge(self) -> bool:
        failed = False
        for purger in self.purgers:
            try:
                purger()
            except (OSError, PersistenceError):
                failed = True
                safe_log("retention_purge_failed", error_code="scheduled_purge_failed")
        with self._lock:
            self.last_purge_failed = failed
            self.last_purge_at = self.clock()
            if not failed:
                self.startup_purge_failed = False
        return not failed

    def run_cycle(self) -> None:
        """One maintenance tick: purge, then vacuum if it is Saturday and not yet done today."""
        self.purge()
        today = self.clock().date()
        if today.weekday() != self.vacuum_weekday or self.last_vacuum_on == today:
            return
        try:
            self.vacuum()
        except (OSError, PersistenceError):
            with self._lock:
                self.last_vacuum_failed = True
            safe_log("retention_vacuum_failed", error_code="scheduled_vacuum_failed")
            return
        with self._lock:
            self.last_vacuum_failed = False
            self.last_vacuum_on = today

    async def run_forever(self, stop: asyncio.Event) -> None:
        interval_seconds = self.interval.total_seconds()
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                pass
            if stop.is_set():
                return
            await run_in_threadpool(self.run_cycle)

    @property
    def healthy(self) -> bool:
        with self._lock:
            return not (self.startup_purge_failed or self.last_purge_failed)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "ready": not (self.startup_purge_failed or self.last_purge_failed),
                "startup_purge_failed": self.startup_purge_failed,
                "last_purge_failed": self.last_purge_failed,
                "last_purge_at": self.last_purge_at.isoformat() if self.last_purge_at else None,
                "last_vacuum_failed": self.last_vacuum_failed,
                "last_vacuum_on": self.last_vacuum_on.isoformat() if self.last_vacuum_on else None,
                "interval_seconds": int(self.interval.total_seconds()),
            }
