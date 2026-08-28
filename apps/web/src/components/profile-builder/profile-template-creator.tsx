"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowDown,
  ArrowLeft,
  ArrowUp,
  Eye,
  EyeOff,
  LayoutTemplate,
  LoaderCircle,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DEFAULT_PROFILE_TEMPLATE,
  PROFILE_TEMPLATE_SAMPLE_PROFILE,
  ProfileDocumentPreview,
  SELECTED_TEMPLATE_STORAGE_KEY,
  type AnonymizationPolicy,
  type CandidateProfile,
  type ProfileTemplate,
  type ProfileTemplateSection,
  type TemplateSectionKind,
} from "@/components/profile-builder/profile-builder-workspace";

const SECTION_DEFAULTS: Record<TemplateSectionKind, Pick<ProfileTemplateSection, "title" | "layout">> = {
  summary: { title: "Summary", layout: "default" },
  skills: { title: "Skills", layout: "inline" },
  technologies: { title: "Technologies", layout: "inline" },
  experience: { title: "Experience", layout: "default" },
  education: { title: "Education", layout: "default" },
  languages: { title: "Languages", layout: "inline" },
  certifications: { title: "Certifications", layout: "bullets" },
  additional_sections: { title: "Additional", layout: "bullets" },
};

const SECTION_ORDER = Object.keys(SECTION_DEFAULTS) as TemplateSectionKind[];
const SIMPLE_LIST_KINDS = new Set<TemplateSectionKind>([
  "skills",
  "technologies",
  "languages",
  "certifications",
]);

function initialNewTemplate(): ProfileTemplate {
  const next = structuredClone(DEFAULT_PROFILE_TEMPLATE);
  next.id = "new";
  next.name = "Untitled template";
  next.description = "Custom candidate profile template.";
  return next;
}

function creatorTemplateId() {
  return `template-${globalThis.crypto.randomUUID()}`;
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
      <span className="min-w-0">
        <span className="block text-sm font-medium">{label}</span>
        {description ? <span className="mt-0.5 block text-xs text-muted-foreground">{description}</span> : null}
      </span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 shrink-0 accent-[var(--primary)]"
      />
    </label>
  );
}

