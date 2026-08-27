from __future__ import annotations

from dataclasses import dataclass

from cv_validator.file_links.normalization import registrable_domain


SERVICE_CATALOG_VERSION = "service-host-catalog-v1"


@dataclass(frozen=True)
class ServiceCatalogEntry:
    name: str
    official_hosts: frozenset[str]
    aliases: frozenset[str] = frozenset()
    allowed_redirect_domains: frozenset[str] = frozenset()

    @property
    def recognized_hosts(self) -> frozenset[str]:
        return self.official_hosts | self.aliases


@dataclass(frozen=True)
class ServiceDomainMatch:
    service: str | None
    hostname: str
    registrable_domain: str
    official: bool
    allowed_redirect: bool
    lookalike: bool


SERVICE_CATALOG: tuple[ServiceCatalogEntry, ...] = (
    ServiceCatalogEntry(
        name="linkedin",
        official_hosts=frozenset({"linkedin.com"}),
        aliases=frozenset({"linkedin.cn"}),
        allowed_redirect_domains=frozenset({"lnkd.in"}),
    ),
    ServiceCatalogEntry(
        name="github",
        official_hosts=frozenset({"github.com", "github.io"}),
        aliases=frozenset({"gist.github.com"}),
        allowed_redirect_domains=frozenset(),
    ),
    ServiceCatalogEntry(
        name="behance",
        official_hosts=frozenset({"behance.net"}),
        allowed_redirect_domains=frozenset(),
    ),
    ServiceCatalogEntry(
        name="dribbble",
        official_hosts=frozenset({"dribbble.com"}),
        allowed_redirect_domains=frozenset(),
    ),
    ServiceCatalogEntry(
        name="orcid",
        official_hosts=frozenset({"orcid.org"}),
        allowed_redirect_domains=frozenset(),
    ),
    ServiceCatalogEntry(
        name="researchgate",
        official_hosts=frozenset({"researchgate.net"}),
        allowed_redirect_domains=frozenset(),
    ),
)


def classify_service_domain(hostname: str) -> ServiceDomainMatch:
    normalized = _normalize_hostname(hostname)
    domain = registrable_domain(normalized)
    for entry in SERVICE_CATALOG:
        official = _matches_entry(normalized, entry.recognized_hosts)
        allowed_redirect = domain in entry.allowed_redirect_domains
        if official or allowed_redirect:
            return ServiceDomainMatch(
                service=entry.name,
                hostname=normalized,
                registrable_domain=domain,
                official=official,
                allowed_redirect=allowed_redirect,
                lookalike=False,
            )
        if _looks_like_entry(normalized, entry):
            return ServiceDomainMatch(
                service=entry.name,
                hostname=normalized,
                registrable_domain=domain,
                official=False,
                allowed_redirect=False,
                lookalike=True,
            )
    return ServiceDomainMatch(
        service=None,
        hostname=normalized,
        registrable_domain=domain,
        official=False,
        allowed_redirect=False,
        lookalike=False,
    )


def service_entry(name: str) -> ServiceCatalogEntry | None:
    return next((entry for entry in SERVICE_CATALOG if entry.name == name), None)


def _normalize_hostname(hostname: str) -> str:
    try:
        return hostname.encode("idna").decode("ascii").lower().rstrip(".")
    except UnicodeError:
        return hostname.strip().lower().rstrip(".")


def _matches_entry(hostname: str, hosts: frozenset[str]) -> bool:
    return any(hostname == host or hostname.endswith(f".{host}") for host in hosts)


def _looks_like_entry(hostname: str, entry: ServiceCatalogEntry) -> bool:
    labels = hostname.split(".")
    for label in labels:
        compact = "".join(character for character in label if character.isalnum())
        for official_host in entry.official_hosts:
            service_label = official_host.split(".")[0].replace("-", "")
            if compact == service_label or _edit_distance_at_most_one(compact, service_label):
                return True
            if compact.startswith(service_label) and compact[len(service_label):] in {
                "login", "secure", "verify", "account", "profile", "support",
            }:
                return True
    return False


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) <= 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    index_left = index_right = differences = 0
    while index_left < len(shorter) and index_right < len(longer):
        if shorter[index_left] != longer[index_right]:
            differences += 1
            index_right += 1
            if differences > 1:
                return False
        else:
            index_left += 1
            index_right += 1
    return True
