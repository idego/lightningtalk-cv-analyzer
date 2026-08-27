from __future__ import annotations

import ipaddress
import posixpath
import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit, urlunsplit


class URLNormalizationError(ValueError):
    """Raised when an uploaded link cannot be represented safely."""

    def __init__(self, reason_code: str, message: str | None = None) -> None:
        self.reason_code = reason_code
        super().__init__(message or reason_code)


@dataclass(frozen=True)
class NormalizedURL:
    """A URL with credentials, query material, and fragments removed."""

    original: str
    sanitized_url: str
    scheme: str
    hostname: str
    port: int
    registrable_domain: str
    is_ip_literal: bool
    comparison_key: str

    @property
    def url(self) -> str:
        return self.sanitized_url


_CONTROL_OR_SPACE = re.compile(r"[\x00-\x20\x7f]")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_URL_TOKEN = re.compile(r"(?i)(?:https?://|www\.)[^\s<>\"']+")
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(
    value: str,
    *,
    allowed_ports: tuple[int, ...] | set[int] | frozenset[int] = (80, 443),
) -> NormalizedURL:
    if not isinstance(value, str) or not value.strip():
        raise URLNormalizationError("invalid_host", "URL must be a non-empty string")
    original = value.strip()
    if _CONTROL_OR_SPACE.search(original) or "\\" in original:
        raise URLNormalizationError("invalid_host", "URL contains unsafe delimiters")

    bare = urlsplit(original)
    has_authority = "://" in original
    if bare.scheme and not has_authority:
        if not re.fullmatch(r"[^/:?#]+:\d+(?:[/?#].*)?", original):
            if bare.scheme.lower() not in {"http", "https"}:
                raise URLNormalizationError("unsafe_scheme", "only HTTP and HTTPS are supported")
            raise URLNormalizationError("invalid_host", "URL scheme is missing an authority")
    if not has_authority and original.startswith("//"):
        raise URLNormalizationError("invalid_host", "scheme-relative URLs are not accepted")
    candidate = original if has_authority else f"https://{original}"
    try:
        parsed = urlsplit(candidate)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise URLNormalizationError("invalid_host", "URL parser rejected the host") from exc

    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise URLNormalizationError("unsafe_scheme", "only HTTP and HTTPS are supported")
    if not hostname:
        raise URLNormalizationError("invalid_host", "URL host is missing")
    authority = parsed.netloc.rsplit("@", 1)[-1]
    if authority.endswith(":") or (authority.endswith("]:") and "]" in authority):
        raise URLNormalizationError("invalid_host", "URL port is empty")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise URLNormalizationError("embedded_credentials", "URL credentials are not allowed")

    normalized_host, is_ip_literal = _normalize_host(hostname, parsed)
    selected_port = _DEFAULT_PORTS[scheme] if port is None else port
    allowed = {int(item) for item in allowed_ports}
    if selected_port not in allowed:
        raise URLNormalizationError("disallowed_port", "URL port is not allowlisted")

    if len(parsed.path) > 4096:
        raise URLNormalizationError("invalid_host", "URL path is too long")
    path = _normalize_path(parsed.path)
    rendered_host = f"[{normalized_host}]" if is_ip_literal and ":" in normalized_host else normalized_host
    rendered_port = "" if selected_port == _DEFAULT_PORTS[scheme] else f":{selected_port}"
    sanitized_url = urlunsplit((scheme, f"{rendered_host}{rendered_port}", path, "", ""))
    comparison_host = normalized_host.removeprefix("www.")
    comparison_port = "" if selected_port == _DEFAULT_PORTS[scheme] else f":{selected_port}"
    comparison_key = urlunsplit(
        (scheme, f"{comparison_host}{comparison_port}", path.rstrip("/") or "/", "", "")
    )
    return NormalizedURL(
        original=original,
        sanitized_url=sanitized_url,
        scheme=scheme,
        hostname=normalized_host,
        port=selected_port,
        registrable_domain=registrable_domain(normalized_host),
        is_ip_literal=is_ip_literal,
        comparison_key=comparison_key,
    )


def registrable_domain(hostname: str) -> str:
    """Return a conservative registrable-domain approximation without network I/O."""

    host = hostname.strip().lower().rstrip(".")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return host
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if labels[-2:] in (["co", "uk"], ["com", "au"], ["co", "jp"], ["com", "br"]):
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _normalize_host(hostname: str, parsed: SplitResult) -> tuple[str, bool]:
    raw_host = hostname.strip()
    if "%" in raw_host:
        raise URLNormalizationError("invalid_host", "encoded or scoped hosts are not allowed")
    try:
        ip_value = ipaddress.ip_address(raw_host)
    except ValueError:
        ip_value = None
    if ip_value is not None:
        return ip_value.compressed.lower(), True

    if "[" in parsed.netloc or "]" in parsed.netloc:
        raise URLNormalizationError("invalid_host", "IPv6 brackets are malformed")
    try:
        normalized = raw_host.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError as exc:
        raise URLNormalizationError("invalid_host", "host IDNA conversion failed") from exc
    if len(normalized) > 253 or not normalized or ".." in normalized:
        raise URLNormalizationError("invalid_host", "host name is malformed")
    labels = normalized.split(".")
    if any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise URLNormalizationError("invalid_host", "host label is malformed")
    return normalized, False


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    normalized = posixpath.normpath(path)
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    if path.endswith("/") and not normalized.endswith("/"):
        normalized += "/"
    return normalized


def sanitize_url_text(
    value: str,
    *,
    limit: int = 2048,
    allowed_ports: tuple[int, ...] | set[int] | frozenset[int] = (80, 443),
) -> str:
    """Keep reviewer text while removing URL credentials, queries, and fragments."""

    if not isinstance(value, str) or _CONTROL.search(value):
        return ""

    def replace_token(match: re.Match[str]) -> str:
        token = match.group(0)
        trailing = ""
        while token and token[-1] in ".,;:!?)]}":
            trailing = token[-1] + trailing
            token = token[:-1]
        try:
            sanitized = normalize_url(token, allowed_ports=allowed_ports).sanitized_url
        except URLNormalizationError:
            return "[invalid-link]" + trailing
        if match.group(0).lower().startswith("www."):
            sanitized = sanitized.removeprefix("https://")
        return sanitized + trailing

    return _URL_TOKEN.sub(replace_token, value).strip()[:limit]
