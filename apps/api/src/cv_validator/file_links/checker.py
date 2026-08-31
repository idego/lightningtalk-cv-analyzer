from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Protocol
from urllib.parse import urljoin

from cv_validator.domain import (
    DocumentLink,
    LinkAssociation,
    LinkCheckResult,
    LinkInspection,
    LinkOutcomeStatus,
    LinkReasonCode,
    LinkRole,
)
from cv_validator.file_links.catalog import (
    ServiceDomainMatch,
    classify_service_domain,
    service_entry,
)
from cv_validator.file_links.normalization import (
    NormalizedURL,
    URLNormalizationError,
    normalize_url,
    sanitize_url_text,
)


LINK_CHECK_CONFIGURATION_VERSION = "link-check-config-v1"
LINK_CHECKER_VERSION = "public-link-checker-v1"
_CLAIM_ROLES = {
    LinkRole.PROFILE,
    LinkRole.PORTFOLIO,
    LinkRole.PROJECT,
    LinkRole.PUBLICATION,
    LinkRole.CREDENTIAL,
    LinkRole.CV_CLAIM,
}
_CLOUD_METADATA_ADDRESSES = frozenset({
    "169.254.169.254",
    "100.100.100.200",
    "fd00:ec2::254",
})


class LinkCheckConfigurationError(ValueError):
    pass


class LinkNetworkError(RuntimeError):
    """Expected checker failure that contains no request or response content."""


class LinkTimeoutError(LinkNetworkError):
    pass


class LinkResponseLimitError(LinkNetworkError):
    pass


class LinkBudgetError(LinkNetworkError):
    pass


class DNSResolver(Protocol):
    def resolve(self, hostname: str, port: int) -> tuple[str, ...]: ...


class LinkHTTPClient(Protocol):
    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
        connect_addresses: Sequence[str] = (),
    ) -> LinkHTTPResponse: ...


@dataclass(frozen=True)
class LinkHTTPResponse:
    status_code: int
    headers: Mapping[str, str]
    body_bytes: int = 0


@dataclass(frozen=True)
class LinkCheckConfig:
    enabled: bool = True
    allowed_protocols: tuple[str, ...] = ("https", "http")
    allowed_ports: tuple[int, ...] = (80, 443)
    timeout_seconds: float = 5.0
    max_response_bytes: int = 64 * 1024
    max_redirects: int = 3
    max_concurrency: int = 4
    max_retries: int = 0
    total_budget_seconds: float = 20.0
    user_agent: str = "CV-Validator-Link-Checker/1"
    configuration_version: str = LINK_CHECK_CONFIGURATION_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_protocols, (tuple, list)):
            raise LinkCheckConfigurationError("allowed_protocols must be a sequence")
        if any(not isinstance(protocol, str) for protocol in self.allowed_protocols):
            raise LinkCheckConfigurationError("allowed_protocols must contain strings")
        protocols = tuple(protocol.lower().strip() for protocol in self.allowed_protocols)
        if not protocols or any(protocol not in {"http", "https"} for protocol in protocols):
            raise LinkCheckConfigurationError("allowed_protocols must contain only HTTP or HTTPS")
        if len(set(protocols)) != len(protocols):
            raise LinkCheckConfigurationError("allowed_protocols must be unique")
        if not isinstance(self.allowed_ports, (tuple, list, set, frozenset)):
            raise LinkCheckConfigurationError("allowed_ports must be a sequence")
        if any(isinstance(port, bool) or not isinstance(port, int) for port in self.allowed_ports):
            raise LinkCheckConfigurationError("allowed_ports must contain integers")
        if not self.allowed_ports or any(not 1 <= port <= 65535 for port in self.allowed_ports):
            raise LinkCheckConfigurationError("allowed_ports must be valid TCP ports")
        if len(set(self.allowed_ports)) != len(self.allowed_ports):
            raise LinkCheckConfigurationError("allowed_ports must be unique")
        if not 0.1 <= self.timeout_seconds <= 60:
            raise LinkCheckConfigurationError("timeout_seconds must be between 0.1 and 60")
        if not 1024 <= self.max_response_bytes <= 10 * 1024 * 1024:
            raise LinkCheckConfigurationError("max_response_bytes is outside the safe range")
        if not 0 <= self.max_redirects <= 10:
            raise LinkCheckConfigurationError("max_redirects must be between 0 and 10")
        if not 1 <= self.max_concurrency <= 32:
            raise LinkCheckConfigurationError("max_concurrency must be between 1 and 32")
        if not 0 <= self.max_retries <= 3:
            raise LinkCheckConfigurationError("max_retries must be between 0 and 3")
        if not 0.1 <= self.total_budget_seconds <= 300:
            raise LinkCheckConfigurationError("total_budget_seconds is outside the safe range")
        if not self.user_agent.strip() or any(ord(char) < 32 for char in self.user_agent) or len(self.user_agent) > 128:
            raise LinkCheckConfigurationError("user_agent is invalid")
        if not self.configuration_version.strip():
            raise LinkCheckConfigurationError("configuration_version must not be empty")
        object.__setattr__(self, "allowed_protocols", protocols)
        object.__setattr__(self, "allowed_ports", tuple(int(port) for port in self.allowed_ports))

    @classmethod
    def from_env(cls) -> LinkCheckConfig:
        import os

        enabled = os.environ.get("CV_VALIDATOR_LINK_CHECK_ENABLED", "true").lower()
        return cls(
            enabled=enabled in {"1", "true", "yes", "on"},
            allowed_protocols=_csv(os.environ.get("CV_VALIDATOR_LINK_CHECK_PROTOCOLS", "https,http")),
            allowed_ports=_ports_env("CV_VALIDATOR_LINK_CHECK_PORTS", (80, 443)),
            timeout_seconds=_float_env("CV_VALIDATOR_LINK_CHECK_TIMEOUT_SECONDS", 5.0),
            max_response_bytes=_int_env("CV_VALIDATOR_LINK_CHECK_MAX_RESPONSE_BYTES", 64 * 1024),
            max_redirects=_int_env("CV_VALIDATOR_LINK_CHECK_MAX_REDIRECTS", 3),
            max_concurrency=_int_env("CV_VALIDATOR_LINK_CHECK_MAX_CONCURRENCY", 4),
            max_retries=_int_env("CV_VALIDATOR_LINK_CHECK_MAX_RETRIES", 0),
            total_budget_seconds=_float_env("CV_VALIDATOR_LINK_CHECK_TOTAL_BUDGET_SECONDS", 20.0),
            user_agent=os.environ.get("CV_VALIDATOR_LINK_CHECK_USER_AGENT", "CV-Validator-Link-Checker/1"),
        )


class SystemDNSResolver:
    def resolve(self, hostname: str, port: int) -> tuple[str, ...]:
        records = socket.getaddrinfo(
            hostname,
            port,
            type=socket.SOCK_STREAM,
        )
        return tuple(dict.fromkeys(record[4][0] for record in records))


