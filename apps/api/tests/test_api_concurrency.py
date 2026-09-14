from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock

import pytest
from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.api.concurrency import AnalysisCancellationRegistry, ResearchLockRegistry
from cv_validator.openai_config import OpenAISettings


class BlockingStrategy:
    """Fake pipeline that parks every analysis until released and counts overlap."""

    name = "document-analysis"
    version = "document-analysis-test-v1"
    ready = True

    def __init__(self) -> None:
        self.release = Event()
        self.started = []
        self.running = 0
        self.max_running = 0
        self._lock = Lock()

    def analyze(self, request):
        with self._lock:
            self.running += 1
            self.max_running = max(self.max_running, self.running)
            started = Event()
            self.started.append(started)
        started.set()
        try:
            assert self.release.wait(10)
            return valid_report(
                request.sha256,
                source_format=request.source_format.value,
                strategy_name=self.name,
            )
        finally:
            with self._lock:
                self.running -= 1


def _post_analysis(client: TestClient, index: int):
    return client.post(
        "/analyze",
        files={"file": (f"cv-{index}.pdf", f"%PDF-1.7 text {index}".encode(), "application/pdf")},
        headers={"X-Analysis-Owner-Id": "owner-token", "X-Analysis-Request-Id": str(index)},
    )


def _run_analyses(tmp_path, limit: int, requests: int):
    strategy = BlockingStrategy()
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
            analysis_strategy=strategy,
            analysis_concurrency=limit,
        )
    )
    with ThreadPoolExecutor(max_workers=requests) as executor:
        futures = [executor.submit(_post_analysis, client, index) for index in range(requests)]
        deadline_reached = Event()
        deadline_reached.wait(1.0)
        started_before_release = len(strategy.started)
        strategy.release.set()
        responses = [future.result(timeout=15) for future in futures]
    return strategy, started_before_release, responses


def test_analyses_run_concurrently_up_to_the_limit_and_the_rest_wait(tmp_path):
    strategy, started_before_release, responses = _run_analyses(tmp_path, limit=2, requests=3)

    assert started_before_release == 2
    assert strategy.max_running == 2
    assert [response.status_code for response in responses] == [200, 200, 200]
    assert len({response.json()["analysis_id"] for response in responses}) == 3


def test_limit_of_one_keeps_analyses_serialized(tmp_path):
    strategy, started_before_release, responses = _run_analyses(tmp_path, limit=1, requests=2)

    assert started_before_release == 1
    assert strategy.max_running == 1
    assert [response.status_code for response in responses] == [200, 200]


def test_analysis_concurrency_env_rejects_values_below_one(tmp_path, monkeypatch):
    monkeypatch.setenv("CV_VALIDATOR_ANALYSIS_CONCURRENCY", "0")
    with pytest.raises(ValueError, match="CV_VALIDATOR_ANALYSIS_CONCURRENCY"):
        create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))


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
