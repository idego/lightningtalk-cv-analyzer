"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Check,
  ChevronUp,
  Download,
  Eye,
  EyeOff,
  FileText,
  History,
  LayoutTemplate,
  LoaderCircle,
  Pencil,
  Plus,
  RotateCcw,
  ShieldCheck,
  Trash2,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAppSettings } from "@/lib/app-settings";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const ACCEPT = ".pdf,.docx";
export const SELECTED_TEMPLATE_STORAGE_KEY = "cv-profile-builder-selected-template-v1";

export type ProfileLink = { label: string; url: string };
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
  | "additional_sections";

export type ProfileTemplateSection = {
  id: string;
  kind: TemplateSectionKind;
  title: string;
  visible: boolean;
  layout: "default" | "inline" | "bullets";
};

export type ProfileTemplate = {
  schema_version: "profile-template-v1";
  id: string;
  name: string;
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
  sections: ProfileTemplateSection[];
};

type ExtractResponse = {
  filename: string;
  profile: CandidateProfile;
  warnings: string[];
};

type TemplateListItem = {
  template: ProfileTemplate;
  built_in: boolean;
  customized: boolean;
  created_at: string | null;
  updated_at: string | null;
};

type RecentProfileItem = {
  profile_id: string;
  source_filename: string;
  candidate_name: string | null;
  template_id: string;
  template_name: string;
  created_at: string;
  updated_at: string;
};

type StoredProfile = {
  profile_id: string;
  source_filename: string;
  profile: CandidateProfile;
  anonymization: AnonymizationPolicy;
  template: ProfileTemplate;
  created_at: string;
  updated_at: string;
};

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

