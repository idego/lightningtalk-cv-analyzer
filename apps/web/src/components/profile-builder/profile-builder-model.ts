export type ProfileLink = { label: string; url: string };

export type ProfileCustomFieldKind = "text" | "number" | "boolean" | "date" | "select";

export type ProfileCustomFieldValue = {
  id: string;
  label: string;
  kind: ProfileCustomFieldKind;
  value: string | number | boolean | null;
  options: string[];
};

export type ProfileCustomFieldDefinition = {
  id: string;
  label: string;
  kind: ProfileCustomFieldKind;
  options: string[];
  default_value: string | number | boolean | null;
};

export type CandidateProfile = {
  schema_version: "candidate-profile-v1";
  personal: {
    first_name: string | null;
    last_name: string | null;
    email: string | null;
    phone: string | null;
    location: string | null;
    links: {
      linkedin: string | null;
      github: string | null;
      portfolio: string | null;
      other: ProfileLink[];
    };
  };
  headline: string | null;
  summary: string | null;
  skills: string[];
  technologies: string[];
  experience: Array<{
    id: string;
    company: string | null;
    company_category: string | null;
    role: string | null;
    project: string | null;
    location: string | null;
    start_date: string | null;
    end_date: string | null;
    current: boolean;
    responsibilities: string[];
    achievements: string[];
    technologies: string[];
  }>;
  education: Array<{
    id: string;
    institution: string | null;
    degree: string | null;
    field: string | null;
    start_date: string | null;
    end_date: string | null;
    location: string | null;
    description: string | null;
  }>;
  languages: Array<{ id: string; language: string; level: string | null }>;
  certifications: Array<{
    id: string;
    name: string;
    issuer: string | null;
    date: string | null;
    url: string | null;
  }>;
  additional_sections: Array<{ id: string; title: string; items: string[] }>;
  custom_fields: ProfileCustomFieldValue[];
};

export type AnonymizationPolicy = {
  hide_first_name: boolean;
  hide_last_name: boolean;
  hide_email: boolean;
  hide_phone: boolean;
  hide_location: boolean;
  hide_linkedin: boolean;
  hide_github: boolean;
  hide_portfolio: boolean;
  employer_mode: "show" | "hide" | "genericize";
  institution_mode: "show" | "hide";
};

export type TemplateSectionKind =
  | "summary"
  | "skills"
  | "technologies"
  | "experience"
  | "education"
  | "languages"
  | "certifications"
  | "additional_sections"
  | "custom_fields";

export type ProfileTemplateSection = {
  id: string;
  kind: TemplateSectionKind;
  title: string;
  visible: boolean;
  layout: "default" | "inline" | "bullets";
  placement: "full" | "left" | "right";
};

export type ProfileTemplateLogo = {
  data_url: string;
  original_name: string;
  x_pct: number;
  y_pct: number;
  width_pct: number;
  aspect_ratio: number;
};

export type ProfileTemplate = {
  schema_version: "profile-template-v1";
  id: string;
  name: string;
  visibility: "private" | "shared";
  description: string | null;
  branding: {
    brand_name: string;
    accent_hex: string;
    show_brand: boolean;
  };
  typography: {
    font_family: "Aptos" | "Arial" | "Calibri";
    body_size: number;
    heading_size: number;
  };
  header: {
    show_name: boolean;
    show_headline: boolean;
    show_contact: boolean;
  };
  logo: ProfileTemplateLogo | null;
  sections: ProfileTemplateSection[];
};

export type ProfileBuilderPreferences = {
  auto_summary: boolean;
  summary_instruction: string;
  anonymization: AnonymizationPolicy;
  aggregate_technologies: boolean;
  date_format: "preserve" | "yyyy-mm" | "mm/yyyy" | "yyyy";
  default_template_id: string;
  filename_pattern: string;
};

export type ProfessionalSectionName =
  | "headline"
  | "summary"
  | "skills"
  | "technologies"
  | "experience"
  | "education"
  | "languages"
  | "certifications"
  | "additional_sections";

export type ProfileTemplateListItem = {
  template: ProfileTemplate;
  built_in: boolean;
  customized: boolean;
  created_at: string | null;
  updated_at: string | null;
  shared?: boolean;
  overrides_shared?: boolean;
};

