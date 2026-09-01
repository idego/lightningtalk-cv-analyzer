import type {
  AnalysisReport,
  EducationRecord,
  EmploymentRecord,
  Evidence,
  SupportedField,
} from "./analyze-types";

export type ReportLanguage = "en" | "pl";

export type ReportFinding = {
  id: string;
  whatWeFound: string;
  whyItMatters: string;
  whatToCheck: string;
  evidence: Evidence[];
};

export type OverviewRecord = {
  id: string;
  value: string;
  detail: string | null;
};

export type ReportOverview = {
  candidateName: string | null;
  phone: string | null;
  phoneCountry: string | null;
  statedLocation: string | null;
  resolvedLocation: string | null;
  postalCode: string | null;
  postalCountry: string | null;
  euStatus: "inside" | "outside" | null;
  education: OverviewRecord[];
  employment: OverviewRecord[];
};

export type ReportInterface = {
  attention: ReportFinding[];
  worthKnowing: ReportFinding[];
  remaining: ReportFinding[];
  overview: ReportOverview;
};

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as UnknownRecord
    : null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function value(field: SupportedField | null | undefined): string | null {
  return field?.value ?? null;
}

function evidenceFrom(input: unknown): Evidence[] {
  const item = record(input);
  const candidate = item?.evidence;
  if (!Array.isArray(candidate)) return [];
  return candidate.flatMap((entry) => {
    const evidence = record(entry);
    const sourceId = text(evidence?.source_id);
    const excerpt = text(evidence?.excerpt);
    return sourceId && excerpt ? [{
      source_id: sourceId,
      excerpt,
      page_number: typeof evidence?.page_number === "number" ? evidence.page_number : null,
    }] : [];
  });
}

function firstEvidence(input: unknown): Evidence[] {
  const item = record(input);
  const direct = evidenceFrom(item);
  if (direct.length) return direct;
  for (const candidate of Object.values(item ?? {})) {
    const nested = evidenceFrom(candidate);
    if (nested.length) return nested;
  }
  return [];
}

function readable(value: string) {
  return value.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
}

function description(input: unknown, fallback: string): string {
  const item = record(input);
  return text(item?.summary)
    ?? text(item?.message)
    ?? text(item?.reason)
    ?? text(item?.reason_code)?.replaceAll("_", " ")
    ?? text(item?.kind)?.replaceAll("_", " ")
    ?? fallback;
}

function finding(
  id: string,
  input: unknown,
  fallback: string,
  whyItMatters: string,
  whatToCheck: string,
): ReportFinding {
  return {
    id,
    whatWeFound: readable(description(input, fallback)),
    whyItMatters,
    whatToCheck,
    evidence: firstEvidence(input),
  };
}