export function ProfileTemplateCreator({ templateId, returnProfileId }: { templateId: string | null; returnProfileId?: string | null }) {
  const router = useRouter();
  const isNew = templateId === null;
  const [template, setTemplate] = useState<ProfileTemplate>(() => initialNewTemplate());
  const [selectedSectionId, setSelectedSectionId] = useState<string>("summary");
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNew || !templateId) return;
    const timer = window.setTimeout(() => {
      void (async () => {
        setLoading(true);
        setError(null);
        try {
          const response = await fetch(`/api/profile-builder/templates/${encodeURIComponent(templateId)}`, {
            cache: "no-store",
          });
          if (!response.ok) throw new Error("template_unavailable");
          const body = await response.json() as { template?: ProfileTemplate };
          if (!body.template) throw new Error("template_unavailable");
          setTemplate(body.template);
          setSelectedSectionId(body.template.sections[0]?.id ?? "");
        } catch {
          setError("This template could not be loaded.");
        } finally {
          setLoading(false);
        }
      })();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isNew, templateId]);

  const selectedIndex = template.sections.findIndex((section) => section.id === selectedSectionId);
  const selectedSection = selectedIndex >= 0 ? template.sections[selectedIndex] : null;
  const missingKinds = useMemo(() => {
    const present = new Set(template.sections.map((section) => section.kind));
    return SECTION_ORDER.filter((kind) => !present.has(kind));
  }, [template.sections]);

  function mutate(mutator: (draft: ProfileTemplate) => void) {
    setTemplate((current) => {
      const draft = structuredClone(current);
      mutator(draft);
      return draft;
    });
  }

  function updateSelectedSection(mutator: (section: ProfileTemplateSection) => void) {
    if (selectedIndex < 0) return;
    mutate((draft) => mutator(draft.sections[selectedIndex]));
  }

  function moveSection(direction: -1 | 1) {
    if (selectedIndex < 0) return;
    const target = selectedIndex + direction;
    if (target < 0 || target >= template.sections.length) return;
    mutate((draft) => {
      const [section] = draft.sections.splice(selectedIndex, 1);
      draft.sections.splice(target, 0, section);
    });
  }

  function removeSection() {
    if (selectedIndex < 0 || template.sections.length <= 1) return;
    const nextSelection = template.sections[selectedIndex - 1] ?? template.sections[selectedIndex + 1];
    mutate((draft) => {
      draft.sections.splice(selectedIndex, 1);
    });
    setSelectedSectionId(nextSelection?.id ?? "");
  }

  function addSection(kind: TemplateSectionKind) {
    const defaults = SECTION_DEFAULTS[kind];
    const section: ProfileTemplateSection = {
      id: `${kind}-${globalThis.crypto.randomUUID()}`,
      kind,
      title: defaults.title,
      visible: true,
      layout: defaults.layout,
    };
    mutate((draft) => {
      draft.sections.push(section);
    });
    setSelectedSectionId(section.id);
  }

  async function saveTemplate() {
    const trimmedName = template.name.trim();
    if (!trimmedName) {
      setError("Template name is required.");
      return;
    }
    if (!template.sections.length) {
      setError("Keep at least one profile block.");
      return;
    }
    if (!template.branding.brand_name.trim()) {
      setError("Brand label is required, even when brand display is hidden.");
      return;
    }
    if (template.sections.some((section) => !section.title.trim())) {
      setError("Every profile block needs a heading.");
      return;
    }
    if (!/^#[0-9A-Fa-f]{6}$/.test(template.branding.accent_hex)) {
      setError("Accent color must be a six-digit hex value, for example #3CC2D9.");
      return;
    }
    if (template.typography.body_size < 8 || template.typography.body_size > 14) {
      setError("Body size must be between 8 and 14 pt.");
      return;
    }
    if (template.typography.heading_size < 10 || template.typography.heading_size > 22) {
      setError("Heading size must be between 10 and 22 pt.");
      return;
    }

    const payload = structuredClone(template);
    payload.name = trimmedName;
    if (isNew || payload.id === "new") payload.id = creatorTemplateId();

    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`/api/profile-builder/templates/${encodeURIComponent(payload.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw new Error("template_save_failed");

      if (returnProfileId) {
        const profileResponse = await fetch(`/api/profile-builder/profiles/${encodeURIComponent(returnProfileId)}`, { cache: "no-store" });
        if (!profileResponse.ok) {
          setError("Template saved, but the current profile could not be reopened.");
          setSaving(false);
          return;
        }
        const stored = await profileResponse.json() as {
          source_filename: string;
          profile: CandidateProfile;
          anonymization: AnonymizationPolicy;
        };
        const update = await fetch(`/api/profile-builder/profiles/${encodeURIComponent(returnProfileId)}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_filename: stored.source_filename,
            profile: stored.profile,
            anonymization: stored.anonymization,
            template: payload,
          }),
        });
        if (!update.ok) {
          setError("Template saved, but the current profile could not be updated.");
          setSaving(false);
          return;
        }
      }

      window.localStorage.setItem(SELECTED_TEMPLATE_STORAGE_KEY, payload.id);
      router.push(returnProfileId ? `/profile-builder?profile=${encodeURIComponent(returnProfileId)}` : "/profile-builder");
    } catch {
      setError("The template could not be saved.");
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="flex min-h-[60vh] items-center justify-center"><LoaderCircle className="size-7 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="mx-auto w-full max-w-[1900px] space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-3">
        <Button
          variant="ghost"
          onClick={() => router.push(returnProfileId ? `/profile-builder?profile=${encodeURIComponent(returnProfileId)}` : "/profile-builder")}
        >
          <ArrowLeft />Back
        </Button>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{isNew ? "Create template" : `Edit ${template.name}`}</p>
          <p className="text-xs text-muted-foreground">Constrained blocks keep the layout predictable in editable DOCX.</p>
        </div>
        <Button onClick={() => void saveTemplate()} disabled={saving}>
          {saving ? <LoaderCircle className="animate-spin" /> : <Save />}
          {saving ? "Saving…" : "Save and use"}
        </Button>
      </div>

      {error ? <p className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p> : null}

      <div className="grid items-start gap-4 xl:grid-cols-[300px_minmax(420px,1fr)_340px]">
        <div className="space-y-4 xl:sticky xl:top-20">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><LayoutTemplate className="size-4" />Blocks</CardTitle>
              <CardDescription>Click a block to edit it. Use arrows to control document flow.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {template.sections.map((section, index) => {
                const selected = section.id === selectedSectionId;
                return (
                  <button
                    key={section.id}
                    type="button"
                    onClick={() => setSelectedSectionId(section.id)}
                    className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring ${selected ? "border-primary/40 bg-primary/5" : "hover:bg-muted/50"}`}
                  >
                    <span className="flex size-6 shrink-0 items-center justify-center rounded-md bg-muted text-xs font-medium">{index + 1}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium">{section.title}</span>
                      <span className="block truncate text-xs text-muted-foreground">{section.kind.replaceAll("_", " ")}</span>
                    </span>
                    {section.visible ? <Eye className="size-3.5 shrink-0 text-muted-foreground" /> : <EyeOff className="size-3.5 shrink-0 text-muted-foreground" />}
                  </button>
                );
              })}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Add block</CardTitle>
              <CardDescription>Only one of each domain block is allowed in V1.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1">
              {missingKinds.length ? missingKinds.map((kind) => (
                <Button key={kind} variant="outline" className="justify-start" onClick={() => addSection(kind)}>
                  <Plus />{SECTION_DEFAULTS[kind].title}
                </Button>
              )) : <p className="text-sm text-muted-foreground">All available blocks are already in this template.</p>}
            </CardContent>
          </Card>
        </div>

        <ProfileDocumentPreview
          profile={PROFILE_TEMPLATE_SAMPLE_PROFILE}
          template={template}
          label="Template Creator preview"
        />

        <div className="space-y-4 xl:sticky xl:top-20">
          <Card>
            <CardHeader>
              <CardTitle>Template</CardTitle>
              <CardDescription>Brand and document-wide typography.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="template-name">Name</Label>
                <Input id="template-name" maxLength={120} value={template.name} onChange={(event) => mutate((draft) => { draft.name = event.target.value; })} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="template-description">Description</Label>
                <textarea id="template-description" rows={3} maxLength={300} value={template.description ?? ""} onChange={(event) => mutate((draft) => { draft.description = event.target.value || null; })} className="w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="template-brand-name">Brand label</Label>
                <Input id="template-brand-name" maxLength={80} value={template.branding.brand_name} onChange={(event) => mutate((draft) => { draft.branding.brand_name = event.target.value; })} />
              </div>
              <div className="grid grid-cols-[72px_1fr] gap-2">
                <input aria-label="Accent color" type="color" value={template.branding.accent_hex} onChange={(event) => mutate((draft) => { draft.branding.accent_hex = event.target.value.toUpperCase(); })} className="h-8 w-full cursor-pointer rounded-lg border bg-transparent p-1" />
                <Input aria-label="Accent hex color" value={template.branding.accent_hex} onChange={(event) => {
                  const value = event.target.value.toUpperCase();
                  if (/^#[0-9A-F]{0,6}$/.test(value)) mutate((draft) => { draft.branding.accent_hex = value; });
                }} />
              </div>
              <ToggleRow label="Show brand" checked={template.branding.show_brand} onChange={(checked) => mutate((draft) => { draft.branding.show_brand = checked; })} />
              <div className="space-y-1.5">
                <Label htmlFor="template-font">Font family</Label>
                <select id="template-font" value={template.typography.font_family} onChange={(event) => mutate((draft) => { draft.typography.font_family = event.target.value as ProfileTemplate["typography"]["font_family"]; })} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                  <option value="Aptos">Aptos</option>
                  <option value="Arial">Arial</option>
                  <option value="Calibri">Calibri</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1.5">
                  <Label htmlFor="template-body-size">Body size</Label>
                  <Input id="template-body-size" type="number" min={8} max={14} step={0.5} value={template.typography.body_size} onChange={(event) => mutate((draft) => { draft.typography.body_size = Number(event.target.value); })} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="template-heading-size">Heading size</Label>
                  <Input id="template-heading-size" type="number" min={10} max={22} step={0.5} value={template.typography.heading_size} onChange={(event) => mutate((draft) => { draft.typography.heading_size = Number(event.target.value); })} />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Header</CardTitle>
              <CardDescription>Choose which candidate-level fields lead the document.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <ToggleRow label="Candidate name" checked={template.header.show_name} onChange={(checked) => mutate((draft) => { draft.header.show_name = checked; })} />
              <ToggleRow label="Headline" checked={template.header.show_headline} onChange={(checked) => mutate((draft) => { draft.header.show_headline = checked; })} />
              <ToggleRow label="Contact line" checked={template.header.show_contact} onChange={(checked) => mutate((draft) => { draft.header.show_contact = checked; })} />
            </CardContent>
          </Card>

          {selectedSection ? (
            <Card>
              <CardHeader>
                <CardTitle>Selected block</CardTitle>
                <CardDescription>{selectedSection.kind.replaceAll("_", " ")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1.5">
                  <Label htmlFor="section-title">Heading</Label>
                  <Input id="section-title" maxLength={80} value={selectedSection.title} onChange={(event) => updateSelectedSection((section) => { section.title = event.target.value; })} />
                </div>
                <ToggleRow label="Visible" checked={selectedSection.visible} onChange={(checked) => updateSelectedSection((section) => { section.visible = checked; })} />
                {SIMPLE_LIST_KINDS.has(selectedSection.kind) ? (
                  <div className="space-y-1.5">
                    <Label htmlFor="section-layout">List layout</Label>
                    <select id="section-layout" value={selectedSection.layout} onChange={(event) => updateSelectedSection((section) => { section.layout = event.target.value as ProfileTemplateSection["layout"]; })} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                      <option value="inline">Inline</option>
                      <option value="bullets">Bullets</option>
                    </select>
                  </div>
                ) : null}
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="outline" disabled={selectedIndex <= 0} onClick={() => moveSection(-1)}><ArrowUp />Move up</Button>
                  <Button variant="outline" disabled={selectedIndex < 0 || selectedIndex >= template.sections.length - 1} onClick={() => moveSection(1)}><ArrowDown />Move down</Button>
                </div>
                <Button variant="destructive" className="w-full" disabled={template.sections.length <= 1} onClick={removeSection}><Trash2 />Remove block</Button>
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}