export type RecentProfileItem = {
  profile_id: string;
  source_filename: string;
  candidate_name: string | null;
  template_id: string;
  template_name: string;
  created_at: string;
  updated_at: string;
};

export type ProfileSnapshotPayload = {
  source_filename: string;
  profile: CandidateProfile;
  anonymization: AnonymizationPolicy;
  template: ProfileTemplate;
};

export type StoredProfile = ProfileSnapshotPayload & {
  profile_id: string;
  created_at: string;
  updated_at: string;
};

export type PersistedProfileResponse = {
  profile_id?: string;
  snapshot?: ProfileSnapshotPayload;
};

export type ProfileExtractionResponse = {
  filename: string;
  profile: CandidateProfile;
  warnings: string[];
};

export type ProfessionalProposal = Omit<
  CandidateProfile,
  "schema_version" | "personal" | "custom_fields"
>;

export type BatchConversionItem = {
  id: string;
  file: File;
  status: "queued" | "processing" | "completed" | "failed";
  profile_id: string | null;
  candidate_name: string | null;
  error: string | null;
};

export const PROFESSIONAL_SECTION_LABELS: Record<ProfessionalSectionName, string> = {
  headline: "Headline",
  summary: "Summary",
  skills: "Skills",
  technologies: "Technologies",
  experience: "Experience",
  education: "Education",
  languages: "Languages",
  certifications: "Certifications",
  additional_sections: "Additional sections",
};

export const PROFESSIONAL_SECTIONS = Object.keys(PROFESSIONAL_SECTION_LABELS) as ProfessionalSectionName[];

export const DEFAULT_ANONYMIZATION: AnonymizationPolicy = {
  hide_first_name: true,
  hide_last_name: true,
  hide_email: true,
  hide_phone: true,
  hide_location: true,
  hide_linkedin: true,
  hide_github: true,
  hide_portfolio: true,
  employer_mode: "hide",
  institution_mode: "hide",
};

export const REVEALED_ANONYMIZATION: AnonymizationPolicy = {
  hide_first_name: false,
  hide_last_name: false,
  hide_email: false,
  hide_phone: false,
  hide_location: false,
  hide_linkedin: false,
  hide_github: false,
  hide_portfolio: false,
  employer_mode: "show",
  institution_mode: "show",
};

export const DEFAULT_PROFILE_BUILDER_PREFERENCES: ProfileBuilderPreferences = {
  auto_summary: false,
  summary_instruction: "",
  anonymization: DEFAULT_ANONYMIZATION,
  aggregate_technologies: true,
  date_format: "preserve",
  default_template_id: "idego-default",
  filename_pattern: "{name}-profile",
};

export const DEFAULT_PROFILE_TEMPLATE: ProfileTemplate = {
  schema_version: "profile-template-v1",
  id: "idego-default",
  name: "IDEGO Default",
  visibility: "shared",
  description: "Default IDEGO candidate profile layout.",
  branding: { brand_name: "IDEGO", accent_hex: "#3CC2D9", show_brand: true },
  typography: { font_family: "Aptos", body_size: 10.5, heading_size: 14 },
  header: { show_name: true, show_headline: true, show_contact: true },
  logo: null,
  sections: [
    { id: "summary", kind: "summary", title: "Summary", visible: true, layout: "default", placement: "full" },
    { id: "skills", kind: "skills", title: "Skills", visible: true, layout: "inline", placement: "full" },
    { id: "technologies", kind: "technologies", title: "Technologies", visible: true, layout: "inline", placement: "full" },
    { id: "experience", kind: "experience", title: "Experience", visible: true, layout: "default", placement: "full" },
    { id: "education", kind: "education", title: "Education", visible: true, layout: "default", placement: "full" },
    { id: "languages", kind: "languages", title: "Languages", visible: true, layout: "inline", placement: "full" },
    { id: "certifications", kind: "certifications", title: "Certifications", visible: true, layout: "bullets", placement: "full" },
    { id: "additional-sections", kind: "additional_sections", title: "Additional", visible: true, layout: "bullets", placement: "full" },
    { id: "custom-fields", kind: "custom_fields", title: "Details", visible: true, layout: "default", placement: "full" },
  ],
};

