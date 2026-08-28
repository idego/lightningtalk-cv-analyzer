import base64
import io
import zipfile

from docx import Document
from PIL import Image
from fastapi.testclient import TestClient

from cv_validator.ai.config import AISettings
from cv_validator.api.app import create_app
from cv_validator.ai.domain import ProfileExtractionResponse, ProfileSummaryResponse
from cv_validator.profile_builder import (
    AnonymizationPolicy,
    CandidateProfile,
    ExperienceEntry,
    PersonalInformation,
    ProfileTemplate,
    ProfileTemplateBranding,
    ProfileTemplateLogo,
    ProfileTemplateSection,
    default_profile_template,
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


class _Summarizer:
    def __init__(self, summary: str = "Generated recruiter summary.") -> None:
        self.summary = summary
        self.requests = []

    def summarize(self, request):
        self.requests.append(request)
        return ProfileSummaryResponse(
            summary=self.summary,
            response_model="gpt-5.6-luna",
            usage={},
        )


def _client(
    tmp_path,
    location_resolver,
    extractor: _Extractor,
    summarizer: _Summarizer | None = None,
) -> TestClient:
    return TestClient(
        create_app(
            db_path=tmp_path / "profile-builder.db",
            location_resolver=location_resolver,
            ai_settings=AISettings(enabled=True, api_key="test-key"),
            profile_extractor=extractor,
            profile_summarizer=summarizer or _Summarizer(),
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


def test_profile_builder_summary_uses_luna_without_reasoning_and_excludes_contact_and_old_summary(
    tmp_path,
    location_resolver,
) -> None:
    summarizer = _Summarizer("Python backend engineer aligned with the role.")
    client = _client(tmp_path, location_resolver, _Extractor(), summarizer)
    profile = _profile_snapshot()["profile"]

    response = client.post(
        "/profile-builder/summary",
        json={
            "profile": profile,
            "instruction": "Focus on backend Python work for this job: Senior Python Engineer.",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "summary": "Python backend engineer aligned with the role."
    }
    payload = summarizer.requests[0].to_openai_payload()
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["reasoning"] == {"effort": "none"}
    assert payload["tools"] == []
    assert payload["store"] is False
    assert payload["max_output_tokens"] <= 384
    input_text = payload["input"][0]["content"][0]["text"]
    assert "Senior Python Engineer" in input_text
    assert "jane@example.com" not in input_text
    assert "Backend engineer focused on Python services." not in input_text
    assert "Built APIs" in input_text


def test_profile_builder_summary_respects_request_ai_opt_out(
    tmp_path,
    location_resolver,
) -> None:
    summarizer = _Summarizer()
    client = _client(tmp_path, location_resolver, _Extractor(), summarizer)
    response = client.post(
        "/profile-builder/summary",
        headers={"X-AI-Enabled": "false"},
        json={"profile": _profile_snapshot()["profile"], "instruction": None},
    )
    assert response.status_code == 409
    assert summarizer.requests == []


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


PROFILE_TOKEN = "profile-owner-a"
OTHER_PROFILE_TOKEN = "profile-owner-b"


def _profile_snapshot(profile: dict | None = None, template: dict | None = None) -> dict:
    return {
        "source_filename": "candidate.docx",
        "profile": profile or {
            "schema_version": "candidate-profile-v1",
            **_extracted_payload(),
            "experience": [
                {"id": "experience-001", **_extracted_payload()["experience"][0]}
            ],
            "education": [
                {"id": "education-001", **_extracted_payload()["education"][0]}
            ],
            "languages": [
                {"id": "language-001", **_extracted_payload()["languages"][0]}
            ],
        },
        "anonymization": AnonymizationPolicy().model_dump(mode="json"),
        "template": template or default_profile_template().model_dump(mode="json"),
    }


def test_profile_builder_recent_profiles_are_owner_scoped_and_reopen_exact_snapshot(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    headers = {"X-Profile-Builder-Access-Token": PROFILE_TOKEN}
    snapshot = _profile_snapshot()

    created = client.post("/profile-builder/profiles", headers=headers, json=snapshot)
    assert created.status_code == 201
    profile_id = created.json()["profile_id"]

    listed = client.get("/profile-builder/profiles", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["profiles"] == [
        {
            "profile_id": profile_id,
            "source_filename": "candidate.docx",
            "candidate_name": "Jane Example",
            "template_id": "idego-default",
            "template_name": "IDEGO Default",
            "created_at": listed.json()["profiles"][0]["created_at"],
            "updated_at": listed.json()["profiles"][0]["updated_at"],
        }
    ]
    assert client.get(
        f"/profile-builder/profiles/{profile_id}",
        headers={"X-Profile-Builder-Access-Token": OTHER_PROFILE_TOKEN},
    ).status_code == 404

    snapshot["profile"]["summary"] = "Autosaved exact summary"
    snapshot["anonymization"]["hide_email"] = True
    updated_template = default_profile_template().model_copy(deep=True)
    updated_template.name = "Selected Snapshot"
    snapshot["template"] = updated_template.model_dump(mode="json")
    updated = client.put(
        f"/profile-builder/profiles/{profile_id}",
        headers=headers,
        json=snapshot,
    )
    assert updated.status_code == 200

    reopened = client.get(
        f"/profile-builder/profiles/{profile_id}", headers=headers
    )
    assert reopened.status_code == 200
    body = reopened.json()
    assert body["profile"]["summary"] == "Autosaved exact summary"
    assert body["anonymization"]["hide_email"] is True
    assert body["template"]["name"] == "Selected Snapshot"
    assert "source_file" not in body
    assert "file_bytes" not in body

    deleted = client.delete(
        f"/profile-builder/profiles/{profile_id}", headers=headers
    )
    assert deleted.status_code == 200
    assert client.get("/profile-builder/profiles", headers=headers).json()["profiles"] == []


def test_profile_builder_templates_have_builtin_fallback_and_owner_scoped_overrides(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    headers = {"X-Profile-Builder-Access-Token": PROFILE_TOKEN}

    initial = client.get("/profile-builder/templates", headers=headers)
    assert initial.status_code == 200
    templates = initial.json()["templates"]
    assert len(templates) == 1
    assert templates[0]["template"]["id"] == "idego-default"
    assert templates[0]["built_in"] is True
    assert templates[0]["customized"] is False

    custom = default_profile_template().model_copy(deep=True)
    custom.id = "client-compact"
    custom.name = "Client Compact"
    custom.description = "Compact client-facing profile"
    custom.branding = ProfileTemplateBranding(
        brand_name="CLIENT",
        accent_hex="#123456",
        show_brand=True,
    )
    saved = client.put(
        "/profile-builder/templates/client-compact",
        headers=headers,
        json=custom.model_dump(mode="json"),
    )
    assert saved.status_code == 200

    owned = client.get("/profile-builder/templates", headers=headers).json()["templates"]
    assert {item["template"]["id"] for item in owned} == {
        "idego-default",
        "client-compact",
    }
    other = client.get(
        "/profile-builder/templates",
        headers={"X-Profile-Builder-Access-Token": OTHER_PROFILE_TOKEN},
    ).json()["templates"]
    assert [item["template"]["id"] for item in other] == ["idego-default"]

    default_override = default_profile_template().model_copy(deep=True)
    default_override.name = "My IDEGO Default"
    assert client.put(
        "/profile-builder/templates/idego-default",
        headers=headers,
        json=default_override.model_dump(mode="json"),
    ).status_code == 200
    overridden = client.get(
        "/profile-builder/templates/idego-default", headers=headers
    ).json()
    assert overridden["template"]["name"] == "My IDEGO Default"
    assert overridden["customized"] is True

    reset = client.delete(
        "/profile-builder/templates/idego-default", headers=headers
    )
    assert reset.status_code == 200
    fallback = client.get(
        "/profile-builder/templates/idego-default", headers=headers
    ).json()
    assert fallback["template"]["name"] == "IDEGO Default"
    assert fallback["customized"] is False


def test_custom_template_snapshot_controls_docx_sections_order_titles_and_branding(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    profile = _profile_snapshot()["profile"]
    template = ProfileTemplate(
        id="custom-export",
        name="Custom Export",
        branding=ProfileTemplateBranding(
            brand_name="CLIENT BRAND",
            accent_hex="#9B2C2C",
            show_brand=True,
        ),
        sections=[
            ProfileTemplateSection(
                id="experience",
                kind="experience",
                title="Selected Work",
            ),
            ProfileTemplateSection(
                id="summary",
                kind="summary",
                title="About",
            ),
        ],
    )
    response = client.post(
        "/profile-builder/export/docx",
        json={
            "profile": profile,
            "anonymization": AnonymizationPolicy().model_dump(mode="json"),
            "template_id": template.id,
            "template": template.model_dump(mode="json"),
        },
    )
    assert response.status_code == 200
    text = _docx_text(response.content)
    assert "CLIENT BRAND" in text
    assert "Selected Work" in text
    assert "About" in text
    assert text.index("Selected Work") < text.index("About")
    assert "Skills" not in text
    assert "\nTechnologies\n" not in f"\n{text}\n"


def test_docx_export_rejects_mismatched_template_snapshot_id(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    template = default_profile_template().model_copy(deep=True)
    template.id = "actual-template"
    response = client.post(
        "/profile-builder/export/docx",
        json={
            "profile": _profile_snapshot()["profile"],
            "anonymization": AnonymizationPolicy().model_dump(mode="json"),
            "template_id": "different-template",
            "template": template.model_dump(mode="json"),
        },
    )
    assert response.status_code == 422


def test_additional_section_block_heading_affects_docx_output(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    profile = _profile_snapshot()["profile"]
    profile["additional_sections"] = [
        {
            "id": "additional-001",
            "title": "Community",
            "items": ["Mentors engineers"],
        }
    ]
    template = ProfileTemplate(
        id="additional-export",
        name="Additional Export",
        sections=[
            ProfileTemplateSection(
                id="additional",
                kind="additional_sections",
                title="Beyond Work",
                layout="bullets",
            )
        ],
    )
    response = client.post(
        "/profile-builder/export/docx",
        json={
            "profile": profile,
            "anonymization": AnonymizationPolicy().model_dump(mode="json"),
            "template_id": template.id,
            "template": template.model_dump(mode="json"),
        },
    )
    assert response.status_code == 200
    text = _docx_text(response.content)
    assert "Beyond Work" in text
    assert "Community" in text
    assert "Mentors engineers" in text


def test_docx_export_rejects_custom_template_id_without_snapshot(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    response = client.post(
        "/profile-builder/export/docx",
        json={
            "profile": _profile_snapshot()["profile"],
            "anonymization": AnonymizationPolicy().model_dump(mode="json"),
            "template_id": "missing-custom-snapshot",
        },
    )
    assert response.status_code == 422



def _transparent_logo_data_url() -> str:
    image = Image.new("RGBA", (240, 80), (0, 0, 0, 0))
    for x in range(30, 210):
        for y in range(20, 60):
            image.putpixel((x, y), (60, 194, 217, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def test_template_logo_is_rendered_as_floating_page_positioned_image(
    tmp_path,
    location_resolver,
) -> None:
    client = _client(tmp_path, location_resolver, _Extractor())
    template = default_profile_template().model_copy(deep=True)
    template.logo = ProfileTemplateLogo(
        data_url=_transparent_logo_data_url(),
        original_name="brand.svg",
        x_pct=63,
        y_pct=8,
        width_pct=22,
        aspect_ratio=3,
    )
    response = client.post(
        "/profile-builder/export/docx",
        json={
            "profile": _profile_snapshot()["profile"],
            "anonymization": AnonymizationPolicy().model_dump(mode="json"),
            "template_id": template.id,
            "template": template.model_dump(mode="json"),
        },
    )
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        header_xml = archive.read("word/header1.xml").decode("utf-8")
        media_names = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert "<wp:anchor" in header_xml
    assert 'relativeFrom="page"' in header_xml
    assert "<wp:wrapNone" in header_xml
    assert media_names