class HttpxLinkHTTPClient:
    """Small HTTP adapter with pinned DNS destinations and bounded bodies."""

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
        connect_addresses: Sequence[str] = (),
    ) -> LinkHTTPResponse:
        try:
            import httpcore
        except ImportError as exc:  # pragma: no cover - packaging failure
            raise LinkNetworkError("http client unavailable") from exc

        if not connect_addresses:
            raise LinkNetworkError("validated destination addresses are required")
        backend = _ValidatedAddressBackend(httpcore, connect_addresses)
        parsed = httpcore.URL(url)
        request_headers = list(headers.items())
        if not any(key.lower() == "host" for key, _ in request_headers):
            authority = parsed.host.decode("ascii")
            if ":" in authority:
                authority = f"[{authority}]"
            if parsed.port is not None:
                authority = f"{authority}:{parsed.port}"
            request_headers.insert(0, ("Host", authority))
        pool = httpcore.ConnectionPool(
            ssl_context=(httpcore.default_ssl_context() if parsed.scheme == b"https" else None),
            max_connections=1,
            max_keepalive_connections=0,
            keepalive_expiry=0,
            network_backend=backend,
        )
        request = httpcore.Request(
            method,
            url,
            headers=request_headers,
            extensions={
                "sni_hostname": parsed.host.decode("ascii"),
                "timeout": {
                    "connect": timeout_seconds,
                    "read": timeout_seconds,
                    "write": timeout_seconds,
                    "pool": timeout_seconds,
                },
            },
        )
        try:
            response = pool.handle_request(request)
            try:
                body_bytes = 0
                if method == "GET":
                    for chunk in response.iter_stream():
                        body_bytes += len(chunk)
                        if body_bytes > max_response_bytes:
                            raise LinkResponseLimitError("response exceeded configured limit")
                return LinkHTTPResponse(
                    status_code=response.status,
                    headers={
                        key.decode("latin-1"): value.decode("latin-1")
                        for key, value in response.headers
                    },
                    body_bytes=body_bytes,
                )
            finally:
                response.close()
        except LinkResponseLimitError:
            raise
        except httpcore.TimeoutException as exc:
            raise LinkTimeoutError("link request timed out") from exc
        except httpcore.ConnectError as exc:
            if "ssl" in str(exc).lower() or "tls" in str(exc).lower():
                raise ssl.SSLError("link TLS negotiation failed") from exc
            raise LinkNetworkError("link connection failed") from exc
        except httpcore.NetworkError as exc:
            raise LinkNetworkError("link connection failed") from exc
        except httpcore.HTTPError as exc:
            raise LinkNetworkError("link request failed") from exc
        finally:
            pool.close()


class _ValidatedAddressBackend:
    """Connect only to addresses already validated by :class:`LinkInspector`."""

    def __init__(self, httpcore: Any, addresses: Sequence[str]) -> None:
        self._backend = httpcore.SyncBackend()
        self._addresses = tuple(dict.fromkeys(addresses))

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Any | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for address in self._addresses:
            try:
                return self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is not None:
            raise last_error
        raise OSError("validated destination addresses are empty")

    def sleep(self, seconds: float) -> None:
        self._backend.sleep(seconds)


