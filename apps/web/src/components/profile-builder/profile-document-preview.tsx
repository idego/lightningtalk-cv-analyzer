"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, FileText, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  type CandidateProfile,
  type ProfileTemplate,
  type ProfileTemplateLogo,
  type ProfileTemplateSection,
} from "@/components/profile-builder/profile-builder-model";

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
  if (section.kind === "custom_fields") {
    const fields = profile.custom_fields.filter((field) => field.value !== null && field.value !== "");
    return fields.length ? (
      <PreviewSection title={section.title} {...shared}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
          {fields.map((field) => (
            <div key={field.id} className="contents">
              <dt className="font-semibold text-slate-900">{field.label}</dt>
              <dd>{typeof field.value === "boolean" ? (field.value ? "Yes" : "No") : String(field.value)}</dd>
            </div>
          ))}
        </dl>
      </PreviewSection>
    ) : null;
  }
  return null;
}

function groupTemplateSections(sections: ProfileTemplateSection[]) {
  const visible = sections.filter((section) => section.visible);
  const groups: Array<
    | { type: "full"; section: ProfileTemplateSection }
    | { type: "columns"; sections: ProfileTemplateSection[] }
  > = [];
  let index = 0;
  while (index < visible.length) {
    const section = visible[index];
    if (section.placement === "full") {
      groups.push({ type: "full", section });
      index += 1;
      continue;
    }
    const sideSections: ProfileTemplateSection[] = [];
    while (index < visible.length && visible[index].placement !== "full") {
      sideSections.push(visible[index]);
      index += 1;
    }
    groups.push({ type: "columns", sections: sideSections });
  }
  return groups;
}

