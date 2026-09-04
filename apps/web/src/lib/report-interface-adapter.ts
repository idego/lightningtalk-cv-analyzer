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
  searchSubject: string | null;
  searchContext: string | null;
  needsReview?: boolean;
};

export type ReportOverview = {
  candidateName: string | null;
  phone: string | null;
  phoneCountry: string | null;
  statedLocation: string | null;
  resolvedLocation: string | null;
  postalCode: string | null;
  postalCountry: string | null;
  postalConsistency: "consistent" | "mismatch" | null;
  euStatus: "inside" | "outside" | null;
  education: OverviewRecord[];
  employment: OverviewRecord[];
  attentionRecords: OverviewRecord[];
  educationStatus?: string;
  employmentStatus?: string;
};

export type ReportInterface = {
  attention: ReportFinding[];
  worthKnowing: ReportFinding[];
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
  return evidenceList(item?.evidence);
}

function evidenceList(input: unknown): Evidence[] {
  if (!Array.isArray(input)) return [];
  return uniqueEvidence(input.flatMap((entry) => {
    const evidence = record(entry);
    const sourceId = text(evidence?.source_id);
    const excerpt = text(evidence?.excerpt);
    return sourceId && excerpt ? [{
      source_id: sourceId,
      excerpt,
      page_number: typeof evidence?.page_number === "number" ? evidence.page_number : null,
    }] : [];
  }));
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

function description(input: unknown, fallback: string): string {
  const item = record(input);
  return text(item?.summary) ?? fallback;
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
    whatWeFound: description(input, fallback),
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
    linkedinMissing: "Nie znaleziono dopasowanego profilu LinkedIn w ograniczonym wyszukiwaniu.",
    linkedinMissingWhy: "Brak wyniku z ograniczonego wyszukiwania nie oznacza, że profil nie istnieje.",
    linkedinMissingCheck: "Wyszukaj profil ręcznie, używając danych kandydata z CV.",
    outsideEu: "Informacje lokalizacyjne wskazują poza UE.",
    outsideEuWhy: "To informacyjna klasyfikacja podanych danych; nie określa fizycznego pobytu, narodowości ani prawa do pracy.",
    outsideEuCheck: "Potwierdź deklarowaną lokalizację i numer telefonu bezpośrednio z kandydatem.",
    declaredSource: "deklarowana lokalizacja",
    phoneSource: "prefiks telefonu",
    locationResolved: "GeoNames rozpoznał deklarowane miasto i kraj.",
    locationAmbiguous: "Deklarowane miasto jest niejednoznaczne w indeksie GeoNames.",
    locationUnresolved: "Deklarowane miasto nie zostało potwierdzone w ograniczonym indeksie GeoNames.",
    locationMismatch: "Deklarowane miasto i kraj wskazują na różne kraje w GeoNames.",
    locationWhy: "Rozpoznanie dotyczy zgodności tekstu CV z ograniczonym indeksem, nie miejsca pobytu.",
    locationCheck: "Sprawdź pisownię miasta i kraju w CV oraz potwierdź je z kandydatem.",
    postalResolved: "Kod pocztowy jest przypisany do deklarowanego miasta i kraju w indeksie offline.",
    postalMismatch: "Kod pocztowy jest przypisany do innego miasta w skonfigurowanym indeksie offline.",
    postalUnresolved: "Kod pocztowy nie został potwierdzony dla deklarowanego miasta i kraju w ograniczonym indeksie offline.",
    postalUnavailable: "Walidacja kodu pocztowego jest niedostępna, ponieważ indeks pocztowy nie jest skonfigurowany.",
    postalWhy: "Walidacja obejmuje tylko powiązany rekord adresowy poparty dowodem z CV.",
    postalCheck: "Sprawdź kod pocztowy, miasto i kraj jako jeden adres.",
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
    linkedinMissing: "No matching LinkedIn profile was found by the limited search.",
    linkedinMissingWhy: "No result from a limited search does not mean that a profile does not exist.",
    linkedinMissingCheck: "Search manually using the candidate details stated in the CV.",
    outsideEu: "Location information points outside the EU.",
    outsideEuWhy: "This only classifies the supplied information; it does not establish physical residence, nationality, or right to work.",
    outsideEuCheck: "Confirm the stated location and phone number directly with the candidate.",
    declaredSource: "declared location",
    phoneSource: "phone prefix",
    locationResolved: "GeoNames resolved the declared city and country.",
    locationAmbiguous: "The declared city is ambiguous in the GeoNames index.",
    locationUnresolved: "The declared city was not confirmed in the limited GeoNames index.",
    locationMismatch: "The declared city and country point to different countries in GeoNames.",
    locationWhy: "This checks CV text against a limited index; it does not establish physical residence.",
    locationCheck: "Review the city and country spelling in the CV and confirm them with the candidate.",
    postalResolved: "The postal code is assigned to the declared city and country in the offline index.",
    postalMismatch: "The postal code is assigned to a different city in the configured offline index.",
    postalUnresolved: "The postal code was not confirmed for the declared city and country in the limited offline index.",
    postalUnavailable: "Postal-code validation is unavailable because the postal index is not configured.",
    postalWhy: "Validation covers only an evidence-supported postal code related to one declared address record.",
    postalCheck: "Review the postal code, city, and country as one address.",
  };
}

function uniqueEvidence(items: Evidence[]): Evidence[] {
  return [...new Map(items.map((item) => [
    `${item.source_id}:${item.excerpt}`,
    item,
  ])).values()];
}

