from __future__ import annotations

from io import BytesIO
from typing import Literal

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileLink(_StrictModel):
    label: str
    url: str


class PersonalLinks(_StrictModel):
    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[ProfileLink] = Field(default_factory=list)


class PersonalInformation(_StrictModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: PersonalLinks = Field(default_factory=PersonalLinks)


class ExperienceEntry(_StrictModel):
    id: str
    company: str | None = None
    company_category: str | None = None
    role: str | None = None
    project: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    current: bool = False
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)


class EducationEntry(_StrictModel):
    id: str
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    description: str | None = None


class LanguageEntry(_StrictModel):
    id: str
    language: str
    level: str | None = None


class CertificationEntry(_StrictModel):
    id: str
    name: str
    issuer: str | None = None
    date: str | None = None
    url: str | None = None


class AdditionalSection(_StrictModel):
    id: str
    title: str
    items: list[str] = Field(default_factory=list)


class CandidateProfile(_StrictModel):
    schema_version: Literal["candidate-profile-v1"] = "candidate-profile-v1"
    personal: PersonalInformation = Field(default_factory=PersonalInformation)
    headline: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    languages: list[LanguageEntry] = Field(default_factory=list)
    certifications: list[CertificationEntry] = Field(default_factory=list)
    additional_sections: list[AdditionalSection] = Field(default_factory=list)


class AnonymizationPolicy(_StrictModel):
    hide_first_name: bool = False
    hide_last_name: bool = False
    hide_email: bool = False
    hide_phone: bool = False
    hide_location: bool = False
    hide_linkedin: bool = False
    hide_github: bool = False
    hide_portfolio: bool = False
    employer_mode: Literal["show", "hide", "genericize"] = "show"
    institution_mode: Literal["show", "hide"] = "show"


class ProfileExportRequest(_StrictModel):
    profile: CandidateProfile
    anonymization: AnonymizationPolicy = Field(default_factory=AnonymizationPolicy)
    template_id: Literal["idego-default"] = "idego-default"


IDEGO_NAVY = RGBColor(0x08, 0x19, 0x32)
IDEGO_CYAN = RGBColor(0x3C, 0xC2, 0xD9)
MUTED = RGBColor(0x5C, 0x67, 0x73)


def apply_profile_anonymization(
    profile: CandidateProfile,
    policy: AnonymizationPolicy,
) -> CandidateProfile:
    result = profile.model_copy(deep=True)
    if policy.hide_first_name:
        result.personal.first_name = None
    if policy.hide_last_name:
        result.personal.last_name = None
    if policy.hide_email:
        result.personal.email = None
    if policy.hide_phone:
        result.personal.phone = None
    if policy.hide_location:
        result.personal.location = None
    if policy.hide_linkedin:
        result.personal.links.linkedin = None
    if policy.hide_github:
        result.personal.links.github = None
    if policy.hide_portfolio:
        result.personal.links.portfolio = None
    if policy.employer_mode != "show":
        for item in result.experience:
            item.company = (
                None
                if policy.employer_mode == "hide"
                else item.company_category or "Company"
            )
    if policy.institution_mode == "hide":
        for item in result.education:
            item.institution = None
    return result


