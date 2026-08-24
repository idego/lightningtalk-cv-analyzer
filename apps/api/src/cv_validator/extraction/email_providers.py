from __future__ import annotations

from dataclasses import dataclass

from cv_validator.domain import (
    Authority,
    Candidate,
    CandidateKind,
    ComponentVersion,
    Observation,
    ObservationId,
    ObservationKind,
    ObservationStatus,
    Provenance,
)


COMMON_EMAIL_PROVIDER_CATALOG_VERSION = "2026-08-24-v1"
EMAIL_DOMAIN_TYPO_CLASSIFIER_VERSION = "1"


@dataclass(frozen=True)
class CommonEmailProviderDomain:
    domain: str
    family: str
    source_url: str


_GOOGLE_SOURCE = "https://support.google.com/mail/answer/56256"
_MICROSOFT_SOURCE = (
    "https://support.microsoft.com/en-us/outlook/"
    "add-or-remove-an-email-alias-in-outlook-com"
)
_YAHOO_SOURCE = "https://help.yahoo.com/kb/SLN2153.html"
_PROTON_SOURCE = "https://proton.me/support/addresses-and-aliases"
_APPLE_SOURCE = "https://support.apple.com/en-lamr/118230"
_ZOHO_SOURCE = "https://www.zoho.com/mail/how-to/create-an-email-account.html"
_ONET_SOURCE = (
    "https://pomoc.poczta.onet.pl/wp-content/uploads/2024/08/"
    "Regulamin_Onet_Poczta_20240812.pdf"
)
_WP_SOURCE = "https://pomoc.wp.pl/1login/nowe-konto-1login-z-nowym-adresem-pocztowym"
_WP_HISTORY_SOURCE = "https://holding.wp.pl/historia"
_INTERIA_SOURCE = (
    "https://pomoc.poczta.interia.pl/popularne-artykuly/"
    "news-parametry-do-konfiguracji-programow-pocztowych,nId,2136275"
)


def _entries(
    family: str,
    source_url: str,
    *domains: str,
) -> tuple[CommonEmailProviderDomain, ...]:
    return tuple(
        CommonEmailProviderDomain(domain, family, source_url)
        for domain in domains
    )


COMMON_EMAIL_PROVIDER_CATALOG = (
    *_entries("google", _GOOGLE_SOURCE, "gmail.com"),
    *_entries(
        "microsoft",
        _MICROSOFT_SOURCE,
        "outlook.com",
        "hotmail.com",
        "live.com",
        "msn.com",
    ),
    *_entries(
        "yahoo",
        _YAHOO_SOURCE,
        "yahoo.com",
        "myyahoo.com",
        "yahoo.co.uk",
        "yahoo.fr",
    ),
    *_entries(
        "proton",
        _PROTON_SOURCE,
        "proton.me",
        "protonmail.com",
        "pm.me",
        "protonmail.ch",
    ),
    *_entries("apple", _APPLE_SOURCE, "icloud.com", "me.com", "mac.com"),
    *_entries(
        "zoho",
        _ZOHO_SOURCE,
        "zohomail.com",
    ),
    *_entries("onet", _ONET_SOURCE, "onet.pl", "op.pl"),
    *_entries("wp-o2", _WP_SOURCE, "wp.pl", "o2.pl"),
    *_entries("wp-o2", _WP_HISTORY_SOURCE, "tlen.pl"),
    *_entries(
        "interia",
        _INTERIA_SOURCE,
        "interia.pl",
        "interia.eu",
        "interia.com",
        "poczta.fm",
        "vip.interia.pl",
        "intmail.pl",
        "interiowy.pl",
        "adresik.net",
        "pisz.to",
        "pacz.to",
        "ogarnij.se",
    ),
)

_CATALOG_BY_DOMAIN = {
    entry.domain: entry for entry in COMMON_EMAIL_PROVIDER_CATALOG
}


def classify_common_email_provider_typos(
    candidates: tuple[Candidate, ...],
) -> tuple[Observation, ...]:
    observations: list[Observation] = []
    for candidate in candidates:
        if candidate.kind is not CandidateKind.EMAIL:
            continue
        domain = candidate.value.rsplit("@", 1)[-1].casefold()
        if domain in _CATALOG_BY_DOMAIN or domain.count(".") != 1:
            continue
        matches = tuple(
            entry
            for entry in COMMON_EMAIL_PROVIDER_CATALOG
            if entry.domain.count(".") == 1
            and _edit_distance_at_most_one(domain, entry.domain) == 1
        )
        if len(matches) != 1:
            continue
        match = matches[0]
        observations.append(
            Observation(
                id=ObservationId(
                    f"observation:possible_email_domain_typo:{candidate.id}"
                ),
                kind=ObservationKind.POSSIBLE_EMAIL_DOMAIN_TYPO,
                status=ObservationStatus.INFORMATIONAL,
                subject_ids=(str(candidate.id),),
                values=(domain, match.domain),
                reason=(
                    f"The email domain differs by one character from the "
                    f"catalogued public-provider domain {match.domain}; confirm "
                    "the address before relying on it. This observation does "
                    "not establish whether the address, domain, person, or CV "
                    "is genuine or usable."
                ),
                provenance=Provenance(
                    authority=Authority.CODE,
                    evidence=candidate.provenance.evidence,
                    extractor=ComponentVersion(
                        "email-domain-typo-classification",
                        EMAIL_DOMAIN_TYPO_CLASSIFIER_VERSION,
                    ),
                    reference_data=ComponentVersion(
                        f"common-email-providers/{match.family}",
                        COMMON_EMAIL_PROVIDER_CATALOG_VERSION,
                        match.source_url,
                    ),
                ),
            )
        )
    return tuple(observations)


def _edit_distance_at_most_one(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2
    if len(left) > len(right):
        left, right = right, left
    if len(left) == len(right):
        differences = sum(a != b for a, b in zip(left, right))
        if differences <= 1:
            return differences
        for index in range(len(left) - 1):
            if (
                left[index] == right[index + 1]
                and left[index + 1] == right[index]
                and left[:index] == right[:index]
                and left[index + 2 :] == right[index + 2 :]
            ):
                return 1
        return 2
    index_left = index_right = differences = 0
    while index_left < len(left) and index_right < len(right):
        if left[index_left] == right[index_right]:
            index_left += 1
            index_right += 1
            continue
        differences += 1
        index_right += 1
        if differences > 1:
            return 2
    return 1