function localized(language: ReportLanguage) {
  return language === "pl" ? {
    conflict: "Reviewer wykrył konflikt w danych CV.",
    conflictWhy: "Sprzeczne wartości mogą należeć do różnych wpisów lub relacji.",
    conflictCheck: "Porównaj wskazane dane z dosłownym fragmentem CV.",
    gap: "Nie udało się bezpiecznie uzupełnić informacji w CV.",
    gapWhy: "Brak danych ogranicza kompletność raportu.",
    gapCheck: "Sprawdź brakującą informację bezpośrednio w CV.",
    ambiguous: "Wpis zawiera niejednoznaczne dane lub relację.",
    ambiguousWhy: "Pola mogą być poprawne osobno, ale połączone w niewłaściwy wpis.",
    ambiguousCheck: "Potwierdź firmę lub instytucję, rolę, daty i lokalizację jako jeden wpis.",
    mismatch: "Deklarowany kraj i kraj numeru telefonu są różne.",
    mismatchWhy: "To sygnał niespójności, a nie dowód miejsca pobytu.",
    mismatchCheck: "Sprawdź deklarowaną lokalizację i numer telefonu w CV.",
    emailTypo: "Adres e-mail może zawierać literówkę w popularnej domenie.",
    emailTypoWhy: "Literówka może uniemożliwić kontakt z kandydatem.",
    emailTypoCheck: "Porównaj adres z oryginalnym CV przed użyciem.",
    incomplete: "Jeden z przebiegów analizy nie został ukończony.",
    incompleteWhy: "Część informacji mogła nie zostać wydobyta.",
    incompleteCheck: "Sprawdź wskazany obszar CV ręcznie.",
    added: "Reviewer dodał pominiętą informację z literalnym dowodem.",
    addedWhy: "Extractor nie zwrócił informacji obecnej w CV.",
    addedCheck: "Sprawdź dodaną wartość i cytowany fragment.",
    changed: "Reviewer scalił lub poprawił relację między polami.",
    changedWhy: "Prawidłowe wartości muszą należeć do właściwego wpisu.",
    changedCheck: "Potwierdź powiązanie pól w CV.",
    rejected: "Kandydat lub pole zostało odrzucone podczas walidacji.",
    rejectedWhy: "Odrzucona wartość nie spełniała wymagań dowodu lub relacji.",
    rejectedCheck: "Uwzględnij ją tylko po ręcznym potwierdzeniu w CV.",
    match: "Deklarowany kraj i kraj numeru telefonu są zgodne.",
    matchWhy: "To informacyjny sygnał spójności, nie weryfikacja lokalizacji.",
    matchCheck: "Nie traktuj tego sygnału jako dowodu miejsca pobytu.",
  } : {
    conflict: "The reviewer found a conflict in the CV data.",
    conflictWhy: "Conflicting values may belong to different records or relationships.",
    conflictCheck: "Compare the identified data with the literal CV excerpt.",
    gap: "Information in the CV could not be added safely.",
    gapWhy: "Missing data limits the completeness of the report.",
    gapCheck: "Review the missing information directly in the CV.",
    ambiguous: "A record contains ambiguous data or relationships.",
    ambiguousWhy: "Fields may be correct separately but combined into the wrong record.",
    ambiguousCheck: "Confirm the company or institution, role, dates, and location as one record.",
    mismatch: "The declared country and phone country differ.",
    mismatchWhy: "This is a consistency signal, not proof of residence.",
    mismatchCheck: "Review the declared location and phone number in the CV.",
    emailTypo: "The email address may contain a typo in a common provider domain.",
    emailTypoWhy: "A typo may prevent contact with the candidate.",
    emailTypoCheck: "Compare the address with the original CV before using it.",
    incomplete: "One analysis pass did not complete.",
    incompleteWhy: "Some information may not have been extracted.",
    incompleteCheck: "Review the identified area of the CV manually.",
    added: "The reviewer added missed information with literal evidence.",
    addedWhy: "An extractor omitted information present in the CV.",
    addedCheck: "Review the added value and its quoted evidence.",
    changed: "The reviewer merged records or corrected a field relationship.",
    changedWhy: "Correct values still need to belong to the correct record.",
    changedCheck: "Confirm the relationship between the fields in the CV.",
    rejected: "A candidate or field was rejected during validation.",
    rejectedWhy: "The rejected value did not meet evidence or relationship requirements.",
    rejectedCheck: "Use it only after manually confirming it in the CV.",
    match: "The declared country and phone country are consistent.",
    matchWhy: "This is an informational consistency signal, not location verification.",
    matchCheck: "Do not treat this signal as proof of residence.",
  };
}

function fieldEvidence(record: EmploymentRecord | EducationRecord): Evidence[] {
  for (const candidate of Object.values(record)) {
    if (recordValue(candidate)?.evidence.length) return recordValue(candidate)!.evidence;
  }
  return [];
}

function recordValue(input: unknown): SupportedField | null {
  const item = record(input);
  return text(item?.value) && Array.isArray(item?.evidence) ? item as SupportedField : null;
}

function join(values: Array<string | null | undefined>): string | null {
  const result = values.filter((item): item is string => Boolean(item)).join(" · ");
  return result || null;
}

function dateRange(start: SupportedField | null, end: SupportedField | null): string | null {
  return join([value(start), value(end)]);
}

function educationRecord(item: EducationRecord): OverviewRecord {
  return {
    id: item.id,
    value: value(item.institution) ?? "Education entry",
    detail: join([
      value(item.program),
      value(item.degree),
      value(item.certificate),
      dateRange(item.start_date, item.end_date),
      value(item.location),
    ]),
  };
}

function employmentRecord(item: EmploymentRecord): OverviewRecord {
  return {
    id: item.id,
    value: value(item.role) ?? value(item.relationship_type) ?? "Employment entry",
    detail: join([
      dateRange(item.start_date, item.end_date),
      value(item.organization),
      value(item.location),
    ]),
  };
}