class LinkInspector:
    def __init__(
        self,
        config: LinkCheckConfig | None = None,
        *,
        dns_resolver: DNSResolver | None = None,
        http_client: LinkHTTPClient | None = None,
        clock: Callable[[], float] | None = None,
        now: Callable[[], str] | None = None,
        metrics: Any | None = None,
    ) -> None:
        self.config = config or LinkCheckConfig()
        self.dns_resolver = dns_resolver or SystemDNSResolver()
        self.http_client = http_client or HttpxLinkHTTPClient()
        self.clock = clock or monotonic
        self.now = now or _utc_now
        self.metrics = metrics

    def inspect(self, links: Sequence[DocumentLink]) -> LinkInspection:
        started = self.clock()
        checked_at = self.now()
        if not links:
            return LinkInspection(
                links=(),
                checked_at=checked_at,
                configuration_version=self.config.configuration_version,
            )
        if self.config.max_concurrency == 1 or len(links) == 1:
            results = tuple(
                self._check_link(link, checked_at, started)
                for link in links
            )
        else:
            with ThreadPoolExecutor(max_workers=self.config.max_concurrency) as executor:
                futures = [
                    executor.submit(self._check_link, link, checked_at, started)
                    for link in links
                ]
                results = tuple(future.result() for future in futures)
        for result in results:
            if self.metrics is not None:
                try:
                    self.metrics.increment(
                        "link_checks_total",
                        status=result.status.value,
                        reason_code=result.reason_code.value,
                    )
                except Exception:  # noqa: BLE001
                    pass
        return LinkInspection(
            links=results,
            checked_at=checked_at,
            configuration_version=self.config.configuration_version,
        )

    def _check_link(
        self,
        link: DocumentLink,
        checked_at: str,
        started: float,
    ) -> LinkCheckResult:
        base = {
            "link_id": link.id,
            "displayed_value": _safe_display_value(
                link.displayed_value,
                allowed_ports=self.config.allowed_ports,
            ),
            "source": link.source,
            "association": link.association,
            "role": link.role,
            "source_page": link.page_number,
            "source_evidence": tuple(
                replace(
                    evidence,
                    excerpt=sanitize_url_text(
                        evidence.excerpt,
                        limit=512,
                        allowed_ports=self.config.allowed_ports,
                    ),
                )
                for evidence in link.evidence
            ),
            "source_location": link.source_location,
            "checked_at": checked_at,
            "configuration_version": self.config.configuration_version,
        }
        if link.target is None or not link.target.strip():
            return self._result(
                base,
                LinkOutcomeStatus.SUSPICIOUS,
                None,
                LinkReasonCode.INVALID_LINK_TARGET,
            )
        try:
            normalized = normalize_url(
                link.target,
                allowed_ports=self.config.allowed_ports,
            )
        except URLNormalizationError as exc:
            return self._result(
                base,
                LinkOutcomeStatus.SUSPICIOUS,
                None,
                _normalization_reason(exc.reason_code),
            )
        if normalized.scheme not in self.config.allowed_protocols:
            return self._result(
                base,
                LinkOutcomeStatus.SUSPICIOUS,
                normalized.sanitized_url,
                LinkReasonCode.UNSAFE_SCHEME,
            )
        if normalized.is_ip_literal and _blocked_ip(normalized.hostname):
            return self._result(
                base,
                LinkOutcomeStatus.SUSPICIOUS,
                normalized.sanitized_url,
                LinkReasonCode.UNSAFE_DESTINATION,
            )
        service = classify_service_domain(normalized.hostname)
        if service.lookalike:
            return self._result(
                base,
                LinkOutcomeStatus.SUSPICIOUS,
                normalized.sanitized_url,
                LinkReasonCode.SERVICE_DOMAIN_LOOKALIKE,
            )
        if link.association is LinkAssociation.MISMATCHED:
            return self._result(
                base,
                LinkOutcomeStatus.SUSPICIOUS,
                normalized.sanitized_url,
                LinkReasonCode.HYPERLINK_TARGET_MISMATCH,
            )
        if not self.config.enabled:
            return self._result(
                base,
                LinkOutcomeStatus.UNAVAILABLE,
                normalized.sanitized_url,
                LinkReasonCode.INSPECTION_DISABLED,
            )
        deadline = started + self.config.total_budget_seconds
        try:
            return self._check_network(
                link,
                normalized,
                service,
                base,
                deadline,
            )
        except Exception as exc:  # noqa: BLE001
            reason = _network_reason(exc)
            return self._result(
                base,
                LinkOutcomeStatus.UNAVAILABLE,
                normalized.sanitized_url,
                reason,
            )

    def _check_network(
        self,
        link: DocumentLink,
        initial: NormalizedURL,
        initial_service: ServiceDomainMatch,
        base: dict[str, Any],
        deadline: float,
    ) -> LinkCheckResult:
        current = initial
        current_addresses: tuple[str, ...] | None = None
        redirects = 0
        while True:
            if self.clock() >= deadline:
                return self._result(
                    base,
                    LinkOutcomeStatus.UNAVAILABLE,
                    current.sanitized_url,
                    LinkReasonCode.REQUEST_BUDGET_EXCEEDED,
                    terminal_registrable_domain=current.registrable_domain,
                )
            if current_addresses is None:
                current_addresses, address_error = self._resolve_destination(current)
            else:
                address_error = None
            if address_error is not None:
                reason, suspicious = address_error
                return self._result(
                    base,
                    LinkOutcomeStatus.SUSPICIOUS if suspicious else LinkOutcomeStatus.UNAVAILABLE,
                    current.sanitized_url,
                    reason,
                    terminal_registrable_domain=current.registrable_domain,
                )
            assert current_addresses is not None
            response = self._request_with_retries(
                current,
                deadline,
                connect_addresses=current_addresses,
            )
            status = response.status_code
            headers = _normalized_headers(response.headers)
            if 300 <= status <= 399:
                location = headers.get("location")
                if not location:
                    return self._result(
                        base,
                        LinkOutcomeStatus.UNAVAILABLE,
                        current.sanitized_url,
                        LinkReasonCode.REDIRECT_WITHOUT_LOCATION,
                        terminal_status=status,
                        terminal_registrable_domain=current.registrable_domain,
                    )
                if redirects >= self.config.max_redirects:
                    return self._result(
                        base,
                        LinkOutcomeStatus.UNAVAILABLE,
                        current.sanitized_url,
                        LinkReasonCode.REDIRECT_LIMIT,
                        terminal_status=status,
                        terminal_registrable_domain=current.registrable_domain,
                    )
                redirects += 1
                try:
                    next_url = normalize_url(
                        urljoin(current.sanitized_url, location),
                        allowed_ports=self.config.allowed_ports,
                    )
                except URLNormalizationError:
                    return self._result(
                        base,
                        LinkOutcomeStatus.SUSPICIOUS,
                        current.sanitized_url,
                        LinkReasonCode.UNSAFE_REDIRECT,
                        terminal_status=status,
                        terminal_registrable_domain=current.registrable_domain,
                    )
                if next_url.scheme not in self.config.allowed_protocols:
                    return self._result(
                        base,
                        LinkOutcomeStatus.SUSPICIOUS,
                        current.sanitized_url,
                        LinkReasonCode.UNSAFE_REDIRECT,
                        terminal_status=status,
                        terminal_registrable_domain=current.registrable_domain,
                    )
                if next_url.is_ip_literal and _blocked_ip(next_url.hostname):
                    return self._result(
                        base,
                        LinkOutcomeStatus.SUSPICIOUS,
                        current.sanitized_url,
                        LinkReasonCode.UNSAFE_REDIRECT,
                        terminal_status=status,
                        terminal_registrable_domain=current.registrable_domain,
                    )
                redirect_addresses, redirect_address_error = self._resolve_destination(next_url)
                if redirect_address_error is not None:
                    reason, suspicious = redirect_address_error
                    return self._result(
                        base,
                        LinkOutcomeStatus.SUSPICIOUS if suspicious else LinkOutcomeStatus.UNAVAILABLE,
                        current.sanitized_url,
                        LinkReasonCode.UNSAFE_REDIRECT if suspicious else reason,
                        terminal_status=status,
                        terminal_registrable_domain=current.registrable_domain,
                    )
                if not self._same_or_allowed_domain(initial, next_url, initial_service):
                    return self._result(
                        base,
                        LinkOutcomeStatus.SUSPICIOUS,
                        current.sanitized_url,
                        LinkReasonCode.UNRELATED_CROSS_DOMAIN_REDIRECT,
                        terminal_status=status,
                        terminal_registrable_domain=next_url.registrable_domain,
                    )
                current = next_url
                current_addresses = redirect_addresses
                continue

            if status in {405, 501}:
                return self._result(
                    base,
                    LinkOutcomeStatus.UNAVAILABLE,
                    initial.sanitized_url,
                    LinkReasonCode.METHOD_NOT_ALLOWED,
                    terminal_status=status,
                    terminal_registrable_domain=current.registrable_domain,
                )
            if not self._same_or_allowed_domain(initial, current, initial_service):
                return self._result(
                    base,
                    LinkOutcomeStatus.SUSPICIOUS,
                    initial.sanitized_url,
                    LinkReasonCode.UNRELATED_CROSS_DOMAIN_REDIRECT,
                    terminal_status=status,
                    terminal_registrable_domain=current.registrable_domain,
                )
            if status in {403, 429}:
                return self._result(
                    base,
                    LinkOutcomeStatus.UNAVAILABLE,
                    initial.sanitized_url,
                    LinkReasonCode.HTTP_FORBIDDEN if status == 403 else LinkReasonCode.RATE_LIMITED,
                    terminal_status=status,
                    terminal_registrable_domain=current.registrable_domain,
                )
            if _anti_bot(headers):
                return self._result(
                    base,
                    LinkOutcomeStatus.UNAVAILABLE,
                    initial.sanitized_url,
                    LinkReasonCode.ANTI_BOT,
                    terminal_status=status,
                    terminal_registrable_domain=current.registrable_domain,
                )
            if status in {404, 410} and link.role in _CLAIM_ROLES:
                return self._result(
                    base,
                    LinkOutcomeStatus.SUSPICIOUS,
                    initial.sanitized_url,
                    LinkReasonCode.DECLARED_LINK_NOT_FOUND,
                    terminal_status=status,
                    terminal_registrable_domain=current.registrable_domain,
                )
            if 200 <= status <= 299:
                return self._result(
                    base,
                    LinkOutcomeStatus.REACHABLE,
                    initial.sanitized_url,
                    LinkReasonCode.REACHABLE,
                    terminal_status=status,
                    terminal_registrable_domain=current.registrable_domain,
                )
            return self._result(
                base,
                LinkOutcomeStatus.UNAVAILABLE,
                initial.sanitized_url,
                LinkReasonCode.HTTP_STATUS_UNAVAILABLE,
                terminal_status=status,
                terminal_registrable_domain=current.registrable_domain,
            )

    def _validate_destination(
        self,
        url: NormalizedURL,
    ) -> tuple[LinkReasonCode, bool] | None:
        _, error = self._resolve_destination(url)
        return error

    def _resolve_destination(
        self,
        url: NormalizedURL,
    ) -> tuple[tuple[str, ...], tuple[LinkReasonCode, bool] | None]:
        if url.is_ip_literal:
            if _blocked_ip(url.hostname):
                return (), (LinkReasonCode.UNSAFE_DESTINATION, True)
            return (url.hostname,), None
        try:
            addresses = self.dns_resolver.resolve(url.hostname, url.port)
        except socket.gaierror:
            return (), (LinkReasonCode.DNS_FAILURE, False)
        except OSError:
            return (), (LinkReasonCode.DNS_FAILURE, False)
        if not addresses:
            return (), (LinkReasonCode.DNS_FAILURE, False)
        if any(_blocked_ip(address) for address in addresses):
            return (), (LinkReasonCode.UNSAFE_DESTINATION, True)
        return tuple(addresses), None

    def _request_with_retries(
        self,
        url: NormalizedURL,
        deadline: float,
        *,
        connect_addresses: Sequence[str],
    ) -> LinkHTTPResponse:
        attempts = 0
        while True:
            remaining = deadline - self.clock()
            if remaining <= 0:
                raise LinkBudgetError("link request budget exhausted")
            attempts += 1
            timeout = min(self.config.timeout_seconds, remaining)
            try:
                response = self.http_client.request(
                    "HEAD",
                    url.sanitized_url,
                    headers={"User-Agent": self.config.user_agent},
                    timeout_seconds=timeout,
                    max_response_bytes=self.config.max_response_bytes,
                    connect_addresses=connect_addresses,
                )
                if response.status_code in {405, 501}:
                    response = self.http_client.request(
                        "GET",
                        url.sanitized_url,
                        headers={"User-Agent": self.config.user_agent},
                        timeout_seconds=min(self.config.timeout_seconds, deadline - self.clock()),
                        max_response_bytes=self.config.max_response_bytes,
                        connect_addresses=connect_addresses,
                    )
                if _response_exceeds_limit(response, self.config.max_response_bytes):
                    raise LinkResponseLimitError("response exceeded configured limit")
                return response
            except (LinkResponseLimitError, LinkBudgetError):
                raise
            except (LinkTimeoutError, LinkNetworkError, OSError, ssl.SSLError):
                if attempts > self.config.max_retries:
                    raise

    def _same_or_allowed_domain(
        self,
        initial: NormalizedURL,
        current: NormalizedURL,
        service: ServiceDomainMatch,
    ) -> bool:
        if initial.registrable_domain == current.registrable_domain:
            return True
        if service.service is None:
            return False
        entry = service_entry(service.service)
        if entry is None:
            return False
        return (
            current.registrable_domain in entry.recognized_hosts
            or current.registrable_domain in entry.allowed_redirect_domains
            or initial.registrable_domain in entry.recognized_hosts
            or initial.registrable_domain in entry.allowed_redirect_domains
        )

    def _result(
        self,
        base: dict[str, Any],
        status: LinkOutcomeStatus,
        sanitized_target: str | None,
        reason_code: LinkReasonCode,
        *,
        terminal_status: int | None = None,
        terminal_registrable_domain: str | None = None,
    ) -> LinkCheckResult:
        return LinkCheckResult(
            **base,
            status=status,
            sanitized_target=sanitized_target,
            reason_code=reason_code,
            terminal_status=terminal_status,
            terminal_registrable_domain=terminal_registrable_domain,
            title=_title_for(reason_code),
        )


