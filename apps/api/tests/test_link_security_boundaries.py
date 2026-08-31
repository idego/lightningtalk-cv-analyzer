from __future__ import annotations

import socket

import httpcore
from cv_validator.file_links.checker import (
    HttpxLinkHTTPClient,
    LinkHTTPResponse,
    _ValidatedAddressBackend,
)


def test_validated_backend_connects_to_address_not_hostname(monkeypatch):
    calls = []

    class FakeSocket:
        def setsockopt(self, *args):
            pass

        def close(self):
            pass

    def fake_create_connection(address, timeout, source_address=None):
        calls.append(address)
        return FakeSocket()

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    backend = _ValidatedAddressBackend(httpcore, ("93.184.216.34",))

    stream = backend.connect_tcp("example.com", 443, timeout=1)
    stream.close()

    assert calls == [("93.184.216.34", 443)]


def test_http_client_preserves_host_and_sni_while_using_validated_addresses(monkeypatch):
    requests = []

    def fake_handle_request(pool, request):
        requests.append(request)
        return httpcore.Response(200, headers=[], content=[])

    monkeypatch.setattr(httpcore.ConnectionPool, "handle_request", fake_handle_request)
    client = HttpxLinkHTTPClient()

    response = client.request(
        "HEAD",
        "https://example.com/profile",
        headers={"User-Agent": "test"},
        timeout_seconds=1,
        max_response_bytes=1024,
        connect_addresses=("93.184.216.34",),
    )

    assert response == LinkHTTPResponse(200, {}, 0)
    assert len(requests) == 1
    request = requests[0]
    assert request.extensions["sni_hostname"] == "example.com"
    assert (b"host", b"example.com") in [
        (key.lower(), value) for key, value in request.headers
    ]
