from __future__ import annotations

import re
from typing import Callable

import phonenumbers

from cv_validator.config import WeightsConfig
from cv_validator.domain import AgreementDirection, ClaimedLocation, Signal, SignalStrength
from cv_validator.gazetteer.data import POSTAL_PATTERNS, TLD_TO_COUNTRY
from cv_validator.gazetteer.resolver import resolve_location
from cv_validator.ingestion import ParsedCV

Extractor = Callable[[ParsedCV, ClaimedLocation, WeightsConfig], list[Signal]]


def extract_all_signals(
    parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig
) -> list[Signal]:
    signals: list[Signal] = []
    for extractor in _EXTRACTORS:
        signals.extend(extractor(parsed, claim, weights))
    return signals


def _direction_for_country(
    observed_country: str | None, claim: ClaimedLocation
) -> AgreementDirection:
    if not observed_country or not claim.country_code:
        return AgreementDirection.NEUTRAL
    if observed_country == claim.country_code:
        return AgreementDirection.SUPPORTS
    return AgreementDirection.CONFLICTS


def _extract_phone(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["phone_country"]
    text = parsed.text
    ssn_pattern = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    matches = re.findall(r"(\+?\d[\d\s().-]{7,}\d)", text)
    for raw in matches:
        if ssn_pattern.search(raw):
            continue
        if not raw.strip().startswith("+") and len(re.sub(r"\D", "", raw)) < 10:
            continue
        try:
            parsed_num = phonenumbers.parse(raw, None if raw.strip().startswith("+") else "DE")
            if not phonenumbers.is_possible_number(parsed_num):
                continue
            region = phonenumbers.region_code_for_number(parsed_num)
            if not region:
                continue
            direction = _direction_for_country(region, claim)
            return [
                Signal(
                    name="phone_country",
                    strength=cfg.strength,
                    observed=f"{raw.strip()} ({region})",
                    inferred_country=region,
                    direction=direction,
                    weight=cfg.weight,
                    rationale=f"Phone number resolves to country {region}",
                )
            ]
        except phonenumbers.NumberParseException:
            continue
    return []


def _extract_address(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["address_postal"]
    contact = parsed.contact_text
    for country_code, pattern in POSTAL_PATTERNS.items():
        if re.search(pattern, contact, re.IGNORECASE):
            direction = _direction_for_country(country_code, claim)
            return [
                Signal(
                    name="address_postal",
                    strength=cfg.strength,
                    observed=f"Postal format matches {country_code}",
                    inferred_country=country_code,
                    direction=direction,
                    weight=cfg.weight,
                    rationale=f"Contact block postal pattern consistent with {country_code}",
                )
            ]
    return []


def _extract_employer(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["employer_location"]
    body = parsed.body_text
    exp_match = re.search(
        r"(?:experience|employment)[^\n]*\n(.*?)(?:\n(?:education|skills)\b|$)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    block = exp_match.group(1) if exp_match else body[:500]
    for line in block.splitlines()[:8]:
        resolution = resolve_location(line)
        if resolution.is_unambiguous and resolution.primary:
            country = resolution.primary.country_code
            direction = _direction_for_country(country, claim)
            return [
                Signal(
                    name="employer_location",
                    strength=cfg.strength,
                    observed=line.strip(),
                    inferred_country=country,
                    direction=direction,
                    weight=cfg.weight,
                    rationale="Most recent employer block references this location",
                )
            ]
    return []


def _extract_dates(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["date_format"]
    text = parsed.text
    us_dates = len(re.findall(r"\b(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])/\d{2,4}\b", text))
    eu_dates = len(re.findall(r"\b(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.\d{2,4}\b", text))
    eu_dates += len(re.findall(r"\b(0?[1-9]|[12]\d|3[01])/(0?[1-9]|1[0-2])/\d{2,4}\b", text))

    if us_dates == 0 and eu_dates == 0:
        return []

    if us_dates > eu_dates:
        inferred = "US"
        observed = "MM/DD date convention"
    elif eu_dates > us_dates:
        inferred = "DE" if claim.country_code == "DE" else "GB" if claim.country_code == "GB" else "EU"
        observed = "DD/MM or DD.MM date convention"
        if claim.country_code in {"DE", "PL", "FR"}:
            inferred = claim.country_code
    else:
        return []

    direction = _direction_for_country(inferred if inferred != "EU" else claim.country_code, claim)
    if inferred == "EU" and claim.country_code in {"DE", "PL", "FR", "GB"}:
        direction = AgreementDirection.SUPPORTS
    return [
        Signal(
            name="date_format",
            strength=cfg.strength,
            observed=observed,
            inferred_country=inferred,
            direction=direction,
            weight=cfg.weight,
            rationale="Date formatting convention implies regional locale",
        )
    ]


def _extract_spelling(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["spelling_locale"]
    text = parsed.text.lower()
    us_markers = ["organize", "color", "center", "analyze"]
    gb_markers = ["organise", "colour", "centre", "analyse"]
    us_hits = sum(1 for w in us_markers if w in text)
    gb_hits = sum(1 for w in gb_markers if w in text)
    if us_hits == gb_hits == 0:
        return []
    inferred = "US" if us_hits >= gb_hits else "GB"
    direction = _direction_for_country(inferred, claim)
    return [
        Signal(
            name="spelling_locale",
            strength=cfg.strength,
            observed=f"Spelling hints {inferred}",
            inferred_country=inferred,
            direction=direction,
            weight=cfg.weight,
            rationale="Spelling variants suggest document locale",
        )
    ]


def _extract_education_currency_email(
    parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig
) -> list[Signal]:
    signals: list[Signal] = []
    body = parsed.body_text.lower()

    edu_cfg = weights.signals["education_location"]
    edu_block = re.search(r"education[^\n]*\n(.*)", body, re.IGNORECASE | re.DOTALL)
    edu_text = edu_block.group(1)[:400] if edu_block else ""
    for line in edu_text.splitlines()[:6]:
        resolution = resolve_location(line)
        if resolution.is_unambiguous and resolution.primary:
            country = resolution.primary.country_code
            signals.append(
                Signal(
                    name="education_location",
                    strength=edu_cfg.strength,
                    observed=line.strip(),
                    inferred_country=country,
                    direction=_direction_for_country(country, claim),
                    weight=edu_cfg.weight,
                    rationale="Education section references this location",
                )
            )
            break

    cur_cfg = weights.signals["currency"]
    currency_map = {"$": "US", "€": "DE", "£": "GB", "zł": "PL"}
    for symbol, country in currency_map.items():
        if symbol in parsed.text:
            signals.append(
                Signal(
                    name="currency",
                    strength=cur_cfg.strength,
                    observed=f"Currency symbol {symbol}",
                    inferred_country=country,
                    direction=_direction_for_country(country, claim),
                    weight=cur_cfg.weight,
                    rationale="Currency symbol suggests regional context",
                )
            )
            break

    tld_cfg = weights.signals["email_tld"]
    email_match = re.search(r"[\w.+-]+@([\w.-]+)", parsed.contact_text)
    if email_match:
        domain = email_match.group(1).lower()
        tld = domain.split(".")[-1]
        country = TLD_TO_COUNTRY.get(tld) or TLD_TO_COUNTRY.get(".".join(domain.split(".")[-2:]))
        if country:
            signals.append(
                Signal(
                    name="email_tld",
                    strength=tld_cfg.strength,
                    observed=f"Email domain .{tld}",
                    inferred_country=country,
                    direction=_direction_for_country(country, claim),
                    weight=tld_cfg.weight,
                    rationale="Email TLD maps to country",
                )
            )
    return signals


def _extract_right_to_work(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["right_to_work"]
    patterns = [
        r"right to work",
        r"work authorization",
        r"work authorisation",
        r"visa status",
        r"requires sponsorship",
        r"eligible to work",
    ]
    for pattern in patterns:
        match = re.search(pattern, parsed.text, re.IGNORECASE)
        if match:
            return [
                Signal(
                    name="right_to_work",
                    strength=cfg.strength,
                    observed=match.group(0),
                    inferred_country=None,
                    direction=AgreementDirection.INFORMATIONAL,
                    weight=cfg.weight,
                    rationale="Right-to-work or visa statement surfaced for human review",
                )
            ]
    return []


def _extract_national_id(parsed: ParsedCV, claim: ClaimedLocation, weights: WeightsConfig) -> list[Signal]:
    cfg = weights.signals["national_id"]
    patterns = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "US_SSN"),
        (r"\b\d{11}\b", "GENERIC_NATIONAL_ID"),
        (r"\b[A-Z]{2}\d{6}[A-Z0-9]?\b", "UK_NINO"),
    ]
    for pattern, id_type in patterns:
        if re.search(pattern, parsed.text):
            return [
                Signal(
                    name="national_id",
                    strength=cfg.strength,
                    observed=f"present:{id_type}",
                    inferred_country=None,
                    direction=AgreementDirection.INFORMATIONAL,
                    weight=cfg.weight,
                    rationale="National ID pattern detected; raw value not retained",
                    metadata={"present": True, "type": id_type},
                )
            ]
    return []


_EXTRACTORS: list[Extractor] = [
    _extract_phone,
    _extract_address,
    _extract_employer,
    _extract_dates,
    _extract_spelling,
    _extract_education_currency_email,
    _extract_right_to_work,
    _extract_national_id,
]