def inspect_document_links(
    links: Sequence[DocumentLink],
    config: LinkCheckConfig | None = None,
    *,
    dns_resolver: DNSResolver | None = None,
    http_client: LinkHTTPClient | None = None,
    clock: Callable[[], float] | None = None,
    now: Callable[[], str] | None = None,
    metrics: Any | None = None,
) -> LinkInspection:
    return LinkInspector(
        config,
        dns_resolver=dns_resolver,
        http_client=http_client,
        clock=clock,
        now=now,
        metrics=metrics,
    ).inspect(links)


def _blocked_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    return (
        str(address) in _CLOUD_METADATA_ADDRESSES
        or address.is_loopback
        or address.is_private
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _normalization_reason(reason: str) -> LinkReasonCode:
    return {
        "unsafe_scheme": LinkReasonCode.UNSAFE_SCHEME,
        "embedded_credentials": LinkReasonCode.EMBEDDED_CREDENTIALS,
        "disallowed_port": LinkReasonCode.DISALLOWED_PORT,
        "invalid_host": LinkReasonCode.INVALID_HOST,
    }.get(reason, LinkReasonCode.INVALID_LINK_TARGET)


def _network_reason(exc: Exception) -> LinkReasonCode:
    if isinstance(exc, LinkBudgetError):
        return LinkReasonCode.REQUEST_BUDGET_EXCEEDED
    if isinstance(exc, LinkResponseLimitError):
        return LinkReasonCode.RESPONSE_LIMIT
    if isinstance(exc, LinkTimeoutError) or isinstance(exc, TimeoutError):
        return LinkReasonCode.TIMEOUT
    if isinstance(exc, ssl.SSLError):
        return LinkReasonCode.TLS_FAILURE
    if isinstance(exc, socket.gaierror):
        return LinkReasonCode.DNS_FAILURE
    return LinkReasonCode.CONNECTION_FAILURE


def _normalized_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in headers.items()}


