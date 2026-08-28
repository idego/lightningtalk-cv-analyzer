from __future__ import annotations

import base64
from io import BytesIO
from typing import Literal

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


TemplateSectionKind = Literal[
    "summary",
    "skills",
    "technologies",
    "experience",
    "education",
    "languages",
    "certifications",
    "additional_sections",
]
TemplateSectionLayout = Literal["default", "inline", "bullets"]


class ProfileTemplateBranding(_StrictModel):
    brand_name: str = Field(default="IDEGO", min_length=1, max_length=80)
    accent_hex: str = Field(default="#3CC2D9", pattern=r"^#[0-9A-Fa-f]{6}$")
    show_brand: bool = True


class ProfileTemplateTypography(_StrictModel):
    font_family: Literal["Aptos", "Arial", "Calibri"] = "Aptos"
    body_size: float = Field(default=10.5, ge=8, le=14)
    heading_size: float = Field(default=14, ge=10, le=22)


class ProfileTemplateHeader(_StrictModel):
    show_name: bool = True
    show_headline: bool = True
    show_contact: bool = True


class ProfileTemplateLogo(_StrictModel):
    data_url: str = Field(
        min_length=32,
        max_length=6_000_000,
        pattern=r"^data:image/png;base64,[A-Za-z0-9+/=]+$",
    )
    original_name: str = Field(min_length=1, max_length=255)
    x_pct: float = Field(default=72, ge=0, le=100)
    y_pct: float = Field(default=4, ge=0, le=100)
    width_pct: float = Field(default=18, ge=2, le=60)
    aspect_ratio: float = Field(default=2, gt=0.05, le=20)

    @model_validator(mode="after")
    def validate_page_bounds(self) -> ProfileTemplateLogo:
        if self.x_pct + self.width_pct > 100.001:
            raise ValueError("template logo must fit inside page width")
        height_pct = self.width_pct * (210 / 297) / self.aspect_ratio
        if self.y_pct + height_pct > 100.001:
            raise ValueError("template logo must fit inside page height")
        return self


class ProfileTemplateSection(_StrictModel):
    id: str = Field(min_length=1, max_length=80)
    kind: TemplateSectionKind
    title: str = Field(min_length=1, max_length=80)
    visible: bool = True
    layout: TemplateSectionLayout = "default"


