import { AlertCircle, EyeOff, Timer } from "lucide-react";
import type { AIEducationFact, AIEmploymentFact, DocumentUnderstanding, StructuralAudits, StructuralSourceLocation, StructuralTimelineEntry, StructuralTimelineObservation, UnderstandingRecord } from "@/lib/analyze-types";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

const COPY = {
  en: {
    title: "Structural review", legacy: "This older report has no structural audit.", completed: "Review completed",
    partial: "Review completed with partial coverage", unavailable: "Review unavailable", not_applicable: "Not applicable",
    noFindings: "No structural review items found.", review: "Needs review", possible: "Possible overlap",
    definite: "Overlapping periods", invalid: "Invalid date period", source: "Source", hidden: "Technically hidden text",
    nearZero: "Very small text", opacity: "Near-transparent text", contrast: "Low-contrast text", omitted: "Not inspected",
    more: "additional items omitted", months: "months", workOverlap: "Overlapping work periods", educationOverlap: "Overlapping education periods",
    workPeriod: "Work period", educationPeriod: "Education period", unknownPeriod: "Timeline period", entries: "entries", relationships: "overlap relationships",
    overlapsOthers: "overlaps {count} other work entries",
  },
  pl: {
    title: "Kontrola struktury", legacy: "Ten starszy raport nie zawiera kontroli struktury.", completed: "Kontrola zakończona",
    partial: "Kontrola zakończona z częściowym zakresem", unavailable: "Kontrola niedostępna", not_applicable: "Nie dotyczy",
    noFindings: "Nie znaleziono elementów wymagających kontroli struktury.", review: "Do sprawdzenia", possible: "Możliwe nakładanie okresów",
    definite: "Nakładające się okresy", invalid: "Nieprawidłowy okres dat", source: "Źródło", hidden: "Tekst technicznie ukryty",
    nearZero: "Bardzo mały tekst", opacity: "Tekst prawie przezroczysty", contrast: "Tekst o niskim kontraście", omitted: "Nie sprawdzono",
    more: "dodatkowych elementów pominięto", months: "mies.", workOverlap: "Nakładające się okresy pracy", educationOverlap: "Nakładające się okresy edukacji",
    workPeriod: "Okres pracy", educationPeriod: "Okres edukacji", unknownPeriod: "Okres na osi czasu", entries: "wpisy", relationships: "relacje nakładania",
    overlapsOthers: "nakłada się z {count} innymi wpisami pracy",
  },
};

function location(value: StructuralSourceLocation) {
  const line = value.line_number ? `, line ${value.line_number}` : "";
  const path = value.paragraph_path ? `, ${value.paragraph_path}` : "";
  return `page ${value.page_number}${line}${path}`;
}

function normalizedDate(value: string | null | undefined) {
  return (value ?? "").toLocaleLowerCase().replace(/[–—]/g, "-").replace(/\s+/g, " ").trim();
}

function entryDescription(
  entry: StructuralTimelineEntry | undefined,
  employment: AIEmploymentFact[],
  education: AIEducationFact[],
  copy: typeof COPY.en | typeof COPY.pl,
  linkedRecord?: UnderstandingRecord,
  allowLegacyDateFallback = false,
) {
  if (!entry) return copy.unknownPeriod;
  if (linkedRecord) {
    const values = Object.fromEntries(linkedRecord.fields.filter(field => field.status === "supported").map(field => [field.name, field.value]));
    return linkedRecord.kind === "employment"
      ? [values.role, values.organization].filter(Boolean).join(" · ") || copy.workPeriod
      : [values.program, values.institution].filter(Boolean).join(" · ") || copy.educationPeriod;
  }
  if (!allowLegacyDateFallback) return entry.category === "employment" ? copy.workPeriod : entry.category === "education" ? copy.educationPeriod : copy.unknownPeriod;
  const range = normalizedDate(`${entry.start_text ?? ""} - ${entry.end_text ?? ""}`);
  if (entry.category === "employment") {
    const fact = employment.find(item => normalizedDate(item.employment_dates) === range);
    return fact ? `${fact.role} · ${fact.organization}` : copy.workPeriod;
  }
  if (entry.category === "education") {
    const fact = education.find(item => normalizedDate(item.study_dates) === range);
    return fact ? [fact.program, fact.institution].filter(Boolean).join(" · ") : copy.educationPeriod;
  }
  return copy.unknownPeriod;
}

type TimelineGroup = {
  key: string;
  category: string;
  entries: StructuralTimelineEntry[];
  observations: StructuralTimelineObservation[];
};

function timelineGroups(audits: StructuralAudits, entryById: Map<string, StructuralTimelineEntry>) {
  const overlaps = audits.timeline.observations.filter(item => item.kind !== "invalid_period");
  const remaining = new Set(overlaps.map(item => item.id));
  const groups: TimelineGroup[] = [];

  while (remaining.size) {
    const seedId = remaining.values().next().value as string;
    const groupObservations: StructuralTimelineObservation[] = [];
    const entryIds = new Set<string>();
    let changed = true;
    const seed = overlaps.find(item => item.id === seedId);
    seed?.entry_ids.forEach(id => entryIds.add(id));

    while (changed) {
      changed = false;
      for (const observation of overlaps) {
        if (!remaining.has(observation.id) || !observation.entry_ids.some(id => entryIds.has(id))) continue;
        remaining.delete(observation.id);
        groupObservations.push(observation);
        observation.entry_ids.forEach(id => entryIds.add(id));
        changed = true;
      }
    }

    const entries = Array.from(entryIds).map(id => entryById.get(id)).filter((entry): entry is StructuralTimelineEntry => Boolean(entry));
    groups.push({ key: seedId, category: entries[0]?.category ?? "unknown", entries, observations: groupObservations });
  }

  for (const observation of audits.timeline.observations.filter(item => item.kind === "invalid_period")) {
    const entries = observation.entry_ids.map(id => entryById.get(id)).filter((entry): entry is StructuralTimelineEntry => Boolean(entry));
    groups.push({ key: observation.id, category: entries[0]?.category ?? "unknown", entries, observations: [observation] });
  }
  return groups;
}

