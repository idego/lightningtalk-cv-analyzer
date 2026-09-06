from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from cv_validator.api.concurrency import AnalysisCancellationRegistry, ResearchLockRegistry


def test_cancellation_is_owner_scoped_consumable_and_bounded():
    registry = AnalysisCancellationRegistry()
    registry.request("owner", "request")
    assert registry.is_cancelled("owner", "request")
    assert not registry.is_cancelled("other", "request")
    assert not registry.is_cancelled("owner", None)
    registry.discard("owner", None)
    registry.discard("owner", "request")
    assert not registry.is_cancelled("owner", "request")

    for index in range(registry._MAX_ENTRIES):
        registry.request("owner", str(index))
    registry.request("owner", "0")
    registry.request("owner", "new")
    assert registry.is_cancelled("owner", "0")
    assert not registry.is_cancelled("owner", "1")
    assert registry.is_cancelled("owner", "new")


def test_research_locks_serialize_same_subject_without_blocking_other_subjects():
    registry = ResearchLockRegistry()
    waiting = Event()
    acquired = Event()

    def wait_for_subject():
        lease = registry.acquire("company:example")
        waiting.set()
        with lease:
            acquired.set()

    with ThreadPoolExecutor(max_workers=1) as executor:
        with registry.acquire("company:example"):
            future = executor.submit(wait_for_subject)
            assert waiting.wait(5)
            assert not acquired.is_set()
            with registry.acquire("company:other"):
                assert len(registry) == 2
            assert len(registry) == 1
        future.result(timeout=5)

    assert acquired.is_set()
    assert len(registry) == 0


def test_research_lock_is_released_when_work_fails():
    registry = ResearchLockRegistry()
    with pytest.raises(ValueError):
        with registry.acquire("subject"):
            raise ValueError("synthetic failure")
    assert len(registry) == 0
    with registry.acquire("subject"):
        assert len(registry) == 1
    assert len(registry) == 0
