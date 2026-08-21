from cv_validator.domain import CandidateKind, LocationRelation, ObservationKind
from cv_validator.pipeline import analyze_cv_text


_REMOVED_PHYSICAL_LOCATION_FINDINGS = {
    "spelling_locale",
    "currency",
    "date_locale",
    "email_tld",
    "employer_location",
    "education_location",
    "client_location",
    "project_location",
    "office_location",
}


def test_weak_proxies_cannot_change_score_band_or_weighted_counts(
    location_resolver,
) -> None:
    base = (
        "Alex Example\nCurrent location: Berlin, Germany\n"
        "Phone: +49 30 123456\n\nExperience\nEngineer"
    )
    with_weak_proxies = (
        "Alex Example\nCurrent location: Berlin, Germany\n"
        "Phone: +49 30 123456\nalex@example.co.uk\n10115\n"
        "Right to work in Germany\n\nExperience\n"
        "Employer location: Berlin\nClient location: London\n"
        "Project location: Oslo\nOffice location: Zurich\n"
        "Education location: Paris\nColour optimisation centre\n"
        "01/02/2020\nBudget: £1000"
    )

    plain = analyze_cv_text(base, location_resolver=location_resolver)
    enriched = analyze_cv_text(
        with_weak_proxies,
        location_resolver=location_resolver,
    )

    assert (enriched.score, enriched.band) == (plain.score, plain.band)
    assert (
        enriched.signal_count,
        enriched.supporting_count,
        enriched.conflicting_count,
    ) == (
        plain.signal_count,
        plain.supporting_count,
        plain.conflicting_count,
    )
    assert not _REMOVED_PHYSICAL_LOCATION_FINDINGS & {
        finding.signal for finding in enriched.findings
    }


def test_dates_remain_candidates_and_related_locations_remain_nested_observations(
    location_resolver,
) -> None:
    report = analyze_cv_text(
        "Alex Example\nCurrent location: Berlin, Germany\n\nExperience\n"
        "Employer location: Berlin\nEducation location: Berlin\n01/02/2020",
        location_resolver=location_resolver,
    )
    assert report.deterministic is not None
    assert any(
        candidate.kind is CandidateKind.DATE
        for candidate in report.deterministic.candidates
    )
    related = {
        observation.relation
        for observation in report.deterministic.observations
        if observation.kind is ObservationKind.LOCATION
    }
    assert {LocationRelation.EMPLOYER, LocationRelation.EDUCATION} <= related
    assert not _REMOVED_PHYSICAL_LOCATION_FINDINGS & {
        finding.signal for finding in report.findings
    }


def test_informational_findings_do_not_increment_legacy_counts(
    location_resolver,
) -> None:
    report = analyze_cv_text(
        "Alex Example\nCurrent location: Berlin, Germany\nPostal: 10115\n"
        "Eligible to work in Germany\n\nExperience",
        location_resolver=location_resolver,
    )

    assert {finding.signal for finding in report.findings} >= {
        "postal_compatibility",
        "right_to_work",
    }
    assert report.signal_count == 0
    assert report.supporting_count == 0
    assert report.conflicting_count == 0
