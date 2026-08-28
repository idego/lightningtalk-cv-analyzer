"use client";

import { useId, useMemo, useState } from "react";
import {
  Download,
  FileText,
  LoaderCircle,
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
import { IDEGO_PRIMARY, IDEGO_SECONDARY } from "@/lib/idego";
import { useAppSettings } from "@/lib/app-settings";

const ACCEPT = ".pdf,.docx";

type ProfileLink = { label: string; url: string };
type CandidateProfile = {
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

type AnonymizationPolicy = {
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

type ExtractResponse = {
  filename: string;
  profile: CandidateProfile;
  warnings: string[];
};

const DEFAULT_ANONYMIZATION: AnonymizationPolicy = {
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

function newId(prefix: string) {
  return `${prefix}-${globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36)}`;
}

function nonEmptyLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function derivedPresentation(
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

function PreviewSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="border-b pb-1 text-xs font-semibold uppercase tracking-[0.16em] text-[#081932]">
        {title}
      </h3>
      {children}
    </section>
  );
}

export function ProfileBuilderWorkspace() {
  const settings = useAppSettings();
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [sourceFilename, setSourceFilename] = useState<string | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [anonymization, setAnonymization] = useState(DEFAULT_ANONYMIZATION);
  const [extracting, setExtracting] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const presentation = useMemo(
    () => (profile ? derivedPresentation(profile, anonymization) : null),
    [profile, anonymization],
  );

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
      setProfile(payload.profile);
      setSourceFilename(payload.filename ?? file.name);
      setAnonymization(DEFAULT_ANONYMIZATION);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Profile extraction failed.");
    } finally {
      setExtracting(false);
    }
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
          template_id: "idego-default",
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
    setProfile(null);
    setSourceFilename(null);
    setSourceFile(null);
    setAnonymization(DEFAULT_ANONYMIZATION);
    setError(null);
  }

  if (!profile || !presentation) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">Profile Builder</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Turn a candidate CV into an editable IDEGO profile. Extract first, correct anything that needs correction, then export the exact current version to DOCX.
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
      </div>
    );
  }

  const fullName = [presentation.personal.first_name, presentation.personal.last_name]
    .filter(Boolean)
    .join(" ");
  const contacts = [
    presentation.personal.email,
    presentation.personal.phone,
    presentation.personal.location,
    presentation.personal.links.linkedin,
    presentation.personal.links.github,
    presentation.personal.links.portfolio,
    ...presentation.personal.links.other.map((link) =>
      link.label ? `${link.label}: ${link.url}` : link.url,
    ),
  ].filter(Boolean);

  return (
    <div className="mx-auto w-full max-w-[1800px] space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{sourceFilename ?? "Candidate profile"}</p>
          <p className="text-xs text-muted-foreground">Template: IDEGO Default · session-only prototype</p>
        </div>
        <Button variant="outline" onClick={reset}>
          <RotateCcw data-icon="inline-start" />New CV
        </Button>
        <Button onClick={() => void exportDocx()} disabled={exporting}>
          {exporting ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Download data-icon="inline-start" />}
          {exporting ? "Exporting…" : "Export DOCX"}
        </Button>
      </div>
      {error ? <p className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Personal information</CardTitle>
              <CardDescription>Canonical values. Anonymization below only changes preview/export.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
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
            </CardContent>
          </Card>

          <Card>
            <CardHeader><CardTitle>Profile</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <Field label="Headline" value={profile.headline} onChange={(value) => mutate((draft) => { draft.headline = value; })} />
              <TextareaField label="Summary" value={profile.summary ?? ""} rows={5} onChange={(value) => mutate((draft) => { draft.summary = value || null; })} />
              <div className="grid gap-3 sm:grid-cols-2">
                <TextareaField label="Skills" value={profile.skills.join("\n")} rows={5} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.skills = nonEmptyLines(value); })} />
                <TextareaField label="Technologies" value={profile.technologies.join("\n")} rows={5} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.technologies = nonEmptyLines(value); })} />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Anonymization</CardTitle>
              <CardDescription>Derived output policy. These switches never delete canonical profile data.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
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
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Experience</CardTitle>
              <CardAction><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.experience.push({ id: newId("experience"), company: null, company_category: null, role: null, project: null, location: null, start_date: null, end_date: null, current: false, responsibilities: [], achievements: [], technologies: [] }); })}><Plus />Add</Button></CardAction>
            </CardHeader>
            <CardContent className="space-y-3">
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
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Education</CardTitle>
              <CardAction><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.education.push({ id: newId("education"), institution: null, degree: null, field: null, start_date: null, end_date: null, location: null, description: null }); })}><Plus />Add</Button></CardAction>
            </CardHeader>
            <CardContent className="space-y-3">
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
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Languages</CardTitle>
                <CardAction><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.languages.push({ id: newId("language"), language: "", level: null }); })}><Plus />Add</Button></CardAction>
              </CardHeader>
              <CardContent className="space-y-2">
                {profile.languages.map((entry, index) => (
                  <div key={entry.id} className="grid grid-cols-[1fr_0.7fr_auto] gap-2">
                    <Input aria-label={`Language ${index + 1}`} value={entry.language} placeholder="Language" onChange={(event) => mutate((draft) => { draft.languages[index].language = event.target.value; })} />
                    <Input aria-label={`Language ${index + 1} level`} value={entry.level ?? ""} placeholder="Level" onChange={(event) => mutate((draft) => { draft.languages[index].level = event.target.value || null; })} />
                    <Button variant="ghost" size="icon" aria-label="Remove language" onClick={() => mutate((draft) => { draft.languages.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Certifications</CardTitle>
                <CardAction><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.certifications.push({ id: newId("certification"), name: "", issuer: null, date: null, url: null }); })}><Plus />Add</Button></CardAction>
              </CardHeader>
              <CardContent className="space-y-3">
                {profile.certifications.map((entry, index) => (
                  <div key={entry.id} className="space-y-2 rounded-lg border p-3">
                    <div className="grid grid-cols-[1fr_auto] gap-2"><Input aria-label={`Certification ${index + 1} name`} value={entry.name} placeholder="Certification" onChange={(event) => mutate((draft) => { draft.certifications[index].name = event.target.value; })} /><Button variant="ghost" size="icon" aria-label="Remove certification" onClick={() => mutate((draft) => { draft.certifications.splice(index, 1); })}><Trash2 /></Button></div>
                    <div className="grid grid-cols-2 gap-2"><Input aria-label={`Certification ${index + 1} issuer`} value={entry.issuer ?? ""} placeholder="Issuer" onChange={(event) => mutate((draft) => { draft.certifications[index].issuer = event.target.value || null; })} /><Input aria-label={`Certification ${index + 1} date`} value={entry.date ?? ""} placeholder="Date" onChange={(event) => mutate((draft) => { draft.certifications[index].date = event.target.value || null; })} /></div>
                    <Input aria-label={`Certification ${index + 1} URL`} value={entry.url ?? ""} placeholder="URL" onChange={(event) => mutate((draft) => { draft.certifications[index].url = event.target.value || null; })} />
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Additional sections</CardTitle>
              <CardAction><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.additional_sections.push({ id: newId("additional"), title: "New section", items: [] }); })}><Plus />Add</Button></CardAction>
            </CardHeader>
            <CardContent className="space-y-3">
              {profile.additional_sections.map((section, index) => (
                <div key={section.id} className="space-y-2 rounded-lg border p-3">
                  <div className="grid grid-cols-[1fr_auto] gap-2"><Input aria-label={`Additional section ${index + 1} title`} value={section.title} onChange={(event) => mutate((draft) => { draft.additional_sections[index].title = event.target.value; })} /><Button variant="ghost" size="icon" aria-label="Remove section" onClick={() => mutate((draft) => { draft.additional_sections.splice(index, 1); })}><Trash2 /></Button></div>
                  <TextareaField label="Items" value={section.items.join("\n")} rows={4} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.additional_sections[index].items = nonEmptyLines(value); })} />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <aside className="min-w-0 xl:sticky xl:top-20">
          <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck className="size-4" />Live preview uses the exact current editor state
          </div>
          <div className="mx-auto min-h-[780px] max-w-[760px] bg-white px-10 py-9 text-[#081932] shadow-sm ring-1 ring-black/10 dark:text-[#081932]">
            <div className="mb-9 flex items-center justify-between gap-4 border-b-2 pb-4" style={{ borderColor: IDEGO_SECONDARY }}>
              <div>
                <p className="text-3xl font-semibold tracking-tight">{fullName || "Candidate Profile"}</p>
                {presentation.headline ? <p className="mt-1 text-base text-slate-600">{presentation.headline}</p> : null}
              </div>
              <div className="text-right">
                <p className="text-lg font-bold tracking-[0.16em]" style={{ color: IDEGO_PRIMARY }}>IDEGO</p>
                <p className="text-[10px] uppercase tracking-[0.18em] text-slate-400">Candidate Profile</p>
              </div>
            </div>

            <div className="space-y-7 text-[13px] leading-relaxed text-slate-700">
              {contacts.length ? <p className="text-xs text-slate-500">{contacts.join(" · ")}</p> : null}
              {presentation.summary ? <PreviewSection title="Summary"><p className="whitespace-pre-wrap">{presentation.summary}</p></PreviewSection> : null}
              {presentation.skills.length ? <PreviewSection title="Skills"><p>{presentation.skills.join(", ")}</p></PreviewSection> : null}
              {presentation.technologies.length ? <PreviewSection title="Technologies"><p>{presentation.technologies.join(", ")}</p></PreviewSection> : null}
              {presentation.experience.length ? (
                <PreviewSection title="Experience">
                  <div className="space-y-5">
                    {presentation.experience.map((entry) => (
                      <div key={entry.id} className="space-y-1.5">
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
                    ))}
                  </div>
                </PreviewSection>
              ) : null}
              {presentation.education.length ? (
                <PreviewSection title="Education">
                  <div className="space-y-4">
                    {presentation.education.map((entry) => (
                      <div key={entry.id}>
                        <p className="font-semibold text-slate-900">{[entry.degree, entry.field, entry.institution].filter(Boolean).join(" — ") || "Education"}</p>
                        <p className="text-xs text-slate-500">{[
                          entry.start_date && entry.end_date ? `${entry.start_date} – ${entry.end_date}` : entry.start_date || entry.end_date,
                          entry.location,
                        ].filter(Boolean).join(" · ")}</p>
                        {entry.description ? <p className="mt-1 whitespace-pre-wrap">{entry.description}</p> : null}
                      </div>
                    ))}
                  </div>
                </PreviewSection>
              ) : null}
              {presentation.languages.length ? <PreviewSection title="Languages"><p>{presentation.languages.map((entry) => [entry.language, entry.level].filter(Boolean).join(" — ")).join(" · ")}</p></PreviewSection> : null}
              {presentation.certifications.length ? <PreviewSection title="Certifications"><ul className="list-disc pl-5">{presentation.certifications.map((entry) => <li key={entry.id}>{[entry.name, entry.issuer, entry.date, entry.url].filter(Boolean).join(" — ")}</li>)}</ul></PreviewSection> : null}
              {presentation.additional_sections.map((section) => section.items.length ? <PreviewSection key={section.id} title={section.title}><ul className="list-disc pl-5">{section.items.map((item, index) => <li key={`${section.id}-${index}`}>{item}</li>)}</ul></PreviewSection> : null)}
            </div>
            <div className="mt-10 border-t pt-3 text-center text-[10px] text-slate-400">
              <FileText className="mr-1 inline size-3" />IDEGO Candidate Profile
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