export function ProfileDocumentPreview({
  profile,
  template,
  label = "Profile layout preview",
  logoEditable = false,
  onLogoChange,
  onLogoSelect,
  fillHeight = false,
  sectionsEditable = false,
  onSectionsChange,
  onSectionSelect,
}: {
  profile: CandidateProfile;
  template: ProfileTemplate;
  label?: string;
  logoEditable?: boolean;
  onLogoChange?: (logo: ProfileTemplateLogo) => void;
  onLogoSelect?: () => void;
  fillHeight?: boolean;
  sectionsEditable?: boolean;
  onSectionsChange?: (sections: ProfileTemplateSection[]) => void;
  onSectionSelect?: (sectionId: string) => void;
}) {
  const [previewPage, setPreviewPage] = useState(1);
  const [previewPageCount, setPreviewPageCount] = useState(1);
  const previewViewportRef = useRef<HTMLDivElement>(null);
  const previewFlowRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef<HTMLDivElement>(null);
  const logoDragRef = useRef<{
    pointerId: number;
    clientX: number;
    clientY: number;
    xPct: number;
    yPct: number;
  } | null>(null);
  const [draggedSectionId, setDraggedSectionId] = useState<string | null>(null);
  const [dragLane, setDragLane] = useState<ProfileTemplateSection["placement"]>("full");

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

  function startLogoDrag(event: React.PointerEvent<HTMLImageElement>) {
    if (!logoEditable || !template.logo || !onLogoChange) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    logoDragRef.current = {
      pointerId: event.pointerId,
      clientX: event.clientX,
      clientY: event.clientY,
      xPct: template.logo.x_pct,
      yPct: template.logo.y_pct,
    };
    onLogoSelect?.();
  }

  function moveLogo(event: React.PointerEvent<HTMLImageElement>) {
    const drag = logoDragRef.current;
    const page = pageRef.current;
    const logo = template.logo;
    if (!drag || drag.pointerId !== event.pointerId || !page || !logo || !onLogoChange) return;
    const rect = page.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    const logoHeightPct = ((rect.width * logo.width_pct / 100) / logo.aspect_ratio) / rect.height * 100;
    const nextX = Math.min(100 - logo.width_pct, Math.max(0, drag.xPct + (event.clientX - drag.clientX) / rect.width * 100));
    const nextY = Math.min(100 - logoHeightPct, Math.max(0, drag.yPct + (event.clientY - drag.clientY) / rect.height * 100));
    onLogoChange({ ...logo, x_pct: nextX, y_pct: nextY });
  }

  function endLogoDrag(event: React.PointerEvent<HTMLImageElement>) {
    if (logoDragRef.current?.pointerId !== event.pointerId) return;
    logoDragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function laneFromPointer(clientX: number): ProfileTemplateSection["placement"] {
    const viewport = previewViewportRef.current;
    if (!viewport) return "full";
    const rect = viewport.getBoundingClientRect();
    const ratio = (clientX - rect.left) / Math.max(1, rect.width);
    if (ratio < 0.34) return "left";
    if (ratio > 0.66) return "right";
    return "full";
  }

  function moveCanvasSection(activeId: string, targetId: string, after: boolean, placement: ProfileTemplateSection["placement"]) {
    if (!onSectionsChange) return;
    const next = structuredClone(template.sections);
    const from = next.findIndex((section) => section.id === activeId);
    const target = next.findIndex((section) => section.id === targetId);
    if (from < 0 || target < 0) return;
    const [section] = next.splice(from, 1);
    section.placement = placement;
    const targetAfterRemoval = next.findIndex((item) => item.id === targetId);
    const insertAt = Math.max(0, targetAfterRemoval + (after ? 1 : 0));
    next.splice(insertAt, 0, section);
    onSectionsChange(next);
    onSectionSelect?.(section.id);
  }

  function draggableSection(section: ProfileTemplateSection) {
    return (
      <div
        key={section.id}
        draggable={sectionsEditable}
        onClick={() => sectionsEditable && onSectionSelect?.(section.id)}
        onDragStart={(event) => {
          if (!sectionsEditable) return;
          setDraggedSectionId(section.id);
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", section.id);
        }}
        onDragEnd={() => { setDraggedSectionId(null); setDragLane("full"); }}
        onDragOver={(event) => {
          if (!sectionsEditable) return;
          event.preventDefault();
          event.stopPropagation();
          setDragLane(laneFromPointer(event.clientX));
        }}
        onDrop={(event) => {
          if (!sectionsEditable) return;
          event.preventDefault();
          event.stopPropagation();
          const activeId = draggedSectionId || event.dataTransfer.getData("text/plain");
          if (!activeId) return;
          const rect = event.currentTarget.getBoundingClientRect();
          moveCanvasSection(activeId, section.id, event.clientY > rect.top + rect.height / 2, laneFromPointer(event.clientX));
          setDraggedSectionId(null);
        }}
        className={sectionsEditable ? `group relative cursor-grab rounded-md transition-[outline,background-color] hover:bg-slate-50/60 hover:outline hover:outline-1 hover:outline-cyan-400/60 active:cursor-grabbing ${draggedSectionId === section.id ? "opacity-40" : ""}` : undefined}
      >
        {sectionsEditable ? <span className="pointer-events-none absolute -right-1 -top-2 z-10 rounded bg-slate-900 px-1.5 py-0.5 text-[8px] font-medium uppercase tracking-wide text-white opacity-0 transition-opacity group-hover:opacity-100">{section.placement}</span> : null}
        <TemplateSectionPreview section={section} profile={profile} template={template} />
      </div>
    );
  }

  const sectionGroups = groupTemplateSections(template.sections);

  return (
    <div className={fillHeight ? "flex h-full min-h-0 min-w-0 flex-col" : "min-w-0"}>
      <div className="mb-2 flex shrink-0 flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="size-4" />{label} · {template.name}
        </div>
        <div className="flex items-center gap-1 rounded-lg border bg-card p-1" role="group" aria-label="Preview page navigation">
          <Button variant="ghost" size="icon-sm" aria-label="Previous preview page" disabled={previewPage <= 1} onClick={() => setPreviewPage((current) => Math.max(1, current - 1))}><ChevronLeft /></Button>
          <span className="min-w-16 text-center text-xs font-medium tabular-nums">{previewPage} / {previewPageCount}</span>
          <Button variant="ghost" size="icon-sm" aria-label="Next preview page" disabled={previewPage >= previewPageCount} onClick={() => setPreviewPage((current) => Math.min(previewPageCount, current + 1))}><ChevronRight /></Button>
        </div>
      </div>
      <div className={fillHeight ? "flex min-h-0 flex-1 items-center justify-center" : ""}>
      <div ref={pageRef} className={fillHeight ? "relative h-full max-h-full aspect-[210/297] w-auto max-w-full overflow-hidden bg-white text-[#081932] shadow-[0_8px_30px_rgba(8,25,50,0.12)] ring-1 ring-black/10 dark:text-[#081932]" : "relative mx-auto aspect-[210/297] w-full max-w-[760px] overflow-hidden bg-white text-[#081932] shadow-[0_8px_30px_rgba(8,25,50,0.12)] ring-1 ring-black/10 dark:text-[#081932]"}>
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
            <div
              className="space-y-6"
              onDragOver={(event) => {
                if (!sectionsEditable) return;
                event.preventDefault();
                setDragLane(laneFromPointer(event.clientX));
              }}
              onDrop={(event) => {
                if (!sectionsEditable || !draggedSectionId || !onSectionsChange) return;
                if (event.target !== event.currentTarget) return;
                event.preventDefault();
                const next = structuredClone(template.sections);
                const from = next.findIndex((section) => section.id === draggedSectionId);
                if (from < 0) return;
                const [section] = next.splice(from, 1);
                section.placement = laneFromPointer(event.clientX);
                next.push(section);
                onSectionsChange(next);
                setDraggedSectionId(null);
              }}
            >
              {template.header.show_contact && contacts.length ? <p className="text-xs text-slate-500">{contacts.join(" · ")}</p> : null}
              {sectionGroups.map((group, groupIndex) => group.type === "full"
                ? draggableSection(group.section)
                : <div key={`columns-${groupIndex}`} className="grid grid-cols-2 items-start gap-5">
                    <div className="space-y-5">{group.sections.filter((section) => section.placement === "left").map(draggableSection)}</div>
                    <div className="space-y-5">{group.sections.filter((section) => section.placement === "right").map(draggableSection)}</div>
                  </div>)}
            </div>
          </div>
        </div>
        {sectionsEditable && draggedSectionId ? <div className="pointer-events-none absolute inset-x-[7.5%] bottom-[7%] top-[6.5%] z-30 grid grid-cols-3 gap-1">{(["left", "full", "right"] as const).map((lane) => <div key={lane} className={`flex items-center justify-center rounded border border-dashed text-[10px] font-semibold uppercase tracking-wider ${dragLane === lane ? "border-cyan-500 bg-cyan-400/15 text-cyan-800" : "border-slate-300/60 bg-white/20 text-slate-400"}`}>{lane}</div>)}</div> : null}
        {template.logo ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={template.logo.data_url}
            alt="Template logo"
            draggable={false}
            onPointerDown={startLogoDrag}
            onPointerMove={moveLogo}
            onPointerUp={endLogoDrag}
            onPointerCancel={endLogoDrag}
            onClick={() => onLogoSelect?.()}
            className={logoEditable ? "absolute z-20 cursor-move select-none rounded-sm outline outline-1 outline-primary/60" : "pointer-events-none absolute z-20 select-none"}
            style={{
              left: `${template.logo.x_pct}%`,
              top: `${template.logo.y_pct}%`,
              width: `${template.logo.width_pct}%`,
              height: "auto",
              touchAction: "none",
            }}
          />
        ) : null}
        <div className="absolute inset-x-[7.5%] bottom-[2.5%] flex items-center justify-between border-t pt-2 text-[10px] text-slate-400">
          <span><FileText className="mr-1 inline size-3" />{template.branding.show_brand ? `${template.branding.brand_name} Candidate Profile` : "Candidate Profile"}</span>
          <span>Page {previewPage} of {previewPageCount}</span>
        </div>
      </div>
      </div>
      <p className={fillHeight ? "mt-1 shrink-0 text-center text-[10px] leading-tight text-muted-foreground" : "mx-auto mt-2 max-w-[760px] text-[11px] leading-relaxed text-muted-foreground"}>
        Page breaks reflect this browser preview. Final DOCX pagination can vary slightly between Word-compatible renderers.
      </p>
    </div>
  );
}