function overview(report: AnalysisReport): ReportOverview {
  const phone = record(report.mechanical.phones[0]);
  const resolution = report.mechanical.location_resolution
    .map(record)
    .find((item) => item?.subject === "declared_location") ?? null;
  const postal = record(report.mechanical.accepted_postal_addresses[0]);
  const postalCountries = Array.isArray(postal?.possible_country_codes)
    ? postal.possible_country_codes.filter((item): item is string => typeof item === "string")
    : [];
  const eu = record(report.mechanical.eu_status);
  const outsideEu = Array.isArray(eu?.outside_eu) ? eu.outside_eu : [];
  const insideEu = Array.isArray(eu?.inside_eu) ? eu.inside_eu : [];
  return {
    candidateName: value(report.base_analysis.profile.candidate_name),
    phone: text(phone?.value),
    phoneCountry: text(phone?.country_code),
    statedLocation: value(report.base_analysis.profile.declared_location),
    resolvedLocation: join([text(resolution?.canonical_name), text(resolution?.country_code)]),
    postalCode: text(postal?.value),
    postalCountry: postalCountries.length === 1 ? postalCountries[0] : null,
    euStatus: outsideEu.length ? "outside" : insideEu.length ? "inside" : null,
    education: report.base_analysis.education.filter((item) => item.status === "accepted").map(educationRecord),
    employment: report.base_analysis.employment.filter((item) => item.status === "accepted").map(employmentRecord),
  };
}

export function adaptReportInterface(report: AnalysisReport, language: ReportLanguage): ReportInterface {
  const copy = localized(language);
  const review = report.base_analysis.review;
  const attention: ReportFinding[] = [
    ...review.conflicts.map((item, index) => finding(`conflict-${index}`, item, copy.conflict, copy.conflictWhy, copy.conflictCheck)),
    ...review.coverage_gaps.map((item, index) => finding(`gap-${index}`, item, copy.gap, copy.gapWhy, copy.gapCheck)),
    ...[...report.base_analysis.employment, ...report.base_analysis.education]
      .filter((item) => item.status === "ambiguous" || item.relation_status === "ambiguous")
      .map((item) => ({
        id: `ambiguous-${item.id}`,
        whatWeFound: copy.ambiguous,
        whyItMatters: copy.ambiguousWhy,
        whatToCheck: copy.ambiguousCheck,
        evidence: fieldEvidence(item),
      })),
    ...report.mechanical.comparisons
      .filter((item) => record(item)?.relationship === "different")
      .map((item, index) => finding(`comparison-different-${index}`, item, copy.mismatch, copy.mismatchWhy, copy.mismatchCheck)),
    ...report.mechanical.email_findings
      .map((item, index) => finding(`email-${index}`, item, copy.emailTypo, copy.emailTypoWhy, copy.emailTypoCheck)),
  ];

  const worthKnowing: ReportFinding[] = [
    ...Object.entries(report.base_analysis.pass_statuses)
      .filter(([, pass]) => pass.status !== "completed")
      .map(([name, pass]) => finding(`pass-${name}`, pass, `${readable(name)}: ${pass.status}`, copy.incompleteWhy, copy.incompleteCheck)),
    ...review.added_profile_fields.map((name) => finding(`added-profile-${name}`, null, `${copy.added} (${readable(name)})`, copy.addedWhy, copy.addedCheck)),
    ...review.added_candidate_ids.map((id) => finding(`added-candidate-${id}`, null, copy.added, copy.addedWhy, copy.addedCheck)),
    ...review.merged_ids.map((ids, index) => finding(`merge-${index}`, null, `${copy.changed} (${ids.join(", ")})`, copy.changedWhy, copy.changedCheck)),
    ...review.relation_corrections.map((item, index) => finding(`relation-${index}`, item, copy.changed, copy.changedWhy, copy.changedCheck)),
  ];

  const remaining: ReportFinding[] = [
    ...review.rejected.map((item, index) => finding(`rejected-${index}`, item, copy.rejected, copy.rejectedWhy, copy.rejectedCheck)),
    ...report.mechanical.comparisons
      .filter((item) => record(item)?.relationship === "same")
      .map((item, index) => finding(`comparison-same-${index}`, item, copy.match, copy.matchWhy, copy.matchCheck)),
  ];

  return { attention, worthKnowing, remaining, overview: overview(report) };
}
