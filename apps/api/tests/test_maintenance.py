from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, time, timedelta, timezone

from fastapi.testclient import TestClient

from cv_validator.api.app import create_app
import pytest

from cv_validator.api.maintenance import RetentionMaintenance, parse_maintenance_time
from cv_validator.errors import PersistenceError
from cv_validator.openai_config import OpenAISettings


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


def _scheduled_moment() -> datetime:
    """2026-09-12 03:00 UTC, the default daily run time on a fixed date."""
    return datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def _maintenance_at(now: datetime) -> RetentionMaintenance:
    return RetentionMaintenance(purgers=(), vacuum=lambda: None, clock=_Clock(now))


def test_cycle_purges_then_vacuums_every_tick() -> None:
    clock = _Clock(_scheduled_moment())
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
        purgers=(lambda: None,), vacuum=failing_vacuum, clock=_Clock(_scheduled_moment())
    )

    maintenance.run_cycle()

    assert maintenance.healthy is True
    assert maintenance.status()["last_vacuum_failed"] is True
    assert maintenance.status()["last_vacuum_at"] is None


def test_next_run_is_today_at_three_utc_when_still_ahead() -> None:
    maintenance = _maintenance_at(datetime(2026, 9, 12, 1, 30, tzinfo=timezone.utc))

    assert maintenance.next_run() == datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def test_next_run_rolls_to_tomorrow_once_three_utc_has_passed() -> None:
    exactly = _maintenance_at(datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc))
    later = _maintenance_at(datetime(2026, 9, 12, 17, 45, tzinfo=timezone.utc))

    assert exactly.next_run() == datetime(2026, 9, 13, 3, 0, tzinfo=timezone.utc)
    assert later.next_run() == datetime(2026, 9, 13, 3, 0, tzinfo=timezone.utc)


def test_next_run_uses_utc_regardless_of_clock_timezone() -> None:
    warsaw = timezone(timedelta(hours=2))
    maintenance = _maintenance_at(datetime(2026, 9, 12, 4, 30, tzinfo=warsaw))  # 02:30 UTC

    assert maintenance.next_run() == datetime(2026, 9, 12, 3, 0, tzinfo=timezone.utc)


def test_run_forever_fires_at_the_scheduled_time_and_stops() -> None:
    calls: list[str] = []
    soon = (datetime.now(timezone.utc) + timedelta(milliseconds=150)).timetz()
    maintenance = RetentionMaintenance(
        purgers=(lambda: calls.append("purge"),),
        vacuum=lambda: calls.append("vacuum"),
        run_at=soon,
    )

    async def scenario() -> None:
        stop = asyncio.Event()
        task = asyncio.create_task(maintenance.run_forever(stop))
        deadline = asyncio.get_running_loop().time() + 5
        while not calls and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.02)
        stop.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())

    # One tick ran purge then vacuum; the next tick is a day away so nothing else fires.
    assert calls == ["purge", "vacuum"]


def test_purge_records_raw_sqlite_errors_instead_of_raising() -> None:
    def locked() -> None:
        raise sqlite3.OperationalError("database is locked")

    maintenance = RetentionMaintenance(purgers=(locked,), vacuum=lambda: None)

    assert maintenance.run_startup() is False
    assert maintenance.healthy is False
    maintenance.run_cycle()
    assert maintenance.status()["last_purge_failed"] is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, time(3, 0, tzinfo=timezone.utc)),
        ("", time(3, 0, tzinfo=timezone.utc)),
        ("05:30", time(5, 30, tzinfo=timezone.utc)),
        (" 23:59 ", time(23, 59, tzinfo=timezone.utc)),
        ("00:00", time(0, 0, tzinfo=timezone.utc)),
    ],
)
def test_parse_maintenance_time_accepts_hh_mm_utc(value, expected) -> None:
    assert parse_maintenance_time(value) == expected


@pytest.mark.parametrize("value", ["3am", "25:00", "03:00:30", "03:00:00", "03:00+02:00", "3", "03", "3:00"])
def test_parse_maintenance_time_rejects_other_formats(value) -> None:
    with pytest.raises(ValueError, match="CV_VALIDATOR_MAINTENANCE_TIME_UTC"):
        parse_maintenance_time(value)


def test_app_reads_maintenance_time_from_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CV_VALIDATOR_MAINTENANCE_TIME_UTC", "05:30")
    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        status = client.get("/operations/status").json()["retention"]["maintenance"]

    assert status["run_at"] == "05:30 UTC"
    assert datetime.fromisoformat(status["next_run_at"]).timetz() == time(5, 30, tzinfo=timezone.utc)


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


def test_request_path_purge_clears_the_startup_failure_flag(tmp_path, monkeypatch) -> None:
    from cv_validator.api import persistence

    real_purge = persistence.PersistenceStore._purge_expired
    attempts = {"count": 0}

    def flaky_purge(self):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise sqlite3.OperationalError("database is locked")
        return real_purge(self)

    monkeypatch.setattr(persistence.PersistenceStore, "_purge_expired", flaky_purge)
    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        assert client.get("/health").json()["ready"] is False

        assert client.get("/analyses", headers={"X-Analysis-Owner-Id": "owner"}).status_code == 200

        health = client.get("/health").json()
        status = client.get("/operations/status").json()["retention"]["maintenance"]

    assert health["capabilities"]["retention_purge"] == {"ready": True, "reason": None}
    assert status["startup_purge_failed"] is False
    assert status["last_purge_failed"] is False


def test_request_path_purge_failure_sets_the_flag(tmp_path, monkeypatch) -> None:
    from cv_validator.api import persistence

    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        assert client.get("/health").json()["capabilities"]["retention_purge"]["ready"] is True

        def broken(self):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(persistence.PersistenceStore, "_purge_expired", broken)
        with pytest.raises(PersistenceError):
            client.get("/analyses", headers={"X-Analysis-Owner-Id": "owner"})

        health = client.get("/health").json()

    assert health["capabilities"]["retention_purge"]["ready"] is False


def test_health_reports_retention_purge_ready_after_successful_startup(tmp_path) -> None:
    app = create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    with TestClient(app) as client:
        health = client.get("/health").json()

    assert health["capabilities"]["retention_purge"] == {"ready": True, "reason": None}
