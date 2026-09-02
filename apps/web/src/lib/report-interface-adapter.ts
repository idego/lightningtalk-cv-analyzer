import type {
  AnalysisReport,
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
    gap: "Nie udało się bezpiecznie uzupełnić informacji w CV.",
    gapWhy: "Brak danych ogranicza kompletność raportu.",
    gapCheck: "Sprawdź brakującą informację bezpośrednio w CV.",
    mismatch: "Deklarowany kraj i kraj numeru telefonu są różne.",
    mismatchWhy: "To sygnał niespójności, a nie dowód miejsca pobytu.",
    mismatchCheck: "Sprawdź deklarowaną lokalizację i numer telefonu w CV.",
    emailTypo: "Adres e-mail może zawierać literówkę w popularnej domenie.",
    emailTypoWhy: "Literówka może uniemożliwić kontakt z kandydatem.",
    emailTypoCheck: "Porównaj adres z oryginalnym CV przed użyciem.",
    match: "Deklarowany kraj i kraj numeru telefonu są zgodne.",
    matchWhy: "To informacyjny sygnał spójności, nie weryfikacja lokalizacji.",
    matchCheck: "Nie traktuj tego sygnału jako dowodu miejsca pobytu.",
  } : {
    gap: "Information in the CV could not be added safely.",
    gapWhy: "Missing data limits the completeness of the report.",
    gapCheck: "Review the missing information directly in the CV.",
    mismatch: "The declared country and phone country differ.",
    mismatchWhy: "This is a consistency signal, not proof of residence.",
    mismatchCheck: "Review the declared location and phone number in the CV.",
    emailTypo: "The email address may contain a typo in a common provider domain.",
    emailTypoWhy: "A typo may prevent contact with the candidate.",
    emailTypoCheck: "Compare the address with the original CV before using it.",
    match: "The declared country and phone country are consistent.",
    matchWhy: "This is an informational consistency signal, not location verification.",
    matchCheck: "Do not treat this signal as proof of residence.",
  };
}

function join(values: Array<string | null | undefined>): string | null {
  const result = values.filter((item): item is string => Boolean(item)).join(" · ");
  return result || null;
}

function dateRange(start: SupportedField | null, end: SupportedField | null): string | null {
  return join([value(start), value(end)]);
}

function educationRecord(item: AnalysisReport["base_analysis"]["education"][number]): OverviewRecord {
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

function employmentRecord(item: AnalysisReport["base_analysis"]["employment"][number]): OverviewRecord {
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
  const unique = (items: UnknownRecord[], key: (item: UnknownRecord) => string) => [
    ...new Map(items.map((item) => [key(item), item])).values(),
  ];
  const countryList = (value: unknown) => Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string").join(", ")
    : "";
  const comparisons = unique(report.mechanical.comparisons.map(record).filter((item): item is UnknownRecord => Boolean(item)), (item) => [
    text(item.kind),
    text(item.relationship),
    countryList(item.declared_country_codes),
    countryList(item.phone_country_codes),
  ].join(":"));
  const emailFindings = unique(report.mechanical.email_findings.map(record).filter((item): item is UnknownRecord => Boolean(item)), (item) => [
    text(item.kind),
    text(item.observed_domain),
    text(item.suggested_domain),
  ].join(":"));
  const coverageGaps = unique(review.coverage_gaps.map(record).filter((item): item is UnknownRecord => Boolean(item)), (item) => [
    text(item.target),
    text(item.reason_code),
    countryList(item.source_block_ids),
  ].join(":"))
    .filter((item) => {
      const reasonCode = text(item.reason_code) ?? "";
      return !/^(?:invalid|unknown|unsafe|reviewer)(?:_|$)/.test(reasonCode);
    });
  const attention: ReportFinding[] = [
    ...comparisons
      .filter((item) => item.relationship === "different")
      .map((item, index) => finding(`comparison-different-${index}`, { ...item, summary: copy.mismatch }, copy.mismatch, copy.mismatchWhy, copy.mismatchCheck)),
    ...emailFindings
      .map((item, index) => finding(`email-${index}`, { ...item, summary: [
        copy.emailTypo,
        text(item.observed_domain) && text(item.suggested_domain)
          ? `${text(item.observed_domain)} → ${text(item.suggested_domain)}`
          : null,
      ].filter(Boolean).join(" ") }, copy.emailTypo, copy.emailTypoWhy, copy.emailTypoCheck)),
  ];

  const worthKnowing: ReportFinding[] = coverageGaps.map((item, index) => finding(
    `gap-${index}`,
    item,
    copy.gap,
    copy.gapWhy,
    copy.gapCheck,
  ));

  const remaining: ReportFinding[] = [
    ...comparisons
      .filter((item) => item.relationship === "same")
      .map((item, index) => finding(`comparison-same-${index}`, { ...item, summary: copy.match }, copy.match, copy.matchWhy, copy.matchCheck)),
  ];

  return { attention, worthKnowing, remaining, overview: overview(report) };
}