def render_candidate_profile_docx(
    profile: CandidateProfile,
    policy: AnonymizationPolicy,
) -> bytes:
    presentation = apply_profile_anonymization(profile, policy)
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10.5)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        styles[style_name].font.name = "Aptos Display"
        styles[style_name].font.color.rgb = IDEGO_NAVY
    styles["Heading 1"].font.size = Pt(14)
    styles["Heading 2"].font.size = Pt(11.5)

    header = section.header.paragraphs[0]
    header.text = "IDEGO"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.runs[0].font.bold = True
    header.runs[0].font.size = Pt(13)
    header.runs[0].font.color.rgb = IDEGO_CYAN

    name = " ".join(
        value
        for value in (
            presentation.personal.first_name,
            presentation.personal.last_name,
        )
        if value
    )
    title = document.add_paragraph(style="Title")
    title.paragraph_format.space_after = Pt(3)
    title_run = title.add_run(name or "Candidate Profile")
    title_run.font.color.rgb = IDEGO_NAVY
    if presentation.headline:
        headline = document.add_paragraph()
        headline.paragraph_format.space_after = Pt(5)
        run = headline.add_run(presentation.headline)
        run.bold = True
        run.font.color.rgb = MUTED

    contact_values = [
        presentation.personal.email,
        presentation.personal.phone,
        presentation.personal.location,
        presentation.personal.links.linkedin,
        presentation.personal.links.github,
        presentation.personal.links.portfolio,
        *(
            f"{link.label}: {link.url}" if link.label else link.url
            for link in presentation.personal.links.other
        ),
    ]
    if any(contact_values):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(8)
        run = paragraph.add_run(" • ".join(value for value in contact_values if value))
        run.font.size = Pt(9)
        run.font.color.rgb = MUTED

    if presentation.summary:
        _add_profile_heading(document, "Summary")
        document.add_paragraph(presentation.summary)

    _add_profile_string_list(document, "Skills", presentation.skills)
    _add_profile_string_list(document, "Technologies", presentation.technologies)

    if presentation.experience:
        _add_profile_heading(document, "Experience")
        for entry in presentation.experience:
            heading_bits = [value for value in (entry.role, entry.company) if value]
            item_heading = document.add_paragraph(style="Heading 2")
            item_heading.paragraph_format.space_after = Pt(0)
            item_heading.add_run(" — ".join(heading_bits) or "Experience")
            _add_profile_meta_line(
                document,
                [
                    value
                    for value in (
                        _profile_date_range(entry.start_date, entry.end_date, entry.current),
                        entry.location,
                        entry.project,
                    )
                    if value
                ],
            )
            for text in entry.responsibilities:
                document.add_paragraph(text, style="List Bullet")
            for text in entry.achievements:
                paragraph = document.add_paragraph(style="List Bullet")
                paragraph.add_run(text).bold = True
            if entry.technologies:
                paragraph = document.add_paragraph()
                paragraph.add_run("Technologies: ").bold = True
                paragraph.add_run(", ".join(entry.technologies))

    if presentation.education:
        _add_profile_heading(document, "Education")
        for entry in presentation.education:
            title_bits = [value for value in (entry.degree, entry.field) if value]
            if entry.institution:
                title_bits.append(entry.institution)
            item_heading = document.add_paragraph(style="Heading 2")
            item_heading.paragraph_format.space_after = Pt(0)
            item_heading.add_run(" — ".join(title_bits) or "Education")
            _add_profile_meta_line(
                document,
                [
                    value
                    for value in (
                        _profile_date_range(entry.start_date, entry.end_date, False),
                        entry.location,
                    )
                    if value
                ],
            )
            if entry.description:
                document.add_paragraph(entry.description)

    if presentation.languages:
        _add_profile_heading(document, "Languages")
        for language in presentation.languages:
            document.add_paragraph(
                " — ".join(
                    value for value in (language.language, language.level) if value
                ),
                style="List Bullet",
            )

    if presentation.certifications:
        _add_profile_heading(document, "Certifications")
        for certification in presentation.certifications:
            values = [certification.name]
            if certification.issuer:
                values.append(certification.issuer)
            if certification.date:
                values.append(certification.date)
            if certification.url:
                values.append(certification.url)
            document.add_paragraph(" — ".join(values), style="List Bullet")

    for extra_section in presentation.additional_sections:
        if not extra_section.items:
            continue
        _add_profile_heading(document, extra_section.title)
        for item in extra_section.items:
            document.add_paragraph(item, style="List Bullet")

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_run = footer.add_run("Candidate Profile • IDEGO")
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = MUTED

    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _add_profile_heading(document: Document, text: str) -> None:
    paragraph = document.add_paragraph(style="Heading 1")
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(3)
    paragraph.add_run(text)


def _add_profile_string_list(document: Document, title: str, values: list[str]) -> None:
    if values:
        _add_profile_heading(document, title)
        document.add_paragraph(", ".join(values))


def _add_profile_meta_line(document: Document, values: list[str]) -> None:
    if not values:
        return
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(2)
    run = paragraph.add_run(" • ".join(values))
    run.italic = True
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED


def _profile_date_range(
    start: str | None,
    end: str | None,
    current: bool,
) -> str | None:
    if current:
        end = "Present"
    if start and end:
        return f"{start} – {end}"
    return start or end
