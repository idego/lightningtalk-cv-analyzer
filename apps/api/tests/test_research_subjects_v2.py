from conftest import supported, valid_report
from cv_validator.research.company import build_company_research_request
from cv_validator.research.education import build_education_research_request
from cv_validator.research.linkedin import build_discovery_request


def test_research_uses_only_accepted_supported_records() -> None:
    report = valid_report()
    report["base_analysis"]["employment"].extend([
        {
            "id": "ambiguous-employer",
            "status": "ambiguous",
            "relation_status": "ambiguous",
            "added_by_reviewer": False,
            "organization": supported("MongoDB"),
            "role": None,
            "start_date": None,
            "end_date": None,
            "location": None,
            "relationship_type": None,
        },
        {
            "id": "self-employment",
            "status": "accepted",
            "relation_status": "supported",
            "added_by_reviewer": False,
            "organization": supported("Freelance"),
            "role": supported("Consultant"),
            "start_date": None,
            "end_date": None,
            "location": None,
            "relationship_type": supported("self-employed"),
        },
    ])

    company = build_company_research_request(report)
    education = build_education_research_request(report)
    linkedin = build_discovery_request(report)

    assert company.input_facts == ({"organization": "Example Systems"},)
    assert education.input_facts[0]["institution"] == "Example University"
    assert linkedin.candidate["name"] == "Jane Example"
    assert linkedin.candidate["search_hints"][0] == {
        "organization": "Example Systems",
        "role": "Software Engineer",
    }


def test_education_research_excludes_certificate_only_records() -> None:
    report = valid_report()
    report["base_analysis"]["education"].append({
        "id": "certificate-only",
        "status": "accepted",
        "relation_status": "supported",
        "added_by_reviewer": False,
        "institution": None,
        "program": None,
        "degree": None,
        "certificate": supported("AWS Cloud Practitioner"),
        "start_date": None,
        "end_date": None,
        "location": None,
    })

    education = build_education_research_request(report)

    assert education.input_facts == (
        {
            "institution": "Example University",
            "program": "Computer Science",
        },
    )


def test_certificate_is_not_sent_even_when_an_institution_is_present() -> None:
    report = valid_report()
    report["base_analysis"]["education"][0]["certificate"] = supported("Example Certificate")
    facts = build_education_research_request(report).input_facts
    assert all("certificate" not in fact for fact in facts)
    assert facts[0]["institution"] == "Example University"
