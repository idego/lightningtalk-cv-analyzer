import type { AnalysisReport, UnderstandingRecord } from "./analyze-types.ts";

export type DisplayRecord = {
  id: string; kind: "education" | "employment"; authority: "code" | "ai";
  confidence: string; institution?: string; program?: string | null; study_dates?: string | null;
  organization?: string; role?: string | null; employment_dates?: string | null; location?: string | null;
  unknown_fields: string[];
};

function field(record: UnderstandingRecord, name: string) {
  return record.fields.find((item) => item.name === name);
}

function codeRecord(record: UnderstandingRecord): DisplayRecord | null {
  const identityName = record.kind === "education" ? "institution" : "organization";
  const identity = field(record, identityName);
  if (identity?.status !== "supported" || !identity.value) return null;
  const unknown_fields = record.fields.filter((item) => item.status !== "supported").map((item) => item.name);
  if (record.kind === "education") return { id: record.id, kind: "education", authority: "code", confidence: record.confidence, institution: identity.value, program: field(record, "program")?.value, study_dates: field(record, "study_dates")?.value, location: field(record, "education_location")?.value, unknown_fields };
  return { id: record.id, kind: "employment", authority: "code", confidence: record.confidence, organization: identity.value, role: field(record, "role")?.value, employment_dates: field(record, "employment_dates")?.value, location: field(record, "employment_location")?.value, unknown_fields };
}

export function selectStructuredRecords(report: Pick<AnalysisReport, "document_understanding" | "ai_analysis">): DisplayRecord[] {
  const understanding = report.document_understanding;
  if (!understanding) return [
    ...report.ai_analysis.facts.education.map((item, index) => ({ id: `legacy-education-${index}`, kind: "education" as const, authority: "ai" as const, confidence: "medium", institution: item.institution, program: item.program, study_dates: item.study_dates, unknown_fields: [] })),
    ...report.ai_analysis.facts.employment.map((item, index) => ({ id: `legacy-employment-${index}`, kind: "employment" as const, authority: "ai" as const, confidence: "medium", organization: item.organization, role: item.role, employment_dates: item.employment_dates, location: item.location, unknown_fields: [] })),
  ];
  const code = understanding.records.map(codeRecord).filter((item): item is DisplayRecord => Boolean(item));
  const keys = new Set(code.map((item) => `${item.kind}:${(item.institution ?? item.organization ?? "").normalize("NFKC").toLocaleLowerCase().trim()}`));
  const additions: DisplayRecord[] = [];
  for (const [index, item] of report.ai_analysis.facts.education.entries()) {
    const key = `education:${item.institution.normalize("NFKC").toLocaleLowerCase().trim()}`; if (keys.has(key)) continue;
    keys.add(key); additions.push({ id: `ai-education-${index}`, kind: "education", authority: "ai", confidence: "medium", institution: item.institution, program: item.program, study_dates: item.study_dates, unknown_fields: [] });
  }
  for (const [index, item] of report.ai_analysis.facts.employment.entries()) {
    const key = `employment:${item.organization.normalize("NFKC").toLocaleLowerCase().trim()}`; if (keys.has(key)) continue;
    keys.add(key); additions.push({ id: `ai-employment-${index}`, kind: "employment", authority: "ai", confidence: "medium", organization: item.organization, role: item.role, employment_dates: item.employment_dates, location: item.location, unknown_fields: [] });
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
