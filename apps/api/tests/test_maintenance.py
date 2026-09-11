from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient

from cv_validator.api.app import create_app
from cv_validator.api.maintenance import RetentionMaintenance
from cv_validator.errors import PersistenceError
from cv_validator.openai_config import OpenAISettings


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _tick_time() -> datetime:
    return datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def test_cycle_purges_then_vacuums_every_tick() -> None:
    clock = _Clock(_tick_time())
    calls: list[str] = []
    maintenance = RetentionMaintenance(
        purgers=(lambda: calls.append("purge"),),
        vacuum=lambda: calls.append("vacuum"),
        clock=clock,
    )

    maintenance.run_cycle()
    clock.now += timedelta(days=1)
    maintenance.run_cycle()

    assert calls == ["purge", "vacuum", "purge", "vacuum"]
    assert maintenance.status()["last_vacuum_at"] == "2026-09-13T03:00:00+00:00"


def test_startup_only_purges() -> None:
    calls: list[str] = []
    maintenance = RetentionMaintenance(
        purgers=(lambda: calls.append("purge"),),
        vacuum=lambda: calls.append("vacuum"),
    )

    assert maintenance.run_startup() is True

    assert calls == ["purge"]


def test_startup_failure_stays_flagged_until_a_purge_succeeds() -> None:
    attempts = {"count": 0}

    def flaky_purge() -> None:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise PersistenceError("locked")

    maintenance = RetentionMaintenance(purgers=(flaky_purge,), vacuum=lambda: None)

    assert maintenance.run_startup() is False
    assert maintenance.healthy is False
    assert maintenance.status()["startup_purge_failed"] is True

    maintenance.run_cycle()

    assert maintenance.healthy is True
    assert maintenance.status() == {
        **maintenance.status(),
        "startup_purge_failed": False,
        "last_purge_failed": False,
    }


def test_vacuum_failure_is_recorded_without_stopping_purges() -> None:
    def failing_vacuum() -> None:
        raise PersistenceError("busy")

    maintenance = RetentionMaintenance(
        purgers=(lambda: None,), vacuum=failing_vacuum, clock=_Clock(_tick_time())
    )

    maintenance.run_cycle()

    assert maintenance.healthy is True
    assert maintenance.status()["last_vacuum_failed"] is True
    assert maintenance.status()["last_vacuum_at"] is None


def test_next_run_is_today_at_three_utc_when_still_ahead() -> None:
    maintenance = RetentionMaintenance(purgers=(), vacuum=lambda: None)

    now = datetime(2026, 9, 12, 1, 30, tzinfo=timezone.utc)

    assert maintenance.next_run(now) == datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def test_next_run_rolls_to_tomorrow_once_three_utc_has_passed() -> None:
    maintenance = RetentionMaintenance(purgers=(), vacuum=lambda: None)

    exactly = datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)
    later = datetime(2026, 9, 12, 17, 45, tzinfo=timezone.utc)

    assert maintenance.next_run(exactly) == datetime(2026, 9, 13, 3, 0, tzinfo=timezone.utc)
    assert maintenance.next_run(later) == datetime(2026, 9, 13, 3, 0, tzinfo=timezone.utc)


def test_next_run_uses_utc_regardless_of_caller_timezone() -> None:
    maintenance = RetentionMaintenance(purgers=(), vacuum=lambda: None)
    warsaw = timezone(timedelta(hours=2))

    now = datetime(2026, 9, 12, 4, 30, tzinfo=warsaw)  # 02:30 UTC

    assert maintenance.next_run(now) == datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def test_run_forever_fires_at_the_scheduled_time_and_stops() -> None:
    calls: list[str] = []
    real_now = datetime.now(timezone.utc)
    soon = (real_now + timedelta(milliseconds=200)).timetz()
    maintenance = RetentionMaintenance(
        purgers=(lambda: calls.append("purge"),),
        vacuum=lambda: calls.append("vacuum"),
        run_at=soon,
    )

    async def scenario() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(maintenance.run_forever(stop))
        await asyncio.sleep(0.7)
        stop.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())

    assert calls == ["purge", "vacuum"]


def test_app_runs_startup_purge_through_maintenance_and_reports_status(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        status = client.get("/operations/status").json()["retention"]["maintenance"]

    assert status["ready"] is True
    assert status["startup_purge_failed"] is False
    assert status["last_purge_at"] is not None
    assert status["run_at"] == "03:00 UTC"
    assert datetime.fromisoformat(status["next_run_at"]) > datetime.now(timezone.utc)


def test_health_reports_startup_purge_failure(tmp_path, monkeypatch) -> None:
    from cv_validator.api import persistence

    def broken_purge(self):
        raise PersistenceError("locked")

    monkeypatch.setattr(persistence.PersistenceStore, "purge_expired", broken_purge)
    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        health = client.get("/health").json()

    assert health["ready"] is False
    assert health["capabilities"]["retention_purge"] == {
        "ready": False,
        "reason": "retention_purge_failed",
    }


def test_health_reports_retention_purge_ready_after_successful_startup(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        health = client.get("/health").json()

    assert health["capabilities"]["retention_purge"] == {"ready": True, "reason": None}