export const PROFILE_TEMPLATE_SAMPLE_PROFILE: CandidateProfile = {
  schema_version: "candidate-profile-v1",
  personal: {
    first_name: "Alex",
    last_name: "Morgan",
    email: "alex.morgan@example.com",
    phone: "+48 500 600 700",
    location: "Gdańsk, Poland",
    links: {
      linkedin: "linkedin.com/in/alex-morgan",
      github: null,
      portfolio: "alexmorgan.dev",
      other: [],
    },
  },
  headline: "Senior Backend Engineer",
  summary: "Backend engineer focused on reliable Python services, APIs, and data-heavy products.",
  skills: ["Backend engineering", "System design", "API design", "Mentoring"],
  technologies: ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS"],
  experience: [
    {
      id: "sample-experience-1",
      company: "Example Labs",
      company_category: "Software company",
      role: "Senior Backend Engineer",
      project: "Payments platform",
      location: "Remote",
      start_date: "2023",
      end_date: null,
      current: true,
      responsibilities: ["Designed and maintained backend services.", "Improved API reliability and observability."],
      achievements: ["Reduced critical request latency by 35%."],
      technologies: ["Python", "FastAPI", "PostgreSQL"],
    },
    {
      id: "sample-experience-2",
      company: "Northstar Systems",
      company_category: "Technology company",
      role: "Backend Developer",
      project: null,
      location: "Gdańsk",
      start_date: "2020",
      end_date: "2023",
      current: false,
      responsibilities: ["Built internal automation and customer-facing APIs."],
      achievements: [],
      technologies: ["Python", "Docker"],
    },
  ],
  education: [
    {
      id: "sample-education-1",
      institution: "Example University",
      degree: "BSc",
      field: "Computer Science",
      start_date: "2017",
      end_date: "2020",
      location: "Gdańsk",
      description: null,
    },
  ],
  languages: [
    { id: "sample-language-1", language: "English", level: "C1" },
    { id: "sample-language-2", language: "Polish", level: "Native" },
  ],
  certifications: [
    { id: "sample-cert-1", name: "Cloud Practitioner", issuer: "Example Cloud", date: "2024", url: null },
  ],
  additional_sections: [
    { id: "sample-additional-1", title: "Community", items: ["Mentors junior engineers and contributes to internal guilds."] },
  ],
  custom_fields: [
    { id: "availability", label: "Availability", kind: "text", value: "2 weeks", options: [] },
    { id: "rate", label: "Rate", kind: "text", value: "Negotiable", options: [] },
  ],
};

export function newProfileBuilderId(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36)}`;
}

export function serializeProfileSnapshot(snapshot: ProfileSnapshotPayload) {
  return JSON.stringify({
    source_filename: snapshot.source_filename,
    profile: snapshot.profile,
    anonymization: snapshot.anonymization,
    template: snapshot.template,
  });
}

export function derivedPresentation(
  profile: CandidateProfile,
  policy: AnonymizationPolicy,
): CandidateProfile {
  return {
    ...profile,
    personal: {
      ...profile.personal,
      first_name: policy.hide_first_name ? null : profile.personal.first_name,
      last_name: policy.hide_last_name ? null : profile.personal.last_name,
      email: policy.hide_email ? null : profile.personal.email,
      phone: policy.hide_phone ? null : profile.personal.phone,
      location: policy.hide_location ? null : profile.personal.location,
      links: {
        ...profile.personal.links,
        linkedin: policy.hide_linkedin ? null : profile.personal.links.linkedin,
        github: policy.hide_github ? null : profile.personal.links.github,
        portfolio: policy.hide_portfolio ? null : profile.personal.links.portfolio,
      },
    },
    experience: profile.experience.map((entry) => ({
      ...entry,
      company:
        policy.employer_mode === "show"
          ? entry.company
          : policy.employer_mode === "hide"
            ? null
            : entry.company_category || "Company",
    })),
    education: profile.education.map((entry) => ({
      ...entry,
      institution: policy.institution_mode === "hide" ? null : entry.institution,
    })),
  };
}
