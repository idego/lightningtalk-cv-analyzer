from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from conftest import valid_report
from cv_validator.api.app import create_app
from cv_validator.errors import PersistenceError
from cv_validator.openai_config import OpenAISettings


class FakeStrategy:
    name = "document-analysis"
    version = "document-analysis-test-v1"
    ready = True

    def analyze(self, request):
        return valid_report(
            request.sha256,
            source_format=request.source_format.value,
            strategy_name=self.name,
        )


def test_health_and_analysis_fail_honestly_without_ai_client(tmp_path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
        )
    )

    health = client.get("/health")
    response = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7", "application/pdf")},
        headers={"X-Analysis-Access-Token": "owner-token"},
    )

    assert health.json()["capabilities"]["base_analysis"] == {
        "ready": False,
        "strategy": None,
        "reason": "ai_client_unavailable",
    }
    assert health.json()["ready"] is False
    assert response.status_code == 503
    assert response.json()["detail"] == "analysis_strategy_unavailable"
    analysis_id = response.headers["X-Analysis-ID"]
    diagnostics = client.get(
        f"/analyses/{analysis_id}/diagnostics",
        headers={"X-Analysis-Access-Token": "owner-token"},
    )
    assert diagnostics.status_code == 200
    assert diagnostics.json()["analysis"]["status"] == "unavailable"
    assert client.get(
        f"/analyses/{analysis_id}",
        headers={"X-Analysis-Access-Token": "owner-token"},
    ).status_code == 404


def test_analysis_round_trip_uses_new_contract(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=FakeStrategy(),
    )
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers={"X-Analysis-Access-Token": "owner-token"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["contract_version"] == "base-analysis-v2"
    assert payload["strategy"]["name"] == "document-analysis"
    assert "score" not in payload
    assert "document_understanding" not in payload
    loaded = client.get(
        f"/analyses/{payload['analysis_id']}",
        headers={"X-Analysis-Access-Token": "owner-token"},
    )
    assert loaded.status_code == 200
    assert loaded.json()["base_analysis"]["education"][0]["added_by_reviewer"] is True


def test_upload_size_limit_is_enforced_before_analysis(tmp_path) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "reports.db",
            openai_settings=OpenAISettings(enabled=False),
            analysis_strategy=FakeStrategy(),
            upload_max_bytes=8,
        )
    )

    too_large = client.post(
        "/analyze",
        files={"file": ("one.pdf", b"%PDF-1.7 text", "application/pdf")},
    )

    assert too_large.status_code == 413
    assert too_large.json()["detail"] == "upload_size_limit_exceeded"


def test_analysis_lifecycle_is_owner_scoped(tmp_path) -> None:
    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=FakeStrategy(),
    )
    client = TestClient(app)
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    created = client.post(
        "/analyze",
        files={"file": ("candidate.pdf", b"%PDF-1.7 text", "application/pdf")},
        headers=owner_headers,
    ).json()
    analysis_id = created["analysis_id"]

    purge_expired = app.state.store.purge_expired
    purge_calls = 0

    def tracked_purge_expired():
        nonlocal purge_calls
        purge_calls += 1
        return purge_expired()

    app.state.store.purge_expired = tracked_purge_expired
    history = client.get("/analyses", headers=owner_headers)

    assert history.json()["analyses"][0]["analysis_id"] == analysis_id
    assert purge_calls == 1
    assert client.get(
        f"/analyses/{analysis_id}",
        headers={"X-Analysis-Access-Token": "another-owner"},
    ).status_code == 404
    assert client.delete(f"/analyses/{analysis_id}", headers=owner_headers).status_code == 200
    assert client.get(f"/analyses/{analysis_id}", headers=owner_headers).status_code == 404


def _analyze(client: TestClient, headers: dict[str, str], filename: str = "candidate.pdf") -> str:
    created = client.post(
        "/analyze",
        files={"file": (filename, b"%PDF-1.7 stored bytes", "application/pdf")},
        headers=headers,
    )
    assert created.status_code == 200
    return created.json()["analysis_id"]


def _document_app(tmp_path):
    return create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=FakeStrategy(),
    )


def _count_source_documents(app) -> int:
    with app.state.store._connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]


def test_source_document_is_stored_and_served_to_owner(tmp_path) -> None:
    app = _document_app(tmp_path)
    client = TestClient(app)
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    analysis_id = _analyze(client, owner_headers, filename='Życiorys "2026".pdf')

    history = client.get("/analyses", headers=owner_headers).json()["analyses"]
    assert history[0]["analysis_id"] == analysis_id
    assert history[0]["has_document"] is True

    document = client.get(f"/analyses/{analysis_id}/document", headers=owner_headers)
    assert document.status_code == 200
    assert document.content == b"%PDF-1.7 stored bytes"
    assert document.headers["content-type"] == "application/pdf"
    assert document.headers["cache-control"] == "private, no-store"
    disposition = document.headers["content-disposition"]
    assert disposition.startswith('inline; filename="')
    assert '"2026"' not in disposition
    assert "filename*=UTF-8''%C5%BByciorys" in disposition

    assert client.get(
        f"/analyses/{analysis_id}/document",
        headers={"X-Analysis-Access-Token": "another-owner"},
    ).status_code == 404
    assert client.get(f"/analyses/{analysis_id}/document").status_code == 404
    assert client.get("/analyses/missing/document", headers=owner_headers).status_code == 404


def test_docx_source_document_uses_docx_content_type(tmp_path) -> None:
    client = TestClient(_document_app(tmp_path))
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    analysis_id = _analyze(client, owner_headers, filename="candidate.docx")
    document = client.get(f"/analyses/{analysis_id}/document", headers=owner_headers)
    assert document.status_code == 200
    assert document.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert document.headers["content-disposition"] == 'inline; filename="candidate.docx"'


def test_source_document_storage_failure_does_not_fail_analysis(tmp_path) -> None:
    app = _document_app(tmp_path)
    client = TestClient(app)
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}

    def failing_persist(*_args, **_kwargs):
        raise PersistenceError("source document persistence failed")

    app.state.store.persist_source_document = failing_persist
    analysis_id = _analyze(client, owner_headers)

    history = client.get("/analyses", headers=owner_headers).json()["analyses"]
    assert history[0]["has_document"] is False
    assert client.get(f"/analyses/{analysis_id}/document", headers=owner_headers).status_code == 404
    diagnostics = client.get(f"/analyses/{analysis_id}/diagnostics", headers=owner_headers).json()
    assert any(
        event.get("event") == "persistence_failed"
        and event.get("error_code") == "source_document_persistence_error"
        for event in diagnostics["diagnostics"]
    )


def test_source_document_is_removed_with_analysis_deletion(tmp_path) -> None:
    app = _document_app(tmp_path)
    client = TestClient(app)
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    first = _analyze(client, owner_headers)
    second = _analyze(client, owner_headers)

    assert client.delete(f"/analyses/{first}", headers=owner_headers).status_code == 200
    assert app.state.store.get_source_document(first) is None
    assert app.state.store.get_source_document(second) is not None

    assert client.delete("/analyses", headers=owner_headers).json()["deleted"] == 1
    assert app.state.store.get_source_document(second) is None
    assert _count_source_documents(app) == 0


def test_source_document_is_purged_with_expired_analysis(tmp_path) -> None:
    app = _document_app(tmp_path)
    client = TestClient(app)
    owner_headers = {"X-Analysis-Access-Token": "owner-token"}
    analysis_id = _analyze(client, owner_headers)
    store = app.state.store
    stale = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
    with store._connect() as conn:
        for table in ("reports", "audit_log", "analysis_runs", "source_documents"):
            conn.execute(
                f"UPDATE {table} SET created_at = ? WHERE analysis_id = ?",
                (stale, analysis_id),
            )

    deleted = store.purge_expired()

    assert analysis_id in deleted["analysis_ids"]
    assert deleted["source_documents"] == 1
    assert store.get_source_document(analysis_id) is None
    assert _count_source_documents(app) == 0
    assert client.get(f"/analyses/{analysis_id}/document", headers=owner_headers).status_code == 404