function findingFromEvidence(
  id: string,
  whatWeFound: string,
  whyItMatters: string,
  whatToCheck: string,
  evidence: Evidence[],
): ReportFinding {
  return { id, whatWeFound, whyItMatters, whatToCheck, evidence: uniqueEvidence(evidence) };
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
      dateRange(item.start_date, item.end_date),
      value(item.location),
    ]),
    searchSubject: value(item.institution),
    searchContext: value(item.program),
    needsReview: item.status === "ambiguous",
  };
}

function employmentRecord(item: AnalysisReport["base_analysis"]["employment"][number]): OverviewRecord {
  return {
    id: item.id,
    value: value(item.role) ?? value(item.relationship_type) ?? value(item.organization) ?? "Employment entry",
    detail: join([
      dateRange(item.start_date, item.end_date),
      value(item.organization),
      value(item.location),
    ]),
    searchSubject: value(item.organization),
    searchContext: value(item.location),
    needsReview: item.status === "ambiguous",
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
  const postalValidation = record(postal?.validation);
  const suspectedIds = new Set(
    (report.base_analysis.review.annotations ?? [])
      .filter((item) => item.kind === "suspected_hallucination" || item.kind === "unsupported_evidence")
      .map((item) => item.record_id),
  );
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
    postalConsistency: postalValidation?.status === "resolved"
      ? "consistent"
      : postalValidation?.status === "mismatch"
        ? "mismatch"
        : null,
    euStatus: outsideEu.length ? "outside" : insideEu.length ? "inside" : null,
    education: report.base_analysis.education.filter((item) => !suspectedIds.has(item.id) && value(item.institution)).map(educationRecord),
    employment: report.base_analysis.employment.filter((item) => !suspectedIds.has(item.id)).map(employmentRecord),
    attentionRecords: [
      ...report.base_analysis.education.filter((item) => suspectedIds.has(item.id) && value(item.institution)).map(educationRecord),
      ...report.base_analysis.employment.filter((item) => suspectedIds.has(item.id)).map(employmentRecord),
    ],
    educationStatus: report.base_analysis.pass_statuses.education?.section_status,
    employmentStatus: report.base_analysis.pass_statuses.employment?.section_status,
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
  ].join(":"))
    .filter((item) => firstEvidence(item).length > 0);
  const coverageGaps = unique(review.coverage_gaps.map(record).filter((item): item is UnknownRecord => Boolean(item)), (item) => [
    text(item.target),
    text(item.reason_code),
    countryList(item.source_block_ids),
  ].join(":"))
    .filter((item) => {
      const reasonCode = text(item.reason_code) ?? "";
      return !/^(?:invalid|unknown|unsafe|reviewer)(?:_|$)/.test(reasonCode)
        && firstEvidence(item).length > 0;
    });
  const comparisonEvidence = uniqueEvidence([
    ...(report.base_analysis.profile.declared_location?.evidence ?? []),
    ...report.mechanical.phones.flatMap((item) => evidenceFrom(item)),
  ]);
  const location = report.mechanical.location_resolution
    .map(record)
    .find((item) => item?.subject === "declared_location") ?? null;
  const locationEvidence = evidenceFrom(location);
  const locationStatus = text(location?.status);
  const cityCountryRelationship = text(location?.city_country_relationship);
  const locationFinding = locationStatus
    && locationStatus !== "unavailable"
    && locationEvidence.length > 0
    ? findingFromEvidence(
        `location-${locationStatus}-${cityCountryRelationship}`,
        cityCountryRelationship === "different"
          ? copy.locationMismatch
          : locationStatus === "resolved"
            ? copy.locationResolved
            : locationStatus === "ambiguous"
              ? copy.locationAmbiguous
              : copy.locationUnresolved,
        copy.locationWhy,
        copy.locationCheck,
        locationEvidence,
      )
    : null;
  const linkedinNotFound = report.linkedin_discovery?.status === "completed"
    && report.linkedin_discovery.linkedin_not_found;
  const linkedinEvidence = report.base_analysis.profile.candidate_name?.evidence ?? [];
  const linkedinFinding = linkedinNotFound && linkedinEvidence.length > 0
    ? findingFromEvidence(
        "linkedin-not-found",
        copy.linkedinMissing,
        copy.linkedinMissingWhy,
        copy.linkedinMissingCheck,
        linkedinEvidence,
      )
    : null;
  const attention: ReportFinding[] = [
    ...(linkedinFinding ? [linkedinFinding] : []),
    ...(locationFinding && cityCountryRelationship === "different" ? [locationFinding] : []),
    ...comparisons
      .filter((item) => item.relationship === "different")
      .map((_item, index) => findingFromEvidence(
        `comparison-different-${index}`,
        copy.mismatch,
        copy.mismatchWhy,
        copy.mismatchCheck,
        comparisonEvidence,
      )),
    ...emailFindings
      .map((item, index) => finding(`email-${index}`, { ...item, summary: [
        copy.emailTypo,
        text(item.observed_domain) && text(item.suggested_domain)
          ? `${text(item.observed_domain)} → ${text(item.suggested_domain)}`
          : null,
      ].filter(Boolean).join(" ") }, copy.emailTypo, copy.emailTypoWhy, copy.emailTypoCheck)),
  ];

  const worthKnowing: ReportFinding[] = [
    ...coverageGaps.map((item, index) => finding(
      `gap-${index}`,
      { ...item, summary: `${copy.gap} (${text(item.target) ?? "CV"})` },
      copy.gap,
      copy.gapWhy,
      copy.gapCheck,
    )),
    ...(locationFinding && cityCountryRelationship !== "different" ? [locationFinding] : []),
  ];

  return { attention, worthKnowing, overview: overview(report) };
}