export function StructuralAuditPanel({ audits, language, employment = [], education = [], understanding }: { audits: StructuralAudits | null | undefined; language: "en" | "pl"; employment?: AIEmploymentFact[]; education?: AIEducationFact[]; understanding?: DocumentUnderstanding | null }) {
  const copy = COPY[language];
  if (!audits) return <HoverDisclosure className="rounded-md border p-3" title={<span className="font-medium">{copy.title}</span>} contentClassName="pt-3"><p className="text-sm text-muted-foreground">{copy.legacy}</p></HoverDisclosure>;

  const status = copy[audits.status as keyof typeof copy] ?? audits.status;
  const entryById = new Map(audits.timeline.entries.map(entry => [entry.id, entry]));
  const recordById = new Map((understanding?.records ?? []).map(record => [record.id, record]));
  const linkedRecordByTimeline = new Map((understanding?.timeline_record_links ?? []).map(link => [link.timeline_entry_id, recordById.get(link.record_id)]));
  const groups = timelineGroups(audits, entryById);
  const visibilityNames = { hidden_text: copy.hidden, near_zero_text: copy.nearZero, zero_opacity_text: copy.opacity, low_contrast_text: copy.contrast };
  const count = groups.length + audits.visibility.observations.length;
  const omittedParts = audits.coverage.omitted_parts.filter(part => part !== "docx_comments");
  const allowLegacyDateFallback = understanding == null;

  return <HoverDisclosure
    className="rounded-md border p-3"
    triggerClassName="text-sm"
    title={<span><span className="font-medium">{copy.title}{count ? ` (${count})` : ""}</span><span className="mt-0.5 block text-xs font-normal text-muted-foreground">{status}</span></span>}
    contentClassName="space-y-3 pt-3"
  >
    {omittedParts.length ? <p className="text-xs text-amber-700 dark:text-amber-300">{copy.omitted}: {omittedParts.join(", ")}</p> : null}
    {!count ? <p className="text-sm text-muted-foreground">{copy.noFindings}</p> : null}

    {groups.length ? <div className="divide-y rounded-md border bg-muted/10">
      {groups.map(group => {
        const invalid = group.observations.some(observation => observation.kind === "invalid_period");
        const title = invalid
          ? copy.invalid
          : group.category === "employment"
            ? copy.workOverlap
            : group.category === "education"
              ? copy.educationOverlap
              : group.observations.every(observation => observation.kind === "definite_overlap") ? copy.definite : copy.possible;
        const connections = new Map(group.entries.map(entry => [entry.id, 0]));
        group.observations.forEach(observation => observation.entry_ids.forEach(id => connections.set(id, (connections.get(id) ?? 0) + 1)));
        const anchor = group.entries.reduce((best, entry) => (connections.get(entry.id) ?? 0) > (connections.get(best?.id ?? "") ?? 0) ? entry : best, group.entries[0]);
        const anchorConnections = anchor ? connections.get(anchor.id) ?? 0 : 0;
        return <div key={group.key} className="px-3 py-3 text-sm">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="flex items-center gap-2 font-medium"><Timer className="size-4" />{title}</span>
            <span className="text-xs text-muted-foreground">{group.entries.length} {copy.entries} · {group.observations.length} {copy.relationships}</span>
          </div>
          {group.category === "employment" && anchorConnections > 1 ? <p className="mt-1 text-xs text-muted-foreground">{entryDescription(anchor, employment, education, copy, anchor ? linkedRecordByTimeline.get(anchor.id) : undefined, allowLegacyDateFallback)} {copy.overlapsOthers.replace("{count}", String(anchorConnections))}.</p> : null}
          <div className="mt-2 grid gap-1.5 sm:grid-cols-2">
            {group.entries.map(entry => <div key={entry.id} className="rounded bg-muted/40 px-2.5 py-2">
              <p className="font-medium">{entryDescription(entry, employment, education, copy, linkedRecordByTimeline.get(entry.id), allowLegacyDateFallback)}</p>
              <p className="text-xs text-muted-foreground">{entry.start_text ?? "?"} – {entry.end_text ?? "?"}</p>
              {entry.evidence[0] ? <p className="mt-1 text-[11px] text-muted-foreground">{location(entry.evidence[0].location)}</p> : null}
            </div>)}
          </div>
        </div>;
      })}
    </div> : null}

    {audits.visibility.observations.length ? <div className="divide-y rounded-md border bg-muted/10">
      {audits.visibility.observations.map(observation => <div key={observation.id} className="px-3 py-2.5 text-sm">
        <p className="flex items-center gap-2 font-medium"><EyeOff className="size-4" />{visibilityNames[observation.kind]} · {copy.review}</p>
        <p className="mt-1 text-xs text-muted-foreground">{observation.character_count} chars · {observation.confidence} · {copy.source}: {location(observation.source_location)}</p>
        {observation.redaction?.present ? <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground"><AlertCircle className="size-3" />Sensitive value redacted ({observation.redaction.type_hints.join(", ")})</p> : null}
      </div>)}
    </div> : null}

    {audits.timeline.additional_entry_count + audits.visibility.additional_observation_count > 0 ? <p className="text-xs text-muted-foreground">{audits.timeline.additional_entry_count + audits.visibility.additional_observation_count} {copy.more}</p> : null}
  </HoverDisclosure>;
}