def test_history_is_served_while_an_analysis_is_running(tmp_path) -> None:
    import threading

    started = threading.Event()
    release = threading.Event()

    class BlockingStrategy(FakeStrategy):
        def analyze(self, request):
            started.set()
            assert release.wait(timeout=10), "analysis was never released"
            return super().analyze(request)

    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=BlockingStrategy(),
    )
    headers = {"X-Analysis-Access-Token": "owner-token"}
    outcome: dict[str, object] = {}
    # The context manager shares one event loop across requests, like uvicorn.
    with TestClient(app) as client:
        _assert_history_served_during_analysis(client, headers, started, release, outcome)


def _assert_history_served_during_analysis(client, headers, started, release, outcome) -> None:
    import threading

    def run_analysis() -> None:
        outcome["analyze"] = client.post(
            "/analyze",
            files={"file": ("slow.pdf", b"%PDF-1.7 slow", "application/pdf")},
            headers=headers,
        ).status_code

    worker = threading.Thread(target=run_analysis)
    worker.start()
    try:
        assert started.wait(timeout=5), "analysis never started"
        history: dict[str, object] = {}
        reader = threading.Thread(
            target=lambda: history.update(
                status=client.get("/analyses", headers=headers).status_code
            )
        )
        reader.start()
        reader.join(timeout=3)
        assert not reader.is_alive(), "GET /analyses blocked behind the running analysis"
        assert history["status"] == 200
    finally:
        release.set()
        worker.join(timeout=10)
    assert outcome["analyze"] == 200


def test_cancelled_analysis_is_discarded_before_persistence(tmp_path) -> None:
    import threading

    started = threading.Event()
    release = threading.Event()

    class BlockingStrategy(FakeStrategy):
        def analyze(self, request):
            started.set()
            assert release.wait(timeout=10), "analysis was never released"
            return super().analyze(request)

    app = create_app(
        db_path=tmp_path / "reports.db",
        openai_settings=OpenAISettings(enabled=False),
        analysis_strategy=BlockingStrategy(),
    )
    headers = {"X-Analysis-Access-Token": "owner-token", "X-Analysis-Request-Id": "req-1"}
    outcome: dict[str, object] = {}
    with TestClient(app) as client:
        worker = threading.Thread(
            target=lambda: outcome.update(
                response=client.post(
                    "/analyze",
                    files={"file": ("slow.pdf", b"%PDF-1.7 slow", "application/pdf")},
                    headers=headers,
                )
            )
        )
        worker.start()
        try:
            assert started.wait(timeout=5), "analysis never started"
            cancel = client.post("/analyze/cancel", headers=headers)
            assert cancel.status_code == 202
        finally:
            release.set()
            worker.join(timeout=10)
        response = outcome["response"]
        assert response.status_code == 409
        assert response.json()["detail"] == "analysis_cancelled"
        analysis_id = response.headers["X-Analysis-ID"]
        assert client.get("/analyses", headers=headers).json()["analyses"] == []
        diagnostics = client.get(f"/analyses/{analysis_id}/diagnostics", headers=headers)
        assert diagnostics.json()["analysis"]["status"] == "cancelled"

        # A cancel from another owner does not touch this request id.
        client.post(
            "/analyze/cancel",
            headers={"X-Analysis-Access-Token": "other-token", "X-Analysis-Request-Id": "req-2"},
        )
        ok = client.post(
            "/analyze",
            files={"file": ("fast.pdf", b"%PDF-1.7 fast", "application/pdf")},
            headers={"X-Analysis-Access-Token": "owner-token", "X-Analysis-Request-Id": "req-2"},
        )
        assert ok.status_code == 200


def test_cancel_endpoint_requires_request_id(tmp_path) -> None:
    client = TestClient(
        create_app(db_path=tmp_path / "reports.db", openai_settings=OpenAISettings(enabled=False))
    )
    response = client.post("/analyze/cancel", headers={"X-Analysis-Access-Token": "owner-token"})
    assert response.status_code == 400
