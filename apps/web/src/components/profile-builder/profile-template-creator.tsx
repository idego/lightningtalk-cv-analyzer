"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Eye,
  EyeOff,
  GripVertical,
  ImagePlus,
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
  type ProfileTemplateLogo,
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
const MAX_LOGO_BYTES = 4 * 1024 * 1024;
const MAX_LOGO_SIDE = 1200;

type InspectorTab = "template" | "header" | "block" | "logo";

function initialNewTemplate(): ProfileTemplate {
  const next = structuredClone(DEFAULT_PROFILE_TEMPLATE);
  next.id = "new";
  next.name = "Untitled template";
  next.description = "Custom candidate profile template.";
  next.logo = null;
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
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-1.5">
      <span className="min-w-0">
        <span className="block text-xs font-medium">{label}</span>
        {description ? <span className="mt-0.5 block text-[11px] leading-tight text-muted-foreground">{description}</span> : null}
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

function sanitizeSvg(source: string) {
  if (/@import|url\s*\(\s*["']?https?:/i.test(source)) {
    throw new Error("SVG logos cannot reference external network resources.");
  }
  const document = new DOMParser().parseFromString(source, "image/svg+xml");
  if (document.querySelector("parsererror")) throw new Error("The SVG could not be parsed.");
  document.querySelectorAll("script, foreignObject").forEach((node) => node.remove());
  for (const element of Array.from(document.querySelectorAll("*"))) {
    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim();
      if (name.startsWith("on")) element.removeAttribute(attribute.name);
      if ((name === "href" || name === "xlink:href") && value && !value.startsWith("#") && !value.startsWith("data:")) {
        element.removeAttribute(attribute.name);
      }
      if (name === "style" && /url\s*\(\s*["']?https?:/i.test(value)) {
        element.removeAttribute(attribute.name);
      }
    }
  }
  return new XMLSerializer().serializeToString(document.documentElement);
}

async function imageFromUrl(url: string) {
  const image = new window.Image();
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("The image could not be decoded."));
    image.src = url;
  });
  return image;
}

async function normalizeLogoFile(file: File): Promise<ProfileTemplateLogo> {
  if (file.size > MAX_LOGO_BYTES) throw new Error("Logo files must be 4 MB or smaller.");
  const extension = file.name.toLowerCase().split(".").pop() ?? "";
  const inferredType = file.type || ({ png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", svg: "image/svg+xml" }[extension] ?? "");
  const supported = new Set(["image/png", "image/jpeg", "image/webp", "image/svg+xml"]);
  if (!supported.has(inferredType)) throw new Error("Use PNG, JPG, WebP, or SVG for the logo.");

  let objectUrl: string | null = null;
  try {
    if (inferredType === "image/svg+xml") {
      const safeSvg = sanitizeSvg(await file.text());
      objectUrl = URL.createObjectURL(new Blob([safeSvg], { type: "image/svg+xml" }));
    } else {
      objectUrl = URL.createObjectURL(file);
    }
    const image = await imageFromUrl(objectUrl);
    const sourceWidth = image.naturalWidth || 300;
    const sourceHeight = image.naturalHeight || 150;
    const scale = Math.min(1, MAX_LOGO_SIDE / Math.max(sourceWidth, sourceHeight));
    const width = Math.max(1, Math.round(sourceWidth * scale));
    const height = Math.max(1, Math.round(sourceHeight * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Logo conversion is unavailable in this browser.");
    context.clearRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    const dataUrl = canvas.toDataURL("image/png");
    if (dataUrl.length > 5_500_000) throw new Error("The converted logo is still too large. Use a smaller image.");
    return {
      data_url: dataUrl,
      original_name: file.name,
      x_pct: 72,
      y_pct: 4,
      width_pct: 18,
      aspect_ratio: width / height,
    };
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}

export function ProfileTemplateCreator({ templateId, returnProfileId }: { templateId: string | null; returnProfileId?: string | null }) {
  const router = useRouter();
  const isNew = templateId === null;
  const [template, setTemplate] = useState<ProfileTemplate>(() => initialNewTemplate());
  const [selectedSectionId, setSelectedSectionId] = useState<string>("summary");
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("template");
  const [draggedSectionId, setDraggedSectionId] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(!isNew);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);

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
          setDirty(false);
        } catch {
          setError("This template could not be loaded.");
        } finally {
          setLoading(false);
        }
      })();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [isNew, templateId]);

  useEffect(() => {
    if (!dirty) return;
    const preventUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [dirty]);

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
    setDirty(true);
  }

  function updateSelectedSection(mutator: (section: ProfileTemplateSection) => void) {
    if (selectedIndex < 0) return;
    mutate((draft) => mutator(draft.sections[selectedIndex]));
  }

  function reorderSection(activeId: string, targetId: string) {
    if (activeId === targetId) return;
    mutate((draft) => {
      const from = draft.sections.findIndex((section) => section.id === activeId);
      const to = draft.sections.findIndex((section) => section.id === targetId);
      if (from < 0 || to < 0) return;
      const [section] = draft.sections.splice(from, 1);
      draft.sections.splice(to, 0, section);
    });
    setSelectedSectionId(activeId);
  }

  function toggleSectionVisibility(sectionId: string) {
    mutate((draft) => {
      const section = draft.sections.find((item) => item.id === sectionId);
      if (section) section.visible = !section.visible;
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
    setInspectorTab("block");
  }

  function leaveCreator() {
    if (dirty && !window.confirm("Discard unsaved template changes?")) return;
    router.push(returnProfileId ? `/profile-builder?profile=${encodeURIComponent(returnProfileId)}` : "/profile-builder");
  }

  async function chooseLogo(file: File) {
    setError(null);
    try {
      const logo = await normalizeLogoFile(file);
      mutate((draft) => { draft.logo = logo; });
      setInspectorTab("logo");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The logo could not be loaded.");
    } finally {
      if (logoInputRef.current) logoInputRef.current.value = "";
    }
  }

  function updateLogo(nextLogo: ProfileTemplateLogo) {
    mutate((draft) => { draft.logo = nextLogo; });
  }

  function resizeLogo(widthPct: number) {
    if (!template.logo) return;
    const width = Math.min(60, Math.max(2, widthPct));
    mutate((draft) => {
      if (!draft.logo) return;
      draft.logo.width_pct = width;
      draft.logo.x_pct = Math.min(draft.logo.x_pct, 100 - width);
      const heightPct = width * (210 / 297) / draft.logo.aspect_ratio;
      draft.logo.y_pct = Math.min(draft.logo.y_pct, Math.max(0, 100 - heightPct));
    });
  }

  async function saveTemplate() {
    const trimmedName = template.name.trim();
    if (!trimmedName) return setError("Template name is required.");
    if (!template.sections.length) return setError("Keep at least one profile block.");
    if (!template.branding.brand_name.trim()) return setError("Brand label is required, even when brand display is hidden.");
    if (template.sections.some((section) => !section.title.trim())) return setError("Every profile block needs a heading.");
    if (!/^#[0-9A-Fa-f]{6}$/.test(template.branding.accent_hex)) return setError("Accent color must be a six-digit hex value, for example #3CC2D9.");
    if (template.typography.body_size < 8 || template.typography.body_size > 14) return setError("Body size must be between 8 and 14 pt.");
    if (template.typography.heading_size < 10 || template.typography.heading_size > 22) return setError("Heading size must be between 10 and 22 pt.");

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

      setDirty(false);
      window.localStorage.setItem(SELECTED_TEMPLATE_STORAGE_KEY, payload.id);
      router.push(returnProfileId ? `/profile-builder?profile=${encodeURIComponent(returnProfileId)}` : "/profile-builder");
    } catch {
      setError("The template could not be saved.");
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="flex h-full min-h-0 items-center justify-center"><LoaderCircle className="size-7 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="flex h-full min-h-0 w-full flex-col gap-3 overflow-hidden">
      <div className="flex h-12 shrink-0 items-center gap-3 rounded-xl border bg-card px-3">
        <Button variant="ghost" size="sm" onClick={leaveCreator}><ArrowLeft />Back</Button>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{isNew ? "Create template" : `Edit ${template.name}`}{dirty ? " · Unsaved" : ""}</p>
          <p className="truncate text-[11px] text-muted-foreground">Drag blocks to reorder. Drag the uploaded logo directly on the page.</p>
        </div>
        {error ? <p className="max-w-[34%] truncate text-xs text-destructive" title={error}>{error}</p> : null}
        <Button size="sm" onClick={() => void saveTemplate()} disabled={saving}>
          {saving ? <LoaderCircle className="animate-spin" /> : <Save />}
          {saving ? "Saving…" : "Save and use"}
        </Button>
      </div>

      <div className="grid min-h-0 flex-1 gap-3 xl:grid-cols-[280px_minmax(380px,1fr)_330px]">
        <Card className="min-h-0 overflow-hidden">
          <CardHeader className="shrink-0 py-3">
            <CardTitle className="flex items-center gap-2 text-sm"><LayoutTemplate className="size-4" />Blocks</CardTitle>
            <CardDescription className="text-[11px]">Drag to reorder. Click the eye to hide or show.</CardDescription>
          </CardHeader>
          <CardContent className="flex h-[calc(100%-4.75rem)] min-h-0 flex-col gap-1.5 pb-3">
            <div className="min-h-0 flex-1 space-y-1.5">
              {template.sections.map((section, index) => {
                const selected = section.id === selectedSectionId;
                return (
                  <div
                    key={section.id}
                    draggable
                    onDragStart={(event) => {
                      setDraggedSectionId(section.id);
                      event.dataTransfer.effectAllowed = "move";
                      event.dataTransfer.setData("text/plain", section.id);
                    }}
                    onDragEnd={() => setDraggedSectionId(null)}
                    onDragOver={(event) => {
                      event.preventDefault();
                      event.dataTransfer.dropEffect = "move";
                    }}
                    onDrop={(event) => {
                      event.preventDefault();
                      const activeId = draggedSectionId || event.dataTransfer.getData("text/plain");
                      if (activeId) reorderSection(activeId, section.id);
                      setDraggedSectionId(null);
                    }}
                    className={`flex h-10 items-center gap-1 rounded-lg border px-1.5 transition-colors ${selected ? "border-primary/40 bg-primary/5" : "hover:bg-muted/50"} ${draggedSectionId === section.id ? "opacity-50" : ""}`}
                  >
                    <GripVertical className="size-4 shrink-0 cursor-grab text-muted-foreground active:cursor-grabbing" />
                    <button
                      type="button"
                      onClick={() => { setSelectedSectionId(section.id); setInspectorTab("block"); }}
                      className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-1 text-left outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span className="flex size-5 shrink-0 items-center justify-center rounded bg-muted text-[10px] font-medium">{index + 1}</span>
                      <span className="min-w-0 flex-1 truncate text-xs font-medium">{section.title}</span>
                    </button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="size-7 shrink-0"
                      aria-label={`${section.visible ? "Hide" : "Show"} ${section.title}`}
                      onClick={() => toggleSectionVisibility(section.id)}
                    >
                      {section.visible ? <Eye className="size-3.5" /> : <EyeOff className="size-3.5 text-muted-foreground" />}
                    </Button>
                  </div>
                );
              })}
            </div>
            <div className="grid shrink-0 grid-cols-[1fr_auto] gap-2 border-t pt-2">
              <select
                aria-label="Add block"
                value=""
                disabled={!missingKinds.length}
                onChange={(event) => {
                  if (event.target.value) addSection(event.target.value as TemplateSectionKind);
                }}
                className="h-8 min-w-0 rounded-lg border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="">{missingKinds.length ? "Add block…" : "All blocks added"}</option>
                {missingKinds.map((kind) => <option key={kind} value={kind}>{SECTION_DEFAULTS[kind].title}</option>)}
              </select>
              <Button variant="outline" size="icon-sm" disabled={!missingKinds.length} aria-label="Add first available block" onClick={() => missingKinds[0] && addSection(missingKinds[0])}><Plus /></Button>
            </div>
          </CardContent>
        </Card>

        <div className="min-h-0 overflow-hidden rounded-xl border bg-muted/10 p-2">
          <ProfileDocumentPreview
            profile={PROFILE_TEMPLATE_SAMPLE_PROFILE}
            template={template}
            label="Template preview"
            fillHeight
            logoEditable
            onLogoSelect={() => setInspectorTab("logo")}
            onLogoChange={updateLogo}
          />
        </div>

        <Card className="min-h-0 overflow-hidden">
          <CardHeader className="shrink-0 py-3">
            <CardTitle className="text-sm">Properties</CardTitle>
            <div className="grid grid-cols-4 gap-1 rounded-lg bg-muted p-1">
              {(["template", "header", "block", "logo"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setInspectorTab(tab)}
                  className={`rounded-md px-1.5 py-1.5 text-[11px] font-medium capitalize ${inspectorTab === tab ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </CardHeader>
          <CardContent className="h-[calc(100%-5.75rem)] min-h-0 pb-3">
            {inspectorTab === "template" ? (
              <div className="space-y-2">
                <div className="space-y-1"><Label htmlFor="template-name" className="text-xs">Name</Label><Input id="template-name" maxLength={120} value={template.name} onChange={(event) => mutate((draft) => { draft.name = event.target.value; })} /></div>
                <div className="space-y-1"><Label htmlFor="template-description" className="text-xs">Description</Label><textarea id="template-description" rows={1} maxLength={300} value={template.description ?? ""} onChange={(event) => mutate((draft) => { draft.description = event.target.value || null; })} className="h-8 w-full resize-none rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring" /></div>
                <div className="space-y-1"><Label htmlFor="template-brand-name" className="text-xs">Brand label</Label><Input id="template-brand-name" maxLength={80} value={template.branding.brand_name} onChange={(event) => mutate((draft) => { draft.branding.brand_name = event.target.value; })} /></div>
                <div className="grid grid-cols-[58px_1fr] gap-2"><input aria-label="Accent color" type="color" value={template.branding.accent_hex} onChange={(event) => mutate((draft) => { draft.branding.accent_hex = event.target.value.toUpperCase(); })} className="h-8 w-full cursor-pointer rounded-lg border bg-transparent p-1" /><Input aria-label="Accent hex color" value={template.branding.accent_hex} onChange={(event) => { const value = event.target.value.toUpperCase(); if (/^#[0-9A-F]{0,6}$/.test(value)) mutate((draft) => { draft.branding.accent_hex = value; }); }} /></div>
                <ToggleRow label="Show brand label" checked={template.branding.show_brand} onChange={(checked) => mutate((draft) => { draft.branding.show_brand = checked; })} />
                <div className="space-y-1"><Label htmlFor="template-font" className="text-xs">Font family</Label><select id="template-font" value={template.typography.font_family} onChange={(event) => mutate((draft) => { draft.typography.font_family = event.target.value as ProfileTemplate["typography"]["font_family"]; })} className="h-8 w-full rounded-lg border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"><option value="Aptos">Aptos</option><option value="Arial">Arial</option><option value="Calibri">Calibri</option></select></div>
                <div className="grid grid-cols-2 gap-2"><div className="space-y-1"><Label htmlFor="template-body-size" className="text-xs">Body pt</Label><Input id="template-body-size" type="number" min={8} max={14} step={0.5} value={template.typography.body_size} onChange={(event) => mutate((draft) => { draft.typography.body_size = Number(event.target.value); })} /></div><div className="space-y-1"><Label htmlFor="template-heading-size" className="text-xs">Heading pt</Label><Input id="template-heading-size" type="number" min={10} max={22} step={0.5} value={template.typography.heading_size} onChange={(event) => mutate((draft) => { draft.typography.heading_size = Number(event.target.value); })} /></div></div>
              </div>
            ) : null}

            {inspectorTab === "header" ? (
              <div className="space-y-2">
                <ToggleRow label="Candidate name" checked={template.header.show_name} onChange={(checked) => mutate((draft) => { draft.header.show_name = checked; })} />
                <ToggleRow label="Headline" checked={template.header.show_headline} onChange={(checked) => mutate((draft) => { draft.header.show_headline = checked; })} />
                <ToggleRow label="Contact line" checked={template.header.show_contact} onChange={(checked) => mutate((draft) => { draft.header.show_contact = checked; })} />
              </div>
            ) : null}

            {inspectorTab === "block" ? (
              selectedSection ? <div className="space-y-3">
                <div><p className="text-xs font-medium">{selectedSection.kind.replaceAll("_", " ")}</p><p className="text-[11px] text-muted-foreground">Visibility is controlled by the eye in the Blocks panel.</p></div>
                <div className="space-y-1"><Label htmlFor="section-title" className="text-xs">Heading</Label><Input id="section-title" maxLength={80} value={selectedSection.title} onChange={(event) => updateSelectedSection((section) => { section.title = event.target.value; })} /></div>
                {SIMPLE_LIST_KINDS.has(selectedSection.kind) ? <div className="space-y-1"><Label htmlFor="section-layout" className="text-xs">List layout</Label><select id="section-layout" value={selectedSection.layout} onChange={(event) => updateSelectedSection((section) => { section.layout = event.target.value as ProfileTemplateSection["layout"]; })} className="h-8 w-full rounded-lg border border-input bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"><option value="inline">Inline</option><option value="bullets">Bullets</option></select></div> : null}
                <Button variant="destructive" size="sm" className="w-full" disabled={template.sections.length <= 1} onClick={removeSection}><Trash2 />Remove block</Button>
              </div> : <p className="text-xs text-muted-foreground">Select a block on the left.</p>
            ) : null}

            {inspectorTab === "logo" ? (
              <div className="space-y-3">
                <input ref={logoInputRef} type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml,.svg" className="hidden" onChange={(event) => { const file = event.target.files?.[0]; if (file) void chooseLogo(file); }} />
                <div><p className="text-xs font-medium">Logo</p><p className="text-[11px] text-muted-foreground">PNG, JPG, WebP, or SVG. SVG/raster uploads are normalized to transparent-capable PNG for DOCX.</p></div>
                <Button variant="outline" size="sm" className="w-full" onClick={() => logoInputRef.current?.click()}><ImagePlus />{template.logo ? "Replace logo" : "Upload logo"}</Button>
                {template.logo ? <>
                  <div className="rounded-lg border bg-muted/20 p-2"><p className="truncate text-xs font-medium">{template.logo.original_name}</p><p className="mt-0.5 text-[11px] text-muted-foreground">Drag the logo anywhere on the A4 preview.</p></div>
                  <div className="space-y-1"><div className="flex justify-between text-[11px]"><Label htmlFor="logo-width" className="text-xs">Width</Label><span className="text-muted-foreground">{Math.round(template.logo.width_pct)}%</span></div><input id="logo-width" type="range" min={2} max={60} step={1} value={template.logo.width_pct} onChange={(event) => resizeLogo(Number(event.target.value))} className="w-full accent-[var(--primary)]" /></div>
                  <div className="grid grid-cols-2 gap-2 text-[11px] text-muted-foreground"><span>X {template.logo.x_pct.toFixed(1)}%</span><span>Y {template.logo.y_pct.toFixed(1)}%</span></div>
                  <Button variant="destructive" size="sm" className="w-full" onClick={() => mutate((draft) => { draft.logo = null; })}><Trash2 />Remove logo</Button>
                </> : null}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
