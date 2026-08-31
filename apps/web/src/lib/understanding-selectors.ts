import type { AnalysisReport, UnderstandingRecord } from "./analyze-types.ts";
import { isSelfEmploymentLabel } from "./relationship-labels.js";

export type DisplayRecord = {
  id: string; kind: "education" | "employment"; authority: "code" | "ai";
  confidence: string; institution?: string; program?: string | null; degree?: string | null; study_dates?: string | null;
  organization?: string; role?: string | null; employment_dates?: string | null; location?: string | null;
  relationship_type?: string | null; unknown_fields: string[];
  ai_enrichments?: Array<{ name: string; value: string; authority: "ai" }>;
  conflicts?: Array<{ name: string; code_value: string; ai_value: string }>;
};

function field(record: UnderstandingRecord, name: string) {
  return record.fields.find((item) => item.name === name);
}

function codeRecord(record: UnderstandingRecord): DisplayRecord | null {
  const identityName = record.kind === "education" ? "institution" : "organization";
  const identity = field(record, identityName);
  const relationship = field(record, "relationship_type")?.value;
  if ((identity?.status !== "supported" || !identity.value) && !(record.kind === "employment" && isSelfEmploymentLabel(relationship))) return null;
  const unknown_fields = record.fields.filter((item) => item.status !== "supported").map((item) => item.name);
  if (record.kind === "education") return { id: record.id, kind: "education", authority: "code", confidence: record.confidence, institution: identity?.value ?? undefined, program: field(record, "program")?.value, degree: field(record, "degree")?.value, study_dates: field(record, "study_dates")?.value, location: field(record, "education_location")?.value, unknown_fields, ai_enrichments: [], conflicts: [] };
  return { id: record.id, kind: "employment", authority: "code", confidence: record.confidence, organization: identity?.value ?? undefined, relationship_type: relationship, role: field(record, "role")?.value, employment_dates: field(record, "employment_dates")?.value, location: field(record, "employment_location")?.value, unknown_fields, ai_enrichments: [], conflicts: [] };
}

const norm = (value: string | null | undefined) => (value ?? "").normalize("NFKC").toLocaleLowerCase().trim().replace(/\s+/g, " ");
const identity = (item: DisplayRecord) => norm(item.institution ?? item.organization ?? item.relationship_type);
const secondary = (item: DisplayRecord) => item.kind === "education" ? [norm(item.program), norm(item.study_dates)] : [norm(item.role), norm(item.employment_dates)];
const exactKey = (item: DisplayRecord) => `${item.kind}:${identity(item)}:${secondary(item).join(":")}`;

function enrich(code: DisplayRecord, ai: DisplayRecord) {
  const names = code.kind === "education" ? ["program", "study_dates"] as const : ["role", "employment_dates", "location", "relationship_type"] as const;
  for (const name of names) {
    const codeValue = code[name]; const aiValue = ai[name];
    if (!aiValue) continue;
    if (!codeValue) code.ai_enrichments!.push({ name, value: aiValue, authority: "ai" });
    else if (norm(codeValue) !== norm(aiValue)) code.conflicts!.push({ name, code_value: codeValue, ai_value: aiValue });
  }
}

export function selectStructuredRecords(report: Pick<AnalysisReport, "document_understanding" | "ai_analysis">): DisplayRecord[] {
  const understanding = report.document_understanding;
  if (!understanding) return [
    ...report.ai_analysis.facts.education.map((item, index) => ({ id: `legacy-education-${index}`, kind: "education" as const, authority: "ai" as const, confidence: "medium", institution: item.institution, program: item.program, study_dates: item.study_dates, unknown_fields: [] })),
    ...report.ai_analysis.facts.employment.map((item, index) => ({ id: `legacy-employment-${index}`, kind: "employment" as const, authority: "ai" as const, confidence: "medium", organization: item.organization, role: item.role, employment_dates: item.employment_dates, location: item.location, unknown_fields: [] })),
  ];
  const code = understanding.records.map(codeRecord).filter((item): item is DisplayRecord => Boolean(item));
  const aiRecords: DisplayRecord[] = [
    ...report.ai_analysis.facts.education.map((item, index) => ({ id: `ai-education-${index}`, kind: "education" as const, authority: "ai" as const, confidence: "medium", institution: item.institution, program: item.program, study_dates: item.study_dates, unknown_fields: [] })),
    ...report.ai_analysis.facts.employment.map((item, index) => ({ id: `ai-employment-${index}`, kind: "employment" as const, authority: "ai" as const, confidence: "medium", organization: item.organization, role: item.role, employment_dates: item.employment_dates, location: item.location, relationship_type: item.relationship_type, unknown_fields: [] })),
  ];
  const matched = new Set<string>();
  for (const record of code) {
    const candidates = aiRecords.filter(item => !matched.has(item.id) && item.kind === record.kind && identity(item) === identity(record));
    const match = candidates.find(item => secondary(record).some((value, index) => value && value === secondary(item)[index])) ?? (candidates.length === 1 ? candidates[0] : undefined);
    if (match) { matched.add(match.id); enrich(record, match); }
  }
  const keys = new Set(code.map(exactKey));
  const additions: DisplayRecord[] = [];
  for (const item of aiRecords) {
    if (matched.has(item.id)) continue;
    const key = exactKey(item); if (keys.has(key)) continue;
    keys.add(key); additions.push(item);
  }
  return [...code, ...additions];
}

export function researchEligibility(report: Pick<AnalysisReport, "document_understanding" | "ai_analysis" | "ai_features_enabled" | "ai_capabilities">) {
  const enabled = report.ai_features_enabled !== false;
  const code = report.document_understanding?.code_research_subjects ?? [];
  const ai = report.ai_analysis.status === "succeeded" ? report.ai_analysis.research_candidates : [];
  return {
    company: enabled && report.ai_capabilities?.company_research !== false && (code.some((item) => item.category === "company") || ai.some((item) => item.category === "company")),
    education: enabled && report.ai_capabilities?.education_research !== false && (code.some((item) => item.category === "education") || ai.some((item) => item.category === "education_or_certification")),
    linkedin: enabled && report.ai_capabilities?.linkedin_research !== false && report.ai_analysis.status === "succeeded" && ai.some((item) => item.category === "linkedin"),
  };
}

export function timelineRecordMap(report: Pick<AnalysisReport, "document_understanding">) {
  return new Map((report.document_understanding?.timeline_record_links ?? []).map((item) => [item.timeline_entry_id, item.record_id]));
}