def _response_exceeds_limit(response: LinkHTTPResponse, limit: int) -> bool:
    if response.body_bytes > limit:
        return True
    content_length = _normalized_headers(response.headers).get("content-length")
    if content_length is None:
        return False
    try:
        return int(content_length) > limit
    except ValueError:
        return False


def _anti_bot(headers: Mapping[str, str]) -> bool:
    signals = ("captcha", "challenge", "cf-mitigated", "bot detected", "automated access")
    return any(
        signal in f"{key}:{value}".lower()
        for key, value in headers.items()
        for signal in signals
    )


def _safe_display_value(
    value: str | None,
    *,
    allowed_ports: tuple[int, ...] = (80, 443),
) -> str | None:
    if value is None:
        return None
    sanitized = sanitize_url_text(
        value,
        limit=2048,
        allowed_ports=allowed_ports,
    )
    return sanitized or None


def _title_for(reason: LinkReasonCode) -> str:
    return {
        LinkReasonCode.REACHABLE: "Link was reachable.",
        LinkReasonCode.HYPERLINK_TARGET_MISMATCH: "Displayed link differs from its target.",
        LinkReasonCode.SERVICE_DOMAIN_LOOKALIKE: "Link uses a lookalike service domain.",
        LinkReasonCode.UNSAFE_SCHEME: "Link uses an unsafe scheme.",
        LinkReasonCode.EMBEDDED_CREDENTIALS: "Link contains embedded credentials.",
        LinkReasonCode.INVALID_HOST: "Link host could not be safely parsed.",
        LinkReasonCode.DISALLOWED_PORT: "Link uses a disallowed port.",
        LinkReasonCode.UNSAFE_DESTINATION: "Link resolves to an unsafe destination.",
        LinkReasonCode.UNSAFE_REDIRECT: "Link redirects to an unsafe destination.",
        LinkReasonCode.UNRELATED_CROSS_DOMAIN_REDIRECT: "Link redirects to an unrelated domain.",
        LinkReasonCode.DECLARED_LINK_NOT_FOUND: "Declared CV link was not found.",
        LinkReasonCode.INVALID_LINK_TARGET: "Embedded link target is invalid.",
        LinkReasonCode.INSPECTION_DISABLED: "Link check was not available.",
        LinkReasonCode.DNS_FAILURE: "Link check could not resolve the host.",
        LinkReasonCode.CONNECTION_FAILURE: "Link check could not connect.",
        LinkReasonCode.TIMEOUT: "Link check timed out.",
        LinkReasonCode.TLS_FAILURE: "Link check could not establish TLS.",
        LinkReasonCode.RESPONSE_LIMIT: "Link response exceeded the configured limit.",
        LinkReasonCode.REDIRECT_LIMIT: "Link redirect limit was reached.",
        LinkReasonCode.HTTP_FORBIDDEN: "Link blocked automated access.",
        LinkReasonCode.RATE_LIMITED: "Link check was rate limited.",
        LinkReasonCode.ANTI_BOT: "Link check encountered an anti-bot response.",
        LinkReasonCode.REQUEST_BUDGET_EXCEEDED: "Link check budget was exhausted.",
        LinkReasonCode.METHOD_NOT_ALLOWED: "Link did not support the checked methods.",
        LinkReasonCode.HTTP_STATUS_UNAVAILABLE: "Link outcome was inconclusive.",
        LinkReasonCode.REDIRECT_WITHOUT_LOCATION: "Link returned an incomplete redirect.",
    }[reason]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _int_env(name: str, default: int) -> int:
    import os

    try:
        return int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise LinkCheckConfigurationError(f"{name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    import os

    try:
        return float(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise LinkCheckConfigurationError(f"{name} must be a number") from exc


def _ports_env(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    import os

    raw = os.environ.get(name)
    if raw is None:
        return default
    values = _csv(raw)
    try:
        return tuple(int(value) for value in values)
    except ValueError as exc:
        raise LinkCheckConfigurationError(f"{name} must contain integers") from exc
