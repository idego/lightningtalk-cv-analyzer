from cv_validator.analysis.document_analysis import _enrich_mechanical
from cv_validator.domain import ComponentVersion
from cv_validator.location import (
    InMemoryLocationResolver,
    InMemoryPostalCodeResolver,
    LocationMatch,
    MatchKind,
    PostalCodeRecord,
    ResolutionLevel,
)


VERSION = ComponentVersion("synthetic", "1")


def location(record_id: str, name: str, code: str, level: ResolutionLevel):
    return LocationMatch(
        record_id=record_id,
        level=level,
        canonical_name=name,
        matched_name=name,
        match_kind=MatchKind.CANONICAL,
        country_code=code,
        country_name={"PL": "Poland", "DE": "Germany", "FR": "France", "US": "United States"}[code],
    )


def resolver():
    return InMemoryLocationResolver(
        records=(
            location("city:warsaw", "Warsaw", "PL", ResolutionLevel.LOCALITY),
            location("city:berlin", "Berlin", "DE", ResolutionLevel.LOCALITY),
            location("city:paris-us", "Paris", "US", ResolutionLevel.LOCALITY),
            location("city:paris-fr", "Paris", "FR", ResolutionLevel.LOCALITY),
            location("country:poland", "Poland", "PL", ResolutionLevel.COUNTRY),
            location("country:germany", "Germany", "DE", ResolutionLevel.COUNTRY),
            location("country:usa", "United States", "US", ResolutionLevel.COUNTRY),
        ),
        reference_data_version=VERSION,
    )


def evidence(value: str, source_id: str = "block-address", start: int = 0):
    return [{
        "source_id": source_id,
        "excerpt": value,
        "start_offset": start,
        "end_offset": start + len(value),
    }]


def mechanical(postal_source: str = "block-address", postal_start: int = 20):
    return {
        "phones": [{
            "value": "+1 202 555 0100",
            "country_code": "US",
            "evidence": evidence("+1 202 555 0100", "block-phone"),
        }],
        "postal_candidates": [{
            "value": "00-001",
            "possible_country_codes": ["PL"],
            "ownership_status": "candidate",
            "evidence": evidence("00-001", postal_source, postal_start),
        }],
        "accepted_postal_addresses": [],
        "location_resolution": [],
        "eu_status": None,
        "comparisons": [],
    }


def profile(value: str):
    return {
        "declared_location": {
            "value": value,
            "status": "supported",
            "evidence": evidence(value),
        }
    }


def test_declared_city_country_and_postal_record_are_validated_together():
    postal = InMemoryPostalCodeResolver(
        (PostalCodeRecord("PL", "00-001", "Warsaw"),),
        reference_data_version=VERSION,
    )

    result = _enrich_mechanical(
        mechanical(), profile("Warsaw, Poland"), resolver(), postal
    )

    location_result = result["location_resolution"][0]
    assert location_result["status"] == "resolved"
    assert location_result["city_country_relationship"] == "same"
    accepted = result["accepted_postal_addresses"][0]
    assert accepted["city"] == "Warsaw"
    assert accepted["country_code"] == "PL"
    assert accepted["validation"]["status"] == "resolved"
    assert result["eu_status"]["primary_source"] == "declared_location"
    assert [item["kind"] for item in result["eu_status"]["sources"]] == [
        "declared_location",
        "phone_prefix",
    ]


def test_city_country_mismatch_and_ambiguous_and_unresolved_are_explicit():
    mismatch = _enrich_mechanical(
        mechanical(), profile("Berlin, Poland"), resolver()
    )["location_resolution"][0]
    ambiguous = _enrich_mechanical(
        mechanical(), profile("Paris, United States"), resolver()
    )["location_resolution"][0]
    unresolved = _enrich_mechanical(
        mechanical(), profile("Atlantis, Poland"), resolver()
    )["location_resolution"][0]

    assert mismatch["status"] == "resolved"
    assert mismatch["city_country_relationship"] == "different"
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["city_country_relationship"] == "ambiguous"
    assert unresolved["status"] == "unresolved"
    assert unresolved["city_country_relationship"] == "unresolved"


def test_postal_validation_is_unavailable_without_index_and_rejects_loose_number():
    unavailable = _enrich_mechanical(
        mechanical(), profile("Warsaw, Poland"), resolver()
    )
    loose = _enrich_mechanical(
        mechanical(postal_start=200), profile("Warsaw, Poland"), resolver()
    )

    assert unavailable["accepted_postal_addresses"][0]["validation"] == {
        "status": "unavailable",
        "reason": "postal_reference_data_unavailable",
    }
    assert loose["accepted_postal_addresses"] == []


def test_configured_postal_index_reports_city_mismatch_without_format_guessing():
    postal = InMemoryPostalCodeResolver(
        (PostalCodeRecord("PL", "00-001", "Krakow"),),
        reference_data_version=VERSION,
    )

    result = _enrich_mechanical(
        mechanical(), profile("Warsaw, Poland"), resolver(), postal
    )

    validation = result["accepted_postal_addresses"][0]["validation"]
    assert validation["status"] == "mismatch"
    assert validation["matched_places"] == ["Krakow"]
