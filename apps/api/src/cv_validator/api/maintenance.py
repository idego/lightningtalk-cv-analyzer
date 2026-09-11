"""Scheduled retention maintenance: daily purge and vacuum, health flags.

Purging on request paths alone leaves expired rows in place while the API sits
idle, so the app also runs this loop in the background. The loop never raises:
every failure is recorded here so ``/health`` can report it.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone

from starlette.concurrency import run_in_threadpool

from cv_validator.errors import PersistenceError
from cv_validator.operations import safe_log

DAILY_RUN_AT = time(hour=3, minute=0, tzinfo=timezone.utc)
MAINTENANCE_TIME_ENV = "CV_VALIDATOR_MAINTENANCE_TIME_UTC"


def parse_maintenance_time(value: str | None) -> time:
    """Parse ``HH:MM`` (24-hour, UTC) into the daily run time; empty means the default."""
    if value is None or not value.strip():
        return DAILY_RUN_AT
    try:
        parsed = time.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{MAINTENANCE_TIME_ENV} must be HH:MM in 24-hour UTC time") from exc
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise ValueError(f"{MAINTENANCE_TIME_ENV} must be HH:MM in 24-hour UTC time")
    return parsed.replace(tzinfo=timezone.utc)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RetentionMaintenance:
    """Runs a retention purge followed by a vacuum once a day at a fixed UTC time."""

    purgers: Sequence[Callable[[], object]]
    vacuum: Callable[[], None]
    run_at: time = DAILY_RUN_AT
    clock: Callable[[], datetime] = _utc_now
    startup_purge_failed: bool = False
    last_purge_failed: bool = False
    last_vacuum_failed: bool = False
    last_purge_at: datetime | None = None
    last_vacuum_at: datetime | None = None
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
        """One maintenance tick: purge, then vacuum so freed pages leave the file."""
        self.purge()
        try:
            self.vacuum()
        except (OSError, PersistenceError):
            with self._lock:
                self.last_vacuum_failed = True
            safe_log("retention_vacuum_failed", error_code="scheduled_vacuum_failed")
            return
        with self._lock:
            self.last_vacuum_failed = False
            self.last_vacuum_at = self.clock()

    def next_run(self, now: datetime | None = None) -> datetime:
        """The next ``run_at`` wall-clock moment strictly after ``now``."""
        current = (now or self.clock()).astimezone(timezone.utc)
        candidate = datetime.combine(current.date(), self.run_at).astimezone(timezone.utc)
        if candidate <= current:
            candidate += timedelta(days=1)
        return candidate

    async def run_forever(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            delay = (self.next_run() - self.clock()).total_seconds()
            try:
                await asyncio.wait_for(stop.wait(), timeout=max(delay, 0))
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
                "last_vacuum_at": self.last_vacuum_at.isoformat() if self.last_vacuum_at else None,
                "run_at": self.run_at.strftime("%H:%M UTC"),
                "next_run_at": self.next_run().isoformat(),
            }