class ProfileTemplate(_StrictModel):
    schema_version: Literal["profile-template-v1"] = "profile-template-v1"
    id: str = Field(min_length=1, max_length=96, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=300)
    branding: ProfileTemplateBranding = Field(default_factory=ProfileTemplateBranding)
    typography: ProfileTemplateTypography = Field(default_factory=ProfileTemplateTypography)
    header: ProfileTemplateHeader = Field(default_factory=ProfileTemplateHeader)
    logo: ProfileTemplateLogo | None = None
    sections: list[ProfileTemplateSection] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def validate_unique_sections(self) -> ProfileTemplate:
        ids = [section.id for section in self.sections]
        kinds = [section.kind for section in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("template section IDs must be unique")
        if len(kinds) != len(set(kinds)):
            raise ValueError("template section kinds must be unique")
        return self


class ProfileBuilderSnapshot(_StrictModel):
    source_filename: str = Field(min_length=1, max_length=512)
    profile: CandidateProfile
    anonymization: AnonymizationPolicy = Field(default_factory=AnonymizationPolicy)
    template: ProfileTemplate


class ProfileSummaryGenerationRequest(_StrictModel):
    profile: CandidateProfile
    instruction: str | None = Field(default=None, max_length=12_000)


class ProfileExportRequest(_StrictModel):
    profile: CandidateProfile
    anonymization: AnonymizationPolicy = Field(default_factory=AnonymizationPolicy)
    template_id: str = "idego-default"
    template: ProfileTemplate | None = None

    @model_validator(mode="after")
    def validate_template_snapshot(self) -> ProfileExportRequest:
        if self.template is None and self.template_id != "idego-default":
            raise ValueError("custom template exports require an exact template snapshot")
        if self.template is not None and self.template.id != self.template_id:
            raise ValueError("template snapshot ID must match template_id")
        return self


IDEGO_NAVY = RGBColor(0x08, 0x19, 0x32)
MUTED = RGBColor(0x5C, 0x67, 0x73)


def default_profile_template() -> ProfileTemplate:
    return ProfileTemplate(
        id="idego-default",
        name="IDEGO Default",
        description="Default IDEGO candidate profile layout.",
        sections=[
            ProfileTemplateSection(id="summary", kind="summary", title="Summary"),
            ProfileTemplateSection(id="skills", kind="skills", title="Skills", layout="inline"),
            ProfileTemplateSection(
                id="technologies",
                kind="technologies",
                title="Technologies",
                layout="inline",
            ),
            ProfileTemplateSection(
                id="experience", kind="experience", title="Experience"
            ),
            ProfileTemplateSection(id="education", kind="education", title="Education"),
            ProfileTemplateSection(
                id="languages", kind="languages", title="Languages", layout="inline"
            ),
            ProfileTemplateSection(
                id="certifications",
                kind="certifications",
                title="Certifications",
                layout="bullets",
            ),
            ProfileTemplateSection(
                id="additional-sections",
                kind="additional_sections",
                title="Additional",
                layout="bullets",
            ),
        ],
    )


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
    template: ProfileTemplate | None = None,
) -> bytes:
    selected_template = template or default_profile_template()
    presentation = apply_profile_anonymization(profile, policy)
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)

    accent = _rgb_from_hex(selected_template.branding.accent_hex)
    font_family = selected_template.typography.font_family
    body_size = selected_template.typography.body_size
    heading_size = selected_template.typography.heading_size

    styles = document.styles
    styles["Normal"].font.name = font_family
    styles["Normal"].font.size = Pt(body_size)
    for style_name in ("Title", "Heading 1", "Heading 2"):
        styles[style_name].font.name = font_family
        styles[style_name].font.color.rgb = IDEGO_NAVY
    styles["Title"].font.size = Pt(min(heading_size + 10, 30))
    styles["Heading 1"].font.size = Pt(heading_size)
    styles["Heading 2"].font.size = Pt(min(body_size + 1.5, heading_size))

    header = section.header.paragraphs[0]
    if selected_template.branding.show_brand:
        header.text = selected_template.branding.brand_name
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        header.runs[0].font.bold = True
        header.runs[0].font.size = Pt(max(body_size + 2.5, 12))
        header.runs[0].font.color.rgb = accent
    if selected_template.logo is not None:
        _add_floating_template_logo(header, section, selected_template.logo)

    _render_profile_header(document, presentation, selected_template)
    for template_section in selected_template.sections:
        if template_section.visible:
            _render_profile_section(
                document,
                presentation,
                template_section,
                accent=accent,
            )

    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    footer_text = (
        f"Candidate Profile • {selected_template.branding.brand_name}"
        if selected_template.branding.show_brand
        else "Candidate Profile"
    )
    footer_run = footer.add_run(footer_text)
    footer_run.font.size = Pt(8)
    footer_run.font.color.rgb = MUTED

    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def _add_floating_template_logo(paragraph, section, logo: ProfileTemplateLogo) -> None:
    encoded = logo.data_url.split(",", 1)[1]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("invalid template logo data") from exc

    page_width = int(section.page_width)
    page_height = int(section.page_height)
    width = max(1, int(page_width * logo.width_pct / 100))
    height = max(1, int(width / logo.aspect_ratio))
    x = int(page_width * logo.x_pct / 100)
    y = int(page_height * logo.y_pct / 100)

    run = paragraph.add_run()
    run.add_picture(BytesIO(image_bytes), width=width, height=height)
    drawing = run._r.drawing_lst[-1]
    inline = drawing[0]
    inline.tag = qn("wp:anchor")
    for name, value in {
        "distT": "0",
        "distB": "0",
        "distL": "0",
        "distR": "0",
        "simplePos": "0",
        "relativeHeight": "251658240",
        "behindDoc": "0",
        "locked": "0",
        "layoutInCell": "1",
        "allowOverlap": "1",
    }.items():
        inline.set(name, value)

    simple_pos = OxmlElement("wp:simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    position_h = OxmlElement("wp:positionH")
    position_h.set("relativeFrom", "page")
    pos_x = OxmlElement("wp:posOffset")
    pos_x.text = str(x)
    position_h.append(pos_x)
    position_v = OxmlElement("wp:positionV")
    position_v.set("relativeFrom", "page")
    pos_y = OxmlElement("wp:posOffset")
    pos_y.text = str(y)
    position_v.append(pos_y)

    inline.insert(0, simple_pos)
    inline.insert(1, position_h)
    inline.insert(2, position_v)

    extent_index = next(
        (index for index, child in enumerate(inline) if child.tag == qn("wp:extent")),
        3,
    )
    effect_extent = OxmlElement("wp:effectExtent")
    for name in ("l", "t", "r", "b"):
        effect_extent.set(name, "0")
    wrap_none = OxmlElement("wp:wrapNone")
    inline.insert(extent_index + 1, effect_extent)
    inline.insert(extent_index + 2, wrap_none)


def _render_profile_header(
    document: Document,
    presentation: CandidateProfile,
    template: ProfileTemplate,
) -> None:
    if template.header.show_name:
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

    if template.header.show_headline and presentation.headline:
        headline = document.add_paragraph()
        headline.paragraph_format.space_after = Pt(5)
        run = headline.add_run(presentation.headline)
        run.bold = True
        run.font.color.rgb = MUTED

    if template.header.show_contact:
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
            run = paragraph.add_run(
                " • ".join(value for value in contact_values if value)
            )
            run.font.size = Pt(max(template.typography.body_size - 1.5, 8))
            run.font.color.rgb = MUTED


def _render_profile_section(
    document: Document,
    presentation: CandidateProfile,
    template_section: ProfileTemplateSection,
    *,
    accent: RGBColor,
) -> None:
    kind = template_section.kind
    if kind == "summary":
        if presentation.summary:
            _add_profile_heading(document, template_section.title, accent)
            document.add_paragraph(presentation.summary)
        return

    if kind == "skills":
        _render_string_values(
            document,
            template_section.title,
            presentation.skills,
            template_section.layout,
            accent,
        )
        return

    if kind == "technologies":
        _render_string_values(
            document,
            template_section.title,
            presentation.technologies,
            template_section.layout,
            accent,
        )
        return

    if kind == "experience":
        if not presentation.experience:
            return
        _add_profile_heading(document, template_section.title, accent)
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
                        _profile_date_range(
                            entry.start_date, entry.end_date, entry.current
                        ),
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
        return

    if kind == "education":
        if not presentation.education:
            return
        _add_profile_heading(document, template_section.title, accent)
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
        return

    if kind == "languages":
        values = [
            " — ".join(value for value in (item.language, item.level) if value)
            for item in presentation.languages
        ]
        _render_string_values(
            document,
            template_section.title,
            values,
            template_section.layout,
            accent,
        )
        return

    if kind == "certifications":
        values: list[str] = []
        for certification in presentation.certifications:
            parts = [certification.name]
            if certification.issuer:
                parts.append(certification.issuer)
            if certification.date:
                parts.append(certification.date)
            if certification.url:
                parts.append(certification.url)
            values.append(" — ".join(parts))
        _render_string_values(
            document,
            template_section.title,
            values,
            template_section.layout,
            accent,
        )
        return

    if kind == "additional_sections":
        non_empty = [
            extra_section
            for extra_section in presentation.additional_sections
            if extra_section.items
        ]
        if not non_empty:
            return
        _add_profile_heading(document, template_section.title, accent)
        for extra_section in non_empty:
            item_heading = document.add_paragraph(style="Heading 2")
            item_heading.paragraph_format.space_after = Pt(0)
            item_heading.add_run(extra_section.title)
            for item in extra_section.items:
                document.add_paragraph(item, style="List Bullet")


def _render_string_values(
    document: Document,
    title: str,
    values: list[str],
    layout: TemplateSectionLayout,
    accent: RGBColor,
) -> None:
    clean = [value for value in values if value]
    if not clean:
        return
    _add_profile_heading(document, title, accent)
    selected_layout = "inline" if layout == "default" else layout
    if selected_layout == "bullets":
        for value in clean:
            document.add_paragraph(value, style="List Bullet")
    else:
        document.add_paragraph(", ".join(clean))


def _add_profile_heading(
    document: Document,
    text: str,
    accent: RGBColor,
) -> None:
    paragraph = document.add_paragraph(style="Heading 1")
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(3)
    run = paragraph.add_run(text)
    run.font.color.rgb = accent


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


def _rgb_from_hex(value: str) -> RGBColor:
    normalized = value.lstrip("#")
    return RGBColor(
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )
