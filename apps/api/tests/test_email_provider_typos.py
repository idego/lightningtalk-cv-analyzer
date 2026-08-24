import pytest

from cv_validator.config import load_weights
from cv_validator.domain import (
    AgreementDirection,
    ObservationKind,
    ObservationStatus,
)
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.extraction.email_providers import (
    COMMON_EMAIL_PROVIDER_CATALOG,
    COMMON_EMAIL_PROVIDER_CATALOG_VERSION,
)
from cv_validator.ingestion import RawDocument, SourcePage
from cv_validator.ingestion.redaction import redact_national_ids
from cv_validator.scoring.engine import score_deterministic


def _analyze(address: str):
    document = redact_national_ids(
        RawDocument(
            pages=(
                SourcePage(
                    "page-0001",
                    1,
                    f"Candidate Example\nEmail: {address}\nEngineer profile skills",
                ),
            ),
            source_format="text",
        )
    )
    return analyze_deterministically(document, "1.0.0")


def test_gmail_cm_is_a_code_owned_zero_weight_confirmation_observation() -> None:
    deterministic = _analyze("candidate@gmail.cm")
    observation = next(
        value
        for value in deterministic.observations
        if value.kind is ObservationKind.POSSIBLE_EMAIL_DOMAIN_TYPO
    )
    report = score_deterministic(deterministic, load_weights())
    exact_report = score_deterministic(
        _analyze("candidate@gmail.com"),
        load_weights(),
    )
    finding = next(
        value
        for value in report.findings
        if value.signal == "possible_email_domain_typo"
    )

    assert observation.status is ObservationStatus.INFORMATIONAL
    assert observation.values == ("gmail.cm", "gmail.com")
    assert observation.provenance.evidence[0].excerpt == "candidate@gmail.cm"
    assert observation.provenance.reference_data is not None
    assert observation.provenance.reference_data.version == (
        COMMON_EMAIL_PROVIDER_CATALOG_VERSION
    )
    assert observation.provenance.reference_data.source_url.startswith("https://support.google.com/")
    assert "confirm" in observation.reason.casefold()
    assert all(
        term not in observation.reason.casefold()
        for term in ("is fake", "is invalid", "does not exist")
    )
    assert finding.direction is AgreementDirection.INFORMATIONAL
    assert finding.weight == 0
    assert finding.score_impact == "none"
    assert (report.score, report.band, report.signal_count) == (
        exact_report.score,
        exact_report.band,
        exact_report.signal_count,
    )


@pytest.mark.parametrize(
    "address",
    (
        "candidate@gmail.com",
        "candidate@outlook.com",
        "candidate@proton.me",
        "candidate@icloud.com",
        "candidate@wp.pl",
        "candidate@o2.pl",
        "candidate@onet.pl",
        "candidate@interia.pl",
        "candidate@company.example",
    ),
)
def test_exact_catalog_and_custom_domains_do_not_emit_typo_observations(
    address,
) -> None:
    result = _analyze(address)

    assert ObservationKind.POSSIBLE_EMAIL_DOMAIN_TYPO not in {
        observation.kind for observation in result.observations
    }


def test_catalog_covers_required_families_with_official_sources() -> None:
    families = {entry.family for entry in COMMON_EMAIL_PROVIDER_CATALOG}
    assert {
        "google",
        "microsoft",
        "yahoo",
        "proton",
        "apple",
        "zoho",
        "onet",
        "wp-o2",
        "interia",
    } <= families
    assert all(entry.source_url.startswith("https://") for entry in COMMON_EMAIL_PROVIDER_CATALOG)
