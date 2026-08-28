import io

from docx import Document
from fastapi.testclient import TestClient

from cv_validator.ai.config import AISettings
from cv_validator.api.app import create_app
from cv_validator.ai.domain import ProfileExtractionResponse
from cv_validator.profile_builder import (
    AnonymizationPolicy,
    CandidateProfile,
    ExperienceEntry,
    PersonalInformation,
    apply_profile_anonymization,
)


def _extracted_payload() -> dict:
    return {
        "personal": {
            "first_name": "Jane",
            "last_name": "Example",
            "email": "jane@example.com",
            "phone": "+48 500 600 700",
            "location": "Gdansk, Poland",
            "links": {
                "linkedin": "https://linkedin.com/in/jane-example",
                "github": None,
                "portfolio": None,
                "other": [],
            },
        },
        "headline": "Backend Engineer",
        "summary": "Backend engineer focused on Python services.",
        "skills": ["Python", "FastAPI", "Python"],
        "technologies": ["PostgreSQL"],
        "experience": [
            {
                "company": "Acme",
                "company_category": None,
                "role": "Backend Engineer",
                "project": None,
                "location": "Gdansk",
                "start_date": "2024-01",
                "end_date": None,
                "current": True,
                "responsibilities": ["Built APIs"],
                "achievements": [],
                "technologies": ["Python", "FastAPI"],
            }
        ],
        "education": [
            {
                "institution": "Example University",
                "degree": "BSc",
                "field": "Computer Science",
                "start_date": "2021",
                "end_date": "2024",
                "location": "Gdansk",
                "description": None,
            }
        ],
        "languages": [{"language": "English", "level": "C1"}],
        "certifications": [],
        "additional_sections": [],
    }


class _Extractor:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or _extracted_payload()
        self.requests = []

    def extract(self, request):
        self.requests.append(request)
        return ProfileExtractionResponse(
            payload=self.payload,
            response_model="test-model",
            usage={},
        )


def _client(tmp_path, location_resolver, extractor: _Extractor) -> TestClient:
    return TestClient(
        create_app(
            db_path=tmp_path / "profile-builder.db",
            location_resolver=location_resolver,
            ai_settings=AISettings(enabled=True, api_key="test-key"),
            profile_extractor=extractor,
        )
    )


def _docx_bytes(text: str) -> bytes:
    document = Document()
    for line in text.splitlines():
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _docx_text(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    chunks = [paragraph.text for paragraph in document.paragraphs]
    for section in document.sections:
        chunks.extend(paragraph.text for paragraph in section.header.paragraphs)
        chunks.extend(paragraph.text for paragraph in section.footer.paragraphs)
    return "\n".join(chunks)


def test_profile_builder_extracts_redacted_cv_and_materializes_stable_ids(
    tmp_path,
    location_resolver,
) -> None:
    extractor = _Extractor()
    client = _client(tmp_path, location_resolver, extractor)
    content = _docx_bytes(
        "Jane Example\n"
        "jane@example.com\n"
        "SSN: 123-45-6789\n"
        "Backend Engineer at Acme"
    )

    response = client.post(
        "/profile-builder/extract",
        files={
            "file": (
                "candidate.docx",
                content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "candidate.docx"
    assert body["profile"]["schema_version"] == "candidate-profile-v1"
    assert body["profile"]["experience"][0]["id"] == "experience-001"
    assert body["profile"]["education"][0]["id"] == "education-001"
    assert body["profile"]["skills"] == ["Python", "FastAPI"]
    request_text = extractor.requests[0].to_openai_payload()["input"][0]["content"][0]["text"]
    assert "123-45-6789" not in request_text
    assert "█" in request_text


def test_profile_builder_rejects_unsupported_upload(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    response = client.post(
        "/profile-builder/extract",
        files={"file": ("candidate.txt", b"candidate", "text/plain")},
    )
    assert response.status_code == 422


def test_profile_builder_respects_request_level_ai_opt_out(
    tmp_path,
    location_resolver,
) -> None:
    extractor = _Extractor()
    client = _client(tmp_path, location_resolver, extractor)
    response = client.post(
        "/profile-builder/extract",
        headers={"X-AI-Enabled": "false"},
        files={
            "file": (
                "candidate.docx",
                _docx_bytes("Jane Example\nBackend Engineer"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "profile_builder_ai_disabled_for_request"}
    assert extractor.requests == []


def test_profile_builder_reports_ai_disabled(tmp_path, location_resolver) -> None:
    client = TestClient(
        create_app(
            db_path=tmp_path / "profile-builder-disabled.db",
            location_resolver=location_resolver,
        )
    )
    response = client.post(
        "/profile-builder/extract",
        files={
            "file": (
                "candidate.docx",
                _docx_bytes("Jane Example\nBackend Engineer"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 503
    assert response.json() == {"detail": "profile_builder_ai_disabled"}


def test_anonymization_is_derived_and_does_not_mutate_canonical_profile() -> None:
    profile = CandidateProfile(
        personal=PersonalInformation(
            first_name="Jane",
            last_name="Example",
            email="jane@example.com",
        ),
        experience=[
            ExperienceEntry(
                id="experience-001",
                company="Acme",
                role="Engineer",
            )
        ],
    )
    presentation = apply_profile_anonymization(
        profile,
        AnonymizationPolicy(
            hide_email=True,
            employer_mode="hide",
        ),
    )

    assert presentation.personal.email is None
    assert presentation.experience[0].company is None
    assert profile.personal.email == "jane@example.com"
    assert profile.experience[0].company == "Acme"


def test_docx_export_uses_exact_current_snapshot_and_anonymization(
    tmp_path,
    location_resolver,
) -> None:
    extractor = _Extractor()
    client = _client(tmp_path, location_resolver, extractor)
    extract_response = client.post(
        "/profile-builder/extract",
        files={
            "file": (
                "candidate.docx",
                _docx_bytes("Jane Example\nBackend Engineer at Acme"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    profile = extract_response.json()["profile"]
    profile["personal"]["first_name"] = "Janet"
    profile["summary"] = "Updated summary from the editor."
    profile["experience"][0]["company"] = "Example Corp"
    profile["experience"][0]["role"] = "Senior Backend Engineer"
    profile["experience"][0]["responsibilities"] = ["Owns the API platform"]
    profile["personal"]["links"]["other"] = [
        {"label": "Website", "url": "https://example.test"}
    ]
    profile["certifications"] = [
        {
            "id": "certification-001",
            "name": "Example Cert",
            "issuer": "Example Org",
            "date": "2026",
            "url": "https://cert.example.test",
        }
    ]

    response = client.post(
        "/profile-builder/export/docx",
        json={
            "profile": profile,
            "anonymization": {
                "hide_first_name": False,
                "hide_last_name": False,
                "hide_email": True,
                "hide_phone": False,
                "hide_location": False,
                "hide_linkedin": False,
                "hide_github": False,
                "hide_portfolio": False,
                "employer_mode": "show",
                "institution_mode": "show",
            },
            "template_id": "idego-default",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    text = _docx_text(response.content)
    assert "Janet Example" in text
    assert "Jane Example" not in text
    assert "Updated summary from the editor." in text
    assert "Backend engineer focused on Python services." not in text
    assert "Example Corp" in text
    assert "Acme" not in text
    assert "Senior Backend Engineer" in text
    assert "Owns the API platform" in text
    assert "Built APIs" not in text
    assert "jane@example.com" not in text
    assert "Website: https://example.test" in text
    assert "https://cert.example.test" in text