const REVEALED_ANONYMIZATION: AnonymizationPolicy = {
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

export const DEFAULT_PROFILE_TEMPLATE: ProfileTemplate = {
  schema_version: "profile-template-v1",
  id: "idego-default",
  name: "IDEGO Default",
  description: "Default IDEGO candidate profile layout.",
  branding: {
    brand_name: "IDEGO",
    accent_hex: "#3CC2D9",
    show_brand: true,
  },
  typography: {
    font_family: "Aptos",
    body_size: 10.5,
    heading_size: 14,
  },
  header: {
    show_name: true,
    show_headline: true,
    show_contact: true,
  },
  sections: [
    { id: "summary", kind: "summary", title: "Summary", visible: true, layout: "default" },
    { id: "skills", kind: "skills", title: "Skills", visible: true, layout: "inline" },
    { id: "technologies", kind: "technologies", title: "Technologies", visible: true, layout: "inline" },
    { id: "experience", kind: "experience", title: "Experience", visible: true, layout: "default" },
    { id: "education", kind: "education", title: "Education", visible: true, layout: "default" },
    { id: "languages", kind: "languages", title: "Languages", visible: true, layout: "inline" },
    { id: "certifications", kind: "certifications", title: "Certifications", visible: true, layout: "bullets" },
    { id: "additional-sections", kind: "additional_sections", title: "Additional", visible: true, layout: "bullets" },
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
};

const EDITOR_SECTIONS = [
  "personal",
  "profile",
  "anonymization",
  "experience",
  "education",
  "languages",
  "certifications",
  "additional",
] as const;
type EditorSectionId = (typeof EDITOR_SECTIONS)[number];

export function newProfileBuilderId(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36)}`;
}

function nonEmptyLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
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

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value || null)}
      />
    </div>
  );
}

function TextareaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
      />
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 accent-[var(--primary)]"
      />
    </label>
  );
}

function pointsToPixels(value: number) {
  return value * (4 / 3);
}


function PreviewSection({
  title,
  accent,
  headingSize,
  children,
}: {
  title: string;
  accent: string;
  headingSize: number;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h3
        className="break-after-avoid border-b pb-1 font-semibold"
        style={{ color: accent, fontSize: `${pointsToPixels(headingSize)}px` }}
      >
        {title}
      </h3>
      {children}
    </section>
  );
}

function StringListPreview({ values, layout }: { values: string[]; layout: ProfileTemplateSection["layout"] }) {
  if (layout === "bullets") {
    return <ul className="list-disc space-y-0.5 pl-5">{values.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}</ul>;
  }
  return <p>{values.join(", ")}</p>;
}

function TemplateSectionPreview({
  section,
  profile,
  template,
}: {
  section: ProfileTemplateSection;
  profile: CandidateProfile;
  template: ProfileTemplate;
}) {
  if (!section.visible) return null;
  const shared = {
    accent: template.branding.accent_hex,
    headingSize: template.typography.heading_size,
  };
  if (section.kind === "summary") {
    return profile.summary ? <PreviewSection title={section.title} {...shared}><p className="whitespace-pre-wrap">{profile.summary}</p></PreviewSection> : null;
  }
  if (section.kind === "skills") {
    return profile.skills.length ? <PreviewSection title={section.title} {...shared}><StringListPreview values={profile.skills} layout={section.layout} /></PreviewSection> : null;
  }
  if (section.kind === "technologies") {
    return profile.technologies.length ? <PreviewSection title={section.title} {...shared}><StringListPreview values={profile.technologies} layout={section.layout} /></PreviewSection> : null;
  }
  if (section.kind === "experience") {
    return profile.experience.length ? <PreviewSection title={section.title} {...shared}><div className="space-y-5">{profile.experience.map((entry) => (
      <div key={entry.id} className="break-inside-avoid space-y-1.5">
        <p className="font-semibold text-slate-900">{[entry.role, entry.company].filter(Boolean).join(" — ") || "Experience"}</p>
        <p className="text-xs text-slate-500">{[
          entry.start_date && (entry.current ? `${entry.start_date} – Present` : entry.end_date ? `${entry.start_date} – ${entry.end_date}` : entry.start_date),
          entry.location,
          entry.project,
        ].filter(Boolean).join(" · ")}</p>
        {entry.responsibilities.length ? <ul className="list-disc space-y-0.5 pl-5">{entry.responsibilities.map((item, index) => <li key={`${entry.id}-responsibility-${index}`}>{item}</li>)}</ul> : null}
        {entry.achievements.length ? <ul className="list-disc space-y-0.5 pl-5 font-medium">{entry.achievements.map((item, index) => <li key={`${entry.id}-achievement-${index}`}>{item}</li>)}</ul> : null}
        {entry.technologies.length ? <p className="text-xs"><span className="font-semibold">Technologies:</span> {entry.technologies.join(", ")}</p> : null}
      </div>
    ))}</div></PreviewSection> : null;
  }
  if (section.kind === "education") {
    return profile.education.length ? <PreviewSection title={section.title} {...shared}><div className="space-y-4">{profile.education.map((entry) => (
      <div key={entry.id} className="break-inside-avoid">
        <p className="font-semibold text-slate-900">{[entry.degree, entry.field, entry.institution].filter(Boolean).join(" — ") || "Education"}</p>
        <p className="text-xs text-slate-500">{[
          entry.start_date && entry.end_date ? `${entry.start_date} – ${entry.end_date}` : entry.start_date || entry.end_date,
          entry.location,
        ].filter(Boolean).join(" · ")}</p>
        {entry.description ? <p className="mt-1 whitespace-pre-wrap">{entry.description}</p> : null}
      </div>
    ))}</div></PreviewSection> : null;
  }
  if (section.kind === "languages") {
    const values = profile.languages.map((entry) => [entry.language, entry.level].filter(Boolean).join(" — "));
    return values.length ? <PreviewSection title={section.title} {...shared}><StringListPreview values={values} layout={section.layout} /></PreviewSection> : null;
  }
  if (section.kind === "certifications") {
    const values = profile.certifications.map((entry) => [entry.name, entry.issuer, entry.date, entry.url].filter(Boolean).join(" — "));
    return values.length ? <PreviewSection title={section.title} {...shared}><StringListPreview values={values} layout={section.layout} /></PreviewSection> : null;
  }
  if (section.kind === "additional_sections") {
    const additional = profile.additional_sections.filter((item) => item.items.length);
    return additional.length ? (
      <PreviewSection title={section.title} {...shared}>
        <div className="space-y-3">
          {additional.map((item) => (
            <div key={item.id} className="break-inside-avoid">
              <p className="mb-1 font-semibold text-slate-900">{item.title}</p>
              <StringListPreview values={item.items} layout="bullets" />
            </div>
          ))}
        </div>
      </PreviewSection>
    ) : null;
  }
  return null;
}

export function ProfileDocumentPreview({
  profile,
  template,
  label = "Profile layout preview",
}: {
  profile: CandidateProfile;
  template: ProfileTemplate;
  label?: string;
}) {
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageCount, setPreviewPageCount] = useState(1);
  const previewViewportRef = useRef<HTMLDivElement>(null);
  const previewFlowRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const viewport = previewViewportRef.current;
    const flow = previewFlowRef.current;
    if (!viewport || !flow) return;
    const measure = () => {
      const pageWidth = viewport.clientWidth;
      if (!pageWidth) return;
      flow.style.setProperty("--preview-page-width", `${pageWidth}px`);
      const count = Math.max(1, Math.ceil(flow.scrollWidth / pageWidth));
      setPreviewPageCount(count);
      setPreviewPage((current) => Math.min(current, count));
    };
    const observer = new ResizeObserver(measure);
    observer.observe(viewport);
    observer.observe(flow);
    const frame = requestAnimationFrame(measure);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [profile, template]);

  const fullName = [profile.personal.first_name, profile.personal.last_name].filter(Boolean).join(" ");
  const contacts = [
    profile.personal.email,
    profile.personal.phone,
    profile.personal.location,
    profile.personal.links.linkedin,
    profile.personal.links.github,
    profile.personal.links.portfolio,
    ...profile.personal.links.other.map((link) => link.label ? `${link.label}: ${link.url}` : link.url),
  ].filter(Boolean);

  return (
    <div className="min-w-0">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="size-4" />{label} · {template.name}
        </div>
        <div className="flex items-center gap-1 rounded-lg border bg-card p-1" role="group" aria-label="Preview page navigation">
          <Button variant="ghost" size="icon-sm" aria-label="Previous preview page" disabled={previewPage <= 1} onClick={() => setPreviewPage((current) => Math.max(1, current - 1))}><ChevronLeft /></Button>
          <span className="min-w-16 text-center text-xs font-medium tabular-nums">{previewPage} / {previewPageCount}</span>
          <Button variant="ghost" size="icon-sm" aria-label="Next preview page" disabled={previewPage >= previewPageCount} onClick={() => setPreviewPage((current) => Math.min(previewPageCount, current + 1))}><ChevronRight /></Button>
        </div>
      </div>
      <div className="relative mx-auto aspect-[210/297] w-full max-w-[760px] overflow-hidden bg-white text-[#081932] shadow-[0_8px_30px_rgba(8,25,50,0.12)] ring-1 ring-black/10 dark:text-[#081932]">
        <div ref={previewViewportRef} className="absolute inset-x-[7.5%] bottom-[7%] top-[6.5%] overflow-hidden">
          <div
            ref={previewFlowRef}
            className="h-full max-w-none bg-white leading-relaxed text-slate-700 transition-transform duration-200 ease-out [column-fill:auto] [column-gap:0]"
            style={{
              width: "var(--preview-page-width)",
              columnWidth: "var(--preview-page-width)",
              transform: `translateX(calc(-1 * ${previewPage - 1} * var(--preview-page-width)))`,
              fontFamily: template.typography.font_family,
              fontSize: `${pointsToPixels(template.typography.body_size)}px`,
            }}
          >
            <div className="mb-8 flex break-inside-avoid items-center justify-between gap-4 border-b-2 pb-4" style={{ borderColor: template.branding.accent_hex }}>
              <div>
                {template.header.show_name ? <p className="font-semibold tracking-tight" style={{ fontSize: `${pointsToPixels(Math.min(template.typography.heading_size + 10, 30))}px` }}>{fullName || "Candidate Profile"}</p> : null}
                {template.header.show_headline && profile.headline ? <p className="mt-1 text-base text-slate-600">{profile.headline}</p> : null}
              </div>
              {template.branding.show_brand ? <div className="text-right">
                <p className="text-lg font-bold tracking-[0.16em]" style={{ color: template.branding.accent_hex }}>{template.branding.brand_name}</p>
                <p className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Candidate Profile</p>
              </div> : null}
            </div>
            <div className="space-y-6">
              {template.header.show_contact && contacts.length ? <p className="text-xs text-slate-500">{contacts.join(" · ")}</p> : null}
              {template.sections.map((section) => <TemplateSectionPreview key={section.id} section={section} profile={profile} template={template} />)}
            </div>
          </div>
        </div>
        <div className="absolute inset-x-[7.5%] bottom-[2.5%] flex items-center justify-between border-t pt-2 text-[10px] text-slate-400">
          <span><FileText className="mr-1 inline size-3" />{template.branding.show_brand ? `${template.branding.brand_name} Candidate Profile` : "Candidate Profile"}</span>
          <span>Page {previewPage} of {previewPageCount}</span>
        </div>
      </div>
      <p className="mx-auto mt-2 max-w-[760px] text-[11px] leading-relaxed text-muted-foreground">
        Page breaks reflect this browser preview. Final DOCX pagination can vary slightly between Word-compatible renderers.
      </p>
    </div>
  );
}

function TemplateManagerDialog({
  open,
  onOpenChange,
  items,
  selectedTemplate,
  onSelect,
  onDelete,
  onEdit,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: TemplateListItem[];
  selectedTemplate: ProfileTemplate;
  onSelect: (template: ProfileTemplate) => void;
  onDelete: (item: TemplateListItem) => void;
  onEdit: (templateId: string) => void;
  onCreate: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Templates</DialogTitle>
          <DialogDescription>Choose the layout used for preview and export, or open the Template Creator.</DialogDescription>
        </DialogHeader>
        <div className="max-h-[55vh] space-y-2 overflow-y-auto pr-1">
          {items.map((item) => {
            const selected = item.template.id === selectedTemplate.id;
            return <div key={item.template.id} className={`flex items-center gap-3 rounded-xl border p-3 ${selected ? "border-primary/40 bg-primary/5" : ""}`}>
              <button type="button" className="min-w-0 flex-1 text-left" onClick={() => onSelect(item.template)}>
                <span className="flex items-center gap-2"><span className="truncate font-medium">{item.template.name}</span>{selected ? <Check className="size-4 text-primary" /> : null}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{item.template.description || "Custom profile template"}{item.built_in ? item.customized ? " · customized default" : " · built-in" : ""}</span>
              </button>
              <Button variant="ghost" size="icon-sm" aria-label={`Edit ${item.template.name}`} onClick={() => onEdit(item.template.id)}><Pencil /></Button>
              {(!item.built_in || item.customized) ? <Button variant="ghost" size="icon-sm" aria-label={item.built_in ? "Reset built-in template" : `Delete ${item.template.name}`} onClick={() => onDelete(item)}><Trash2 /></Button> : null}
            </div>;
          })}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCreate}><Plus />Create template</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ProfileBuilderWorkspace() {
  const settings = useAppSettings();
  const router = useRouter();
  const searchParams = useSearchParams();
  const reopenProfileId = searchParams.get("profile");
  const [profileId, setProfileId] = useState<string | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [sourceFilename, setSourceFilename] = useState<string | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [anonymization, setAnonymization] = useState(DEFAULT_ANONYMIZATION);
  const [selectedTemplate, setSelectedTemplate] = useState<ProfileTemplate>(DEFAULT_PROFILE_TEMPLATE);
  const [templateItems, setTemplateItems] = useState<TemplateListItem[]>([
    { template: DEFAULT_PROFILE_TEMPLATE, built_in: true, customized: false, created_at: null, updated_at: null },
  ]);
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [recentProfiles, setRecentProfiles] = useState<RecentProfileItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [openingProfileId, setOpeningProfileId] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<EditorSectionId>>(
    () => new Set(EDITOR_SECTIONS),
  );
  const latestSnapshotRef = useRef<{
    profile_id: string;
    source_filename: string;
    profile: CandidateProfile;
    anonymization: AnonymizationPolicy;
    template: ProfileTemplate;
  } | null>(null);
  const lastSavedSnapshotRef = useRef<string | null>(null);
  const templateSelectionLockedRef = useRef(false);
  const saveInFlightRef = useRef(false);
  const saveQueuedRef = useRef(false);
  const lastSaveOkRef = useRef(true);

  const presentation = useMemo(
    () => (profile ? derivedPresentation(profile, anonymization) : null),
    [profile, anonymization],
  );

  const refreshRecentProfiles = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const response = await fetch("/api/profile-builder/profiles", { cache: "no-store" });
      if (!response.ok) throw new Error("recent_profiles_unavailable");
      const body = await response.json() as { profiles?: RecentProfileItem[] };
      setRecentProfiles(body.profiles ?? []);
    } catch {
      setRecentProfiles([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const refreshTemplates = useCallback(async () => {
    try {
      const response = await fetch("/api/profile-builder/templates", { cache: "no-store" });
      if (!response.ok) throw new Error("templates_unavailable");
      const body = await response.json() as { templates?: TemplateListItem[] };
      const items = body.templates?.length ? body.templates : [
        { template: DEFAULT_PROFILE_TEMPLATE, built_in: true, customized: false, created_at: null, updated_at: null },
      ];
      setTemplateItems(items);
      setSelectedTemplate((current) => {
        if (templateSelectionLockedRef.current) return current;
        const preferredId = window.localStorage.getItem(SELECTED_TEMPLATE_STORAGE_KEY) || current.id;
        return items.find((item) => item.template.id === preferredId)?.template
          ?? items.find((item) => item.template.id === current.id)?.template
          ?? items[0].template;
      });
    } catch {
      setTemplateItems((current) => current.length ? current : [
        { template: DEFAULT_PROFILE_TEMPLATE, built_in: true, customized: false, created_at: null, updated_at: null },
      ]);
    }
  }, []);

  const openStoredProfile = useCallback(async (storedProfileId: string) => {
    setOpeningProfileId(storedProfileId);
    setError(null);
    try {
      const response = await fetch(`/api/profile-builder/profiles/${encodeURIComponent(storedProfileId)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("recent_profile_unavailable");
      const stored = await response.json() as StoredProfile;
      templateSelectionLockedRef.current = true;
      setProfileId(stored.profile_id);
      setProfile(stored.profile);
      setSourceFilename(stored.source_filename);
      setSourceFile(null);
      setAnonymization(stored.anonymization);
      setSelectedTemplate(stored.template);
      window.localStorage.setItem(SELECTED_TEMPLATE_STORAGE_KEY, stored.template.id);
      setExpandedSections(new Set(EDITOR_SECTIONS));
      lastSavedSnapshotRef.current = JSON.stringify({
        source_filename: stored.source_filename,
        profile: stored.profile,
        anonymization: stored.anonymization,
        template: stored.template,
      });
      lastSaveOkRef.current = true;
      setSaveStatus("saved");
    } catch {
      setError("This recent profile is no longer available.");
      void refreshRecentProfiles();
    } finally {
      setOpeningProfileId(null);
    }
  }, [refreshRecentProfiles]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void refreshRecentProfiles();
      void refreshTemplates();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshRecentProfiles, refreshTemplates]);

  useEffect(() => {
    if (!reopenProfileId || profile || profileId === reopenProfileId) return;
    const timer = window.setTimeout(() => { void openStoredProfile(reopenProfileId); }, 0);
    return () => window.clearTimeout(timer);
  }, [reopenProfileId, profile, profileId, openStoredProfile]);

  const flushAutosave = useCallback(async function flushAutosaveNow() {
    if (saveInFlightRef.current) {
      saveQueuedRef.current = true;
      return;
    }
    const snapshot = latestSnapshotRef.current;
    if (!snapshot) return;
    const serialized = JSON.stringify({
      source_filename: snapshot.source_filename,
      profile: snapshot.profile,
      anonymization: snapshot.anonymization,
      template: snapshot.template,
    });
    if (serialized === lastSavedSnapshotRef.current) {
      lastSavedSnapshotRef.current = serialized;
      lastSaveOkRef.current = true;
      setSaveStatus("saved");
      return;
    }
    saveInFlightRef.current = true;
    setSaveStatus("saving");
    try {
      const response = await fetch(`/api/profile-builder/profiles/${encodeURIComponent(snapshot.profile_id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_filename: snapshot.source_filename,
          profile: snapshot.profile,
          anonymization: snapshot.anonymization,
          template: snapshot.template,
        }),
      });
      if (!response.ok) throw new Error("profile_autosave_failed");
      lastSaveOkRef.current = true;
      setSaveStatus("saved");
      void refreshRecentProfiles();
    } catch {
      lastSaveOkRef.current = false;
      setSaveStatus("error");
    } finally {
      saveInFlightRef.current = false;
      if (saveQueuedRef.current) {
        saveQueuedRef.current = false;
        void flushAutosaveNow();
      }
    }
  }, [refreshRecentProfiles]);

  useEffect(() => {
    if (!profileId || !profile || !sourceFilename) {
      latestSnapshotRef.current = null;
      return;
    }
    latestSnapshotRef.current = {
      profile_id: profileId,
      source_filename: sourceFilename,
      profile,
      anonymization,
      template: selectedTemplate,
    };
    const serialized = JSON.stringify({
      source_filename: sourceFilename,
      profile,
      anonymization,
      template: selectedTemplate,
    });
    if (serialized === lastSavedSnapshotRef.current) return;
    const timer = window.setTimeout(() => { void flushAutosave(); }, 750);
    return () => window.clearTimeout(timer);
  }, [profileId, profile, sourceFilename, anonymization, selectedTemplate, flushAutosave]);

  function sectionIsOpen(section: EditorSectionId) {
    return expandedSections.has(section);
  }

  function toggleSection(section: EditorSectionId) {
    setExpandedSections((current) => {
      const next = new Set(current);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  }

  function sectionToggle(section: EditorSectionId, label: string) {
    const open = sectionIsOpen(section);
    return (
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
        aria-expanded={open}
        onClick={() => toggleSection(section)}
      >
        {open ? <ChevronUp /> : <ChevronDown />}
      </Button>
    );
  }

  function mutate(mutator: (draft: CandidateProfile) => void) {
    setProfile((current) => {
      if (!current) return current;
      const draft = structuredClone(current);
      mutator(draft);
      return draft;
    });
  }

  async function extract(file: File) {
    if (extracting) return;
    if (!settings.aiEnabled) {
      setError("Enable AI features in Settings before extracting a profile.");
      return;
    }
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      setError("Choose a PDF or DOCX file.");
      return;
    }
    setError(null);
    setSourceFile(file);
    setSourceFilename(file.name);
    setProfileId(null);
    setExtracting(true);
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const response = await fetch("/api/profile-builder/extract", {
        method: "POST",
        body: form,
        headers: { "X-AI-Enabled": String(settings.aiEnabled) },
      });
      const payload = (await response.json().catch(() => ({}))) as Partial<ExtractResponse> & {
        detail?: string;
        error?: string;
      };
      if (!response.ok || !payload.profile) {
        if (payload.detail === "profile_builder_ai_disabled_for_request") {
          throw new Error("Enable AI features in Settings before extracting a profile.");
        }
        if (payload.detail === "profile_builder_ai_disabled") {
          throw new Error("Profile Builder needs AI enabled on this deployment.");
        }
        throw new Error("Profile extraction failed. Check the file and try again.");
      }

      const extractedFilename = payload.filename ?? file.name;
      const extractedProfile = payload.profile;
      templateSelectionLockedRef.current = true;
      setProfile(extractedProfile);
      setSourceFilename(extractedFilename);
      setAnonymization(DEFAULT_ANONYMIZATION);
      setSaveStatus("saving");

      const persist = await fetch("/api/profile-builder/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          source_filename: extractedFilename,
          profile: extractedProfile,
          anonymization: DEFAULT_ANONYMIZATION,
          template: selectedTemplate,
        }),
      });
      const persisted = await persist.json().catch(() => ({})) as { profile_id?: string };
      if (persist.ok && persisted.profile_id) {
        setProfileId(persisted.profile_id);
        lastSavedSnapshotRef.current = JSON.stringify({
          source_filename: extractedFilename,
          profile: extractedProfile,
          anonymization: DEFAULT_ANONYMIZATION,
          template: selectedTemplate,
        });
        lastSaveOkRef.current = true;
        setSaveStatus("saved");
        void refreshRecentProfiles();
      } else {
        setSaveStatus("error");
        setError("Profile was extracted, but it could not be added to Recent profiles.");
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Profile extraction failed.");
    } finally {
      setExtracting(false);
    }
  }


  async function deleteRecentProfile(item: RecentProfileItem) {
    if (!window.confirm(`Delete ${item.candidate_name ?? item.source_filename}?`)) return;
    const response = await fetch(`/api/profile-builder/profiles/${encodeURIComponent(item.profile_id)}`, { method: "DELETE" });
    if (response.ok) {
      setRecentProfiles((current) => current.filter((profileItem) => profileItem.profile_id !== item.profile_id));
    } else {
      setError("The recent profile could not be deleted.");
    }
  }

  function selectTemplate(template: ProfileTemplate) {
    templateSelectionLockedRef.current = true;
    setSelectedTemplate(structuredClone(template));
    window.localStorage.setItem(SELECTED_TEMPLATE_STORAGE_KEY, template.id);
    setTemplateDialogOpen(false);
  }

  async function deleteTemplate(item: TemplateListItem) {
    const action = item.built_in ? "Reset the customized IDEGO Default template?" : `Delete ${item.template.name}?`;
    if (!window.confirm(action)) return;
    const response = await fetch(`/api/profile-builder/templates/${encodeURIComponent(item.template.id)}`, { method: "DELETE" });
    if (!response.ok) {
      setError("The template could not be deleted.");
      return;
    }
    if (selectedTemplate.id === item.template.id) {
      templateSelectionLockedRef.current = true;
      setSelectedTemplate(DEFAULT_PROFILE_TEMPLATE);
      window.localStorage.setItem(SELECTED_TEMPLATE_STORAGE_KEY, DEFAULT_PROFILE_TEMPLATE.id);
    }
    await refreshTemplates();
  }

  async function persistBeforeTemplateNavigation() {
    if (!profileId || !profile || !sourceFilename) return true;
    latestSnapshotRef.current = {
      profile_id: profileId,
      source_filename: sourceFilename,
      profile,
      anonymization,
      template: selectedTemplate,
    };
    if (saveInFlightRef.current) saveQueuedRef.current = true;
    else void flushAutosave();
    while (saveInFlightRef.current || saveQueuedRef.current) {
      await new Promise((resolve) => window.setTimeout(resolve, 25));
    }
    return lastSaveOkRef.current;
  }

  async function openTemplateCreator(templateId: string | null) {
    setTemplateDialogOpen(false);
    const saved = await persistBeforeTemplateNavigation();
    if (!saved) {
      setError("Autosave failed, so Template Creator was not opened. Retry after the profile saves.");
      return;
    }
    const returnQuery = profileId ? `?profile=${encodeURIComponent(profileId)}` : "";
    router.push(`/profile-builder/templates/${encodeURIComponent(templateId ?? "new")}${returnQuery}`);
  }

  async function exportDocx() {
    if (!profile) return;
    setError(null);
    setExporting(true);
    try {
      const response = await fetch("/api/profile-builder/export/docx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile,
          anonymization,
          template_id: selectedTemplate.id,
          template: selectedTemplate,
        }),
      });
      if (!response.ok) throw new Error("DOCX export failed.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const exportedProfile = derivedPresentation(profile, anonymization);
      const name = [exportedProfile.personal.first_name, exportedProfile.personal.last_name]
        .filter(Boolean)
        .join("-")
        .replace(/[^\p{L}\p{N}-]+/gu, "-")
        .replace(/^-+|-+$/g, "")
        .toLowerCase();
      anchor.href = url;
      anchor.download = `${name || "candidate"}-profile.docx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "DOCX export failed.");
    } finally {
      setExporting(false);
    }
  }

  function reset() {
    setProfileId(null);
    setProfile(null);
    setSourceFilename(null);
    setSourceFile(null);
    setAnonymization(DEFAULT_ANONYMIZATION);
    setExpandedSections(new Set(EDITOR_SECTIONS));
    setSaveStatus("idle");
    setError(null);
    latestSnapshotRef.current = null;
    lastSavedSnapshotRef.current = null;
    lastSaveOkRef.current = true;
    void refreshRecentProfiles();
  }

  if (!profile || !presentation) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">Profile Builder</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Drop in a CV, correct the extracted profile, choose a template, and export the exact current version to DOCX.
          </p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Upload candidate CV</CardTitle>
            <CardDescription>PDF or DOCX. National identifiers are redacted before AI extraction.</CardDescription>
          </CardHeader>
          <CardContent>
            <label
              className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-muted-foreground/30 bg-muted/20 p-8 text-center transition-colors hover:bg-muted/35"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                if (extracting) return;
                const file = event.dataTransfer.files[0];
                if (file) void extract(file);
              }}
            >
              <input
                type="file"
                accept={ACCEPT}
                className="hidden"
                disabled={extracting || !settings.aiEnabled}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void extract(file);
                }}
              />
              {extracting ? (
                <LoaderCircle className="mb-4 size-9 animate-spin text-primary" />
              ) : (
                <Upload className="mb-4 size-9 text-primary" />
              )}
              <p className="font-medium">{extracting ? "Extracting candidate profile…" : "Drop a CV here or click to select"}</p>
              <p className="mt-1 text-xs text-muted-foreground">Accepted: PDF, DOCX</p>
              {!settings.aiEnabled ? (
                <p className="mt-3 text-xs font-medium text-amber-700 dark:text-amber-400">
                  AI features are disabled in Settings. Profile extraction is paused.
                </p>
              ) : null}
            </label>
            {error ? (
              <div className="mt-4 flex flex-wrap items-center gap-3" aria-live="polite">
                <p className="min-w-0 flex-1 text-sm text-destructive">
                  {sourceFilename ? `${sourceFilename}: ` : ""}{error}
                </p>
                {sourceFile ? (
                  <Button variant="outline" size="sm" disabled={extracting} onClick={() => void extract(sourceFile)}>
                    Retry
                  </Button>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
          <section className="overflow-hidden rounded-xl border bg-card">
            <div className="flex items-center gap-2 border-b px-5 py-4">
              <History className="size-4" />
              <div className="min-w-0 flex-1">
                <h2 className="font-medium">Recent profiles</h2>
                <p className="text-xs text-muted-foreground">Reopen an extracted profile with its exact saved template and visibility settings.</p>
              </div>
            </div>
            {historyLoading ? <div className="flex items-center justify-center py-9"><LoaderCircle className="size-5 animate-spin text-muted-foreground" /></div> : null}
            {!historyLoading && !recentProfiles.length ? <p className="px-5 py-8 text-sm text-muted-foreground">No recent profiles yet.</p> : null}
            {recentProfiles.length ? <ul className="divide-y">{recentProfiles.slice(0, 10).map((item) => (
              <li key={item.profile_id} className="flex min-w-0 items-center gap-2 px-3 py-2">
                <button type="button" onClick={() => void openStoredProfile(item.profile_id)} disabled={openingProfileId === item.profile_id} className="min-w-0 flex-1 rounded-md px-2 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-sm font-medium">{item.candidate_name ?? item.source_filename}</span>
                    <time className="shrink-0 text-xs text-muted-foreground">{new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.updated_at))}</time>
                  </span>
                  <span className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{item.source_filename}</span>
                    <span aria-hidden>·</span>
                    <span className="truncate">{item.template_name}</span>
                  </span>
                </button>
                {openingProfileId === item.profile_id ? <LoaderCircle className="size-4 shrink-0 animate-spin text-muted-foreground" /> : null}
                <Button variant="ghost" size="icon" className="size-8 shrink-0" aria-label={`Delete ${item.candidate_name ?? item.source_filename}`} onClick={() => void deleteRecentProfile(item)}><Trash2 className="size-4" /></Button>
              </li>
            ))}</ul> : null}
          </section>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><LayoutTemplate className="size-4" />Current template</CardTitle>
              <CardDescription>Used for the next CV and carried with every saved profile.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="font-medium">{selectedTemplate.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{selectedTemplate.description || "Custom profile template"}</p>
                <p className="mt-3 text-xs text-muted-foreground">{selectedTemplate.sections.filter((section) => section.visible).length} visible blocks · {selectedTemplate.typography.font_family}</p>
              </div>
              <Button variant="outline" className="w-full" onClick={() => setTemplateDialogOpen(true)}><LayoutTemplate />Manage templates</Button>
            </CardContent>
          </Card>
        </div>

        <TemplateManagerDialog
          open={templateDialogOpen}
          onOpenChange={setTemplateDialogOpen}
          items={templateItems}
          selectedTemplate={selectedTemplate}
          onSelect={selectTemplate}
          onDelete={(item) => { void deleteTemplate(item); }}
          onEdit={(templateId) => { void openTemplateCreator(templateId); }}
          onCreate={() => { void openTemplateCreator(null); }}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1800px] space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{sourceFilename ?? "Candidate profile"}</p>
          <p className="text-xs text-muted-foreground">
            Template: {selectedTemplate.name}
            {saveStatus === "saving" ? " · Saving…" : saveStatus === "saved" ? " · Saved" : saveStatus === "error" ? " · Autosave failed" : ""}
          </p>
        </div>
        <Button variant="outline" onClick={() => setTemplateDialogOpen(true)}>
          <LayoutTemplate />Manage template
        </Button>
        <Button variant="outline" onClick={reset}>
          <RotateCcw data-icon="inline-start" />New CV
        </Button>
        <Button onClick={() => void exportDocx()} disabled={exporting}>
          {exporting ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Download data-icon="inline-start" />}
          {exporting ? "Exporting…" : "Export DOCX"}
        </Button>
      </div>
      {error ? <p className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p> : null}
      <TemplateManagerDialog
        open={templateDialogOpen}
        onOpenChange={setTemplateDialogOpen}
        items={templateItems}
        selectedTemplate={selectedTemplate}
        onSelect={selectTemplate}
        onDelete={(item) => { void deleteTemplate(item); }}
        onEdit={(templateId) => { void openTemplateCreator(templateId); }}
        onCreate={() => { void openTemplateCreator(null); }}
      />

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-card px-3 py-2">
            <p className="text-sm font-medium">Profile sections</p>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => setExpandedSections(new Set(EDITOR_SECTIONS))}>
                <ChevronDown />Expand all
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setExpandedSections(new Set())}>
                <ChevronUp />Collapse all
              </Button>
            </div>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Personal information</CardTitle>
              <CardDescription>Canonical values. Anonymization below only changes preview/export.</CardDescription>
              <CardAction>{sectionToggle("personal", "Personal information")}</CardAction>
            </CardHeader>
            {sectionIsOpen("personal") ? <CardContent className="grid gap-3 sm:grid-cols-2">
              <Field label="First name" value={profile.personal.first_name} onChange={(value) => mutate((draft) => { draft.personal.first_name = value; })} />
              <Field label="Last name" value={profile.personal.last_name} onChange={(value) => mutate((draft) => { draft.personal.last_name = value; })} />
              <Field label="Email" value={profile.personal.email} onChange={(value) => mutate((draft) => { draft.personal.email = value; })} />
              <Field label="Phone" value={profile.personal.phone} onChange={(value) => mutate((draft) => { draft.personal.phone = value; })} />
              <Field label="Location" value={profile.personal.location} onChange={(value) => mutate((draft) => { draft.personal.location = value; })} />
              <Field label="LinkedIn" value={profile.personal.links.linkedin} onChange={(value) => mutate((draft) => { draft.personal.links.linkedin = value; })} />
              <Field label="GitHub" value={profile.personal.links.github} onChange={(value) => mutate((draft) => { draft.personal.links.github = value; })} />
              <Field label="Portfolio" value={profile.personal.links.portfolio} onChange={(value) => mutate((draft) => { draft.personal.links.portfolio = value; })} />
              <div className="space-y-2 sm:col-span-2">
                <div className="flex items-center justify-between">
                  <Label>Other links</Label>
                  <Button variant="ghost" size="sm" onClick={() => mutate((draft) => { draft.personal.links.other.push({ label: "", url: "" }); })}>
                    <Plus />Add link
                  </Button>
                </div>
                {profile.personal.links.other.map((link, index) => (
                  <div key={index} className="grid gap-2 sm:grid-cols-[0.45fr_1fr_auto]">
                    <Input aria-label={`Other link ${index + 1} label`} value={link.label} placeholder="Label" onChange={(event) => mutate((draft) => { draft.personal.links.other[index].label = event.target.value; })} />
                    <Input aria-label={`Other link ${index + 1} URL`} value={link.url} placeholder="https://…" onChange={(event) => mutate((draft) => { draft.personal.links.other[index].url = event.target.value; })} />
                    <Button variant="ghost" size="icon" aria-label="Remove link" onClick={() => mutate((draft) => { draft.personal.links.other.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                ))}
              </div>
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader><CardTitle>Profile</CardTitle><CardAction>{sectionToggle("profile", "Profile")}</CardAction></CardHeader>
            {sectionIsOpen("profile") ? <CardContent className="space-y-3">
              <Field label="Headline" value={profile.headline} onChange={(value) => mutate((draft) => { draft.headline = value; })} />
              <TextareaField label="Summary" value={profile.summary ?? ""} rows={5} onChange={(value) => mutate((draft) => { draft.summary = value || null; })} />
              <div className="grid gap-3 sm:grid-cols-2">
                <TextareaField label="Skills" value={profile.skills.join("\n")} rows={5} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.skills = nonEmptyLines(value); })} />
                <TextareaField label="Technologies" value={profile.technologies.join("\n")} rows={5} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.technologies = nonEmptyLines(value); })} />
              </div>
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Anonymization</CardTitle>
              <CardDescription>Private by default. These controls only change preview/export and never delete canonical data.</CardDescription>
              <CardAction>{sectionToggle("anonymization", "Anonymization")}</CardAction>
            </CardHeader>
            {sectionIsOpen("anonymization") ? <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/45 px-3 py-2">
                <div>
                  <p className="text-sm font-medium">Visibility preset</p>
                  <p className="text-xs text-muted-foreground">Start anonymized, then reveal only what this profile needs.</p>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" onClick={() => setAnonymization(DEFAULT_ANONYMIZATION)}>
                    <EyeOff />Select all
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setAnonymization(REVEALED_ANONYMIZATION)}>
                    <Eye />Deselect all
                  </Button>
                </div>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {([
                  ["Hide first name", "hide_first_name"],
                  ["Hide last name", "hide_last_name"],
                  ["Hide email", "hide_email"],
                  ["Hide phone", "hide_phone"],
                  ["Hide location", "hide_location"],
                  ["Hide LinkedIn", "hide_linkedin"],
                  ["Hide GitHub", "hide_github"],
                  ["Hide portfolio", "hide_portfolio"],
                ] as const).map(([label, key]) => (
                  <Toggle key={key} label={label} checked={anonymization[key]} onChange={(checked) => setAnonymization((current) => ({ ...current, [key]: checked }))} />
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="profile-builder-employer-mode">Employer names</Label>
                  <select id="profile-builder-employer-mode" value={anonymization.employer_mode} onChange={(event) => setAnonymization((current) => ({ ...current, employer_mode: event.target.value as AnonymizationPolicy["employer_mode"] }))} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                    <option value="show">Show</option>
                    <option value="hide">Hide</option>
                    <option value="genericize">Genericize</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profile-builder-institution-mode">Institution names</Label>
                  <select id="profile-builder-institution-mode" value={anonymization.institution_mode} onChange={(event) => setAnonymization((current) => ({ ...current, institution_mode: event.target.value as AnonymizationPolicy["institution_mode"] }))} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                    <option value="show">Show</option>
                    <option value="hide">Hide</option>
                  </select>
                </div>
              </div>
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Experience</CardTitle>
              <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.experience.push({ id: newProfileBuilderId("experience"), company: null, company_category: null, role: null, project: null, location: null, start_date: null, end_date: null, current: false, responsibilities: [], achievements: [], technologies: [] }); })}><Plus />Add</Button>{sectionToggle("experience", "Experience")}</div></CardAction>
            </CardHeader>
            {sectionIsOpen("experience") ? <CardContent className="space-y-3">
              {profile.experience.length ? profile.experience.map((entry, index) => (
                <div key={entry.id} className="space-y-3 rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-medium">{entry.role || entry.company || `Experience ${index + 1}`}</p>
                    <Button variant="ghost" size="icon-sm" aria-label="Remove experience" onClick={() => mutate((draft) => { draft.experience.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Role" value={entry.role} onChange={(value) => mutate((draft) => { draft.experience[index].role = value; })} />
                    <Field label="Company" value={entry.company} onChange={(value) => mutate((draft) => { draft.experience[index].company = value; })} />
                    <Field label="Company category" value={entry.company_category} placeholder="Optional generic label" onChange={(value) => mutate((draft) => { draft.experience[index].company_category = value; })} />
                    <Field label="Project" value={entry.project} onChange={(value) => mutate((draft) => { draft.experience[index].project = value; })} />
                    <Field label="Location" value={entry.location} onChange={(value) => mutate((draft) => { draft.experience[index].location = value; })} />
                    <div className="grid grid-cols-2 gap-2">
                      <Field label="Start" value={entry.start_date} onChange={(value) => mutate((draft) => { draft.experience[index].start_date = value; })} />
                      <Field label="End" value={entry.end_date} onChange={(value) => mutate((draft) => { draft.experience[index].end_date = value; })} />
                    </div>
                  </div>
                  <Toggle label="Current role" checked={entry.current} onChange={(checked) => mutate((draft) => { draft.experience[index].current = checked; })} />
                  <TextareaField label="Responsibilities" value={entry.responsibilities.join("\n")} rows={4} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.experience[index].responsibilities = nonEmptyLines(value); })} />
                  <TextareaField label="Achievements" value={entry.achievements.join("\n")} rows={3} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.experience[index].achievements = nonEmptyLines(value); })} />
                  <TextareaField label="Technologies" value={entry.technologies.join("\n")} rows={3} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.experience[index].technologies = nonEmptyLines(value); })} />
                </div>
              )) : <p className="text-sm text-muted-foreground">No experience entries extracted.</p>}
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Education</CardTitle>
              <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.education.push({ id: newProfileBuilderId("education"), institution: null, degree: null, field: null, start_date: null, end_date: null, location: null, description: null }); })}><Plus />Add</Button>{sectionToggle("education", "Education")}</div></CardAction>
            </CardHeader>
            {sectionIsOpen("education") ? <CardContent className="space-y-3">
              {profile.education.length ? profile.education.map((entry, index) => (
                <div key={entry.id} className="space-y-3 rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-medium">{entry.institution || entry.degree || `Education ${index + 1}`}</p>
                    <Button variant="ghost" size="icon-sm" aria-label="Remove education" onClick={() => mutate((draft) => { draft.education.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Institution" value={entry.institution} onChange={(value) => mutate((draft) => { draft.education[index].institution = value; })} />
                    <Field label="Degree" value={entry.degree} onChange={(value) => mutate((draft) => { draft.education[index].degree = value; })} />
                    <Field label="Field" value={entry.field} onChange={(value) => mutate((draft) => { draft.education[index].field = value; })} />
                    <Field label="Location" value={entry.location} onChange={(value) => mutate((draft) => { draft.education[index].location = value; })} />
                    <Field label="Start" value={entry.start_date} onChange={(value) => mutate((draft) => { draft.education[index].start_date = value; })} />
                    <Field label="End" value={entry.end_date} onChange={(value) => mutate((draft) => { draft.education[index].end_date = value; })} />
                  </div>
                  <TextareaField label="Description" value={entry.description ?? ""} rows={3} onChange={(value) => mutate((draft) => { draft.education[index].description = value || null; })} />
                </div>
              )) : <p className="text-sm text-muted-foreground">No education entries extracted.</p>}
            </CardContent> : null}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Languages</CardTitle>
                <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.languages.push({ id: newProfileBuilderId("language"), language: "", level: null }); })}><Plus />Add</Button>{sectionToggle("languages", "Languages")}</div></CardAction>
              </CardHeader>
              {sectionIsOpen("languages") ? <CardContent className="space-y-2">
                {profile.languages.map((entry, index) => (
                  <div key={entry.id} className="grid grid-cols-[1fr_0.7fr_auto] gap-2">
                    <Input aria-label={`Language ${index + 1}`} value={entry.language} placeholder="Language" onChange={(event) => mutate((draft) => { draft.languages[index].language = event.target.value; })} />
                    <Input aria-label={`Language ${index + 1} level`} value={entry.level ?? ""} placeholder="Level" onChange={(event) => mutate((draft) => { draft.languages[index].level = event.target.value || null; })} />
                    <Button variant="ghost" size="icon" aria-label="Remove language" onClick={() => mutate((draft) => { draft.languages.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                ))}
              </CardContent> : null}
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Certifications</CardTitle>
                <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.certifications.push({ id: newProfileBuilderId("certification"), name: "", issuer: null, date: null, url: null }); })}><Plus />Add</Button>{sectionToggle("certifications", "Certifications")}</div></CardAction>
              </CardHeader>
              {sectionIsOpen("certifications") ? <CardContent className="space-y-3">
                {profile.certifications.map((entry, index) => (
                  <div key={entry.id} className="space-y-2 rounded-lg border p-3">
                    <div className="grid grid-cols-[1fr_auto] gap-2"><Input aria-label={`Certification ${index + 1} name`} value={entry.name} placeholder="Certification" onChange={(event) => mutate((draft) => { draft.certifications[index].name = event.target.value; })} /><Button variant="ghost" size="icon" aria-label="Remove certification" onClick={() => mutate((draft) => { draft.certifications.splice(index, 1); })}><Trash2 /></Button></div>
                    <div className="grid grid-cols-2 gap-2"><Input aria-label={`Certification ${index + 1} issuer`} value={entry.issuer ?? ""} placeholder="Issuer" onChange={(event) => mutate((draft) => { draft.certifications[index].issuer = event.target.value || null; })} /><Input aria-label={`Certification ${index + 1} date`} value={entry.date ?? ""} placeholder="Date" onChange={(event) => mutate((draft) => { draft.certifications[index].date = event.target.value || null; })} /></div>
                    <Input aria-label={`Certification ${index + 1} URL`} value={entry.url ?? ""} placeholder="URL" onChange={(event) => mutate((draft) => { draft.certifications[index].url = event.target.value || null; })} />
                  </div>
                ))}
              </CardContent> : null}
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Additional sections</CardTitle>
              <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.additional_sections.push({ id: newProfileBuilderId("additional"), title: "New section", items: [] }); })}><Plus />Add</Button>{sectionToggle("additional", "Additional sections")}</div></CardAction>
            </CardHeader>
            {sectionIsOpen("additional") ? <CardContent className="space-y-3">
              {profile.additional_sections.map((section, index) => (
                <div key={section.id} className="space-y-2 rounded-lg border p-3">
                  <div className="grid grid-cols-[1fr_auto] gap-2"><Input aria-label={`Additional section ${index + 1} title`} value={section.title} onChange={(event) => mutate((draft) => { draft.additional_sections[index].title = event.target.value; })} /><Button variant="ghost" size="icon" aria-label="Remove section" onClick={() => mutate((draft) => { draft.additional_sections.splice(index, 1); })}><Trash2 /></Button></div>
                  <TextareaField label="Items" value={section.items.join("\n")} rows={4} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.additional_sections[index].items = nonEmptyLines(value); })} />
                </div>
              ))}
            </CardContent> : null}
          </Card>
        </div>

        <aside className="min-w-0 xl:sticky xl:top-20">
          <ProfileDocumentPreview
            profile={presentation}
            template={selectedTemplate}
            label="Anonymized A4 layout preview"
          />
        </aside>
      </div>
    </div>
  );
}
