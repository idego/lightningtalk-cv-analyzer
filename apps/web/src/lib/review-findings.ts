import type {
  AIAnalysis,
  AnalysisReport,
  Band,
  ReviewFlag,
} from "@/lib/analyze-types";
import { isSelfEmploymentLabel } from "./relationship-labels.js";

type CompletedResearchPatch = Partial<Pick<
  AnalysisReport,
  "company_research" | "education_research" | "linkedin_discovery"
>>;

export function mergeCompletedResearch<T extends AnalysisReport>(
  report: T,
  patch: CompletedResearchPatch,
): T {
  return { ...report, ...patch };
}

type LocationConsistencyInput = Pick<
  AnalysisReport,
  "band" | "score" | "signal_count" | "supporting_count" | "conflicting_count"
>;

export function locationConsistencyPresentation(
  report: LocationConsistencyInput,
) {
  if (report.signal_count === 0 || report.band === "gray") {
    return {
      status: "Insufficient evidence",
      description: "Not enough independent details. This does not verify the candidate's location.",
    };
  }
  if (report.conflicting_count > 0) {
    return {
      status: "Some details conflict",
      description: "At least one detail points to another country. This does not verify the candidate's location.",
    };
  }
  return {
    status: "Details agree",
    description: "The available details point to the same country. This does not verify the candidate's location.",
  };
}

export function historyLocationSummary(band: Band) {
  if (band === "gray") {
    return null;
  }
  if (band === "green") {
    return "Location consistency check: available details agree.";
  }
  return "Location consistency check: some details conflict.";
}

function countryLabel(countryCode: string) {
  const code = countryCode.toUpperCase();
  const name = new Intl.DisplayNames(["en"], { type: "region" }).of(code);
  return name && name !== code ? `${name} (${code})` : code;
}

export function structuredFactLines(
  report: Pick<AnalysisReport, "deterministic" | "ai_analysis">,
) {
  const lines: string[] = [];
  const seen = new Set<string>();
  const add = (line: string) => {
    const normalized = line.trim().toLocaleLowerCase();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    lines.push(line);
  };

  const personPostalCandidateIds = new Set(
    report.deterministic.facts
      .filter((fact) => fact.kind === "postal_country" && fact.subject === "person")
      .flatMap((fact) => fact.source_candidate_ids),
  );
  for (const candidate of report.deterministic.candidates) {
    if (candidate.subject !== "person") continue;
    if (candidate.kind === "phone") add(`Phone: ${candidate.value}`);
    if (candidate.kind === "explicit_location") {
      add(`Stated location: ${candidate.value}`);
    }
  }
  for (const candidate of report.deterministic.candidates) {
    if (candidate.kind === "postal" && personPostalCandidateIds.has(candidate.id)) {
      add(`Postal code: ${candidate.value}`);
    }
  }
  for (const fact of report.deterministic.facts) {
    if (fact.subject !== "person") continue;
    if (fact.kind === "phone_country") {
      add(`Phone country: ${countryLabel(fact.value)}`);
    }
    if (fact.kind === "postal_country") {
      add(`Postal country: ${countryLabel(fact.value)}`);
    }
    if (fact.kind === "claimed_location") {
      const location = fact.resolved_name ?? fact.value;
      add(`Resolved location: ${location}${fact.value ? ` (${fact.value})` : ""}`);
    }
  }
  if (report.deterministic.observations.some(
    (observation) => observation.kind === "combined_location_outside_eu",
  )) {
    add("EU status: Outside the EU");
  }
  if (report.deterministic.observations.some(
    (observation) => observation.kind === "combined_location_inside_eu",
  )) {
    add("EU status: Inside the EU");
  }

  const claim = report.deterministic.facts.find(
    (fact) => fact.kind === "claimed_location" && fact.subject === "person",
  );
  const comparisonValues = (report.deterministic.scoring_signals ?? [])
    .filter((signal) => signal.kind === "phone_country" || signal.kind === "postal_country")
    .map((signal) => signal.value);
  if (claim && comparisonValues.length > 0) {
    add(
      comparisonValues.every((value) => value === claim.value)
        ? "Location consistency: Available deterministic details agree"
        : "Location consistency: Available deterministic details conflict",
    );
  }

  const contactLabels = {
    candidate_name: "Candidate name",
    phone: "Phone",
    stated_location: "Stated location",
  } as const;
  for (const fact of report.ai_analysis.facts.contact) {
    add(`${contactLabels[fact.kind]}: ${fact.value}`);
  }
  for (const fact of report.ai_analysis.facts.education) {
    add([fact.institution, fact.program, fact.study_dates].filter(Boolean).join(" — "));
  }
  for (const fact of report.ai_analysis.facts.employment) {
    add([fact.organization, fact.role, fact.employment_dates].filter(Boolean).join(" — "));
  }
  return lines;
}

export function partitionReviewFlags(flags: ReviewFlag[]) {
  return {
    attention: flags.filter((flag) => flag.importance === "attention"),
    worthKnowing: flags.filter((flag) => flag.importance === "worth_knowing"),
    remaining: flags.filter((flag) => flag.importance === "remaining"),
  };
}

export type ResearchChecklistItem = {
  id: string;
  importance: "attention" | "worth_knowing";
  title: string;
  reason: string;
  source: "company" | "education" | "linkedin";
};

type ReportLanguage = "en" | "pl";

function researchReviewLimitation(language: ReportLanguage) {
  return language === "pl"
    ? "Sprawdź przytoczone źródła publiczne i potwierdź istotne informacje z kandydatem."
    : "Review the cited public sources and confirm relevant details with the candidate.";
}

export function researchChecklistItems(
  report: Pick<
    AnalysisReport,
    "company_research" | "education_research" | "linkedin_discovery"
  >,
  language: ReportLanguage = "en",
): ResearchChecklistItem[] {
  const items: ResearchChecklistItem[] = [];
  const isNonCompanySubject = (value: string) => {
    const normalized = value.toLocaleLowerCase().replace(/[^a-z]+/g, " ").trim();
    return isSelfEmploymentLabel(normalized);
  };

  for (const organization of report.company_research?.organizations ?? []) {
    const companyName = organization.query_subject;
    if (isNonCompanySubject(companyName)) continue;
    if (organization.existence !== "supported") {
      items.push({
        id: `company:${companyName}:existence-review`,
        importance: "attention",
        title: organization.existence === "conflicting"
          ? language === "pl"
            ? `Publiczne informacje o firmie ${companyName} są sprzeczne.`
            : `Public information about ${companyName} conflicts.`
          : language === "pl"
            ? `Nie potwierdzono firmy ${companyName} w wykonanych wyszukiwaniach.`
            : `${companyName} was not confirmed by the completed searches.`,
        reason: organization.uncertainty,
        source: "company",
      });
    }
  }

  for (const [credentialIndex, credential] of (report.education_research?.credentials ?? []).entries()) {
    const institution = credential.institution ?? credential.program ?? (language === "pl" ? "Wpis edukacyjny" : "An education entry");
    const addEducationField = (
      field: "institution" | "program" | "degree" | "certificate",
      value: string | null,
      status: "supported" | "mismatch" | "evidence_unavailable",
    ) => {
      if (!value) return;
      const label = language === "pl"
        ? ({ institution: "instytucję", program: "program", degree: "stopień", certificate: "certyfikat" }[field])
        : field === "institution" ? "institution" : field;
      const supported = status === "supported";
      // Detailed field-level outcomes remain in Education Research. The top
      // checklist only escalates an institution identity mismatch.
      if (supported || field !== "institution") return;
      items.push({
        id: `education:${credentialIndex}:${field}`,
        importance: supported ? "worth_knowing" : "attention",
        title: supported
          ? field === "institution"
            ? language === "pl"
              ? `Źródła publiczne potwierdzają istnienie ${value}.`
              : `Public sources support that ${value} exists.`
            : language === "pl"
              ? `Źródła publiczne potwierdzają ${label}: ${value}.`
              : `Public sources support the ${label} ${value}.`
          : status === "mismatch"
            ? language === "pl"
              ? `${label[0].toLocaleUpperCase()}${label.slice(1)} ${value} nie pasuje do zachowanych dowodów publicznych.`
              : `The ${label} ${value} does not match the retained public evidence.`
            : language === "pl"
              ? `Wykonane wyszukiwania nie potwierdziły ${label}: ${value}.`
              : `The completed searches did not confirm the ${label} ${value}.`,
        reason: field === "institution" && supported
          && [credential.city, credential.country].filter(Boolean).length
          ? language === "pl"
            ? `Instytucję zlokalizowano w ${[credential.city, credential.country].filter(Boolean).join(", ")}.`
            : `The institution was located in ${[credential.city, credential.country].filter(Boolean).join(", ")}.`
          : credential.uncertainty,
        source: "education",
      });
    };
    addEducationField("institution", credential.institution, credential.institution_exists);
    addEducationField("program", credential.program, credential.program_exists);
    addEducationField("degree", credential.degree, credential.degree_exists);
    addEducationField("certificate", credential.certificate, credential.certificate_exists);
    if (credential.accreditation_status && credential.accreditation_status !== "established") {
      items.push({
        id: `education:${credentialIndex}:accreditation`,
        importance: "attention",
        title: credential.accreditation_status === "not_established"
            ? language === "pl"
              ? `Wykonane wyszukiwania nie potwierdziły akredytacji dla ${institution}.`
              : `The completed searches did not establish accreditation for ${institution}.`
            : language === "pl"
              ? `Nie udało się potwierdzić akredytacji dla ${institution}.`
              : `Accreditation for ${institution} could not be confirmed.`,
        reason: credential.uncertainty,
        source: "education",
      });
    }
    if (credential.location_difference_for_review) {
      items.push({
        id: `education:${credentialIndex}:location`,
        importance: "attention",
        title: language === "pl"
          ? `Lokalizacja ${institution} wymaga sprawdzenia.`
          : `The location of ${institution} needs review.`,
        reason: credential.location_difference_for_review,
        source: "education",
      });
    }
  }

  const discovery = report.linkedin_discovery;
  if (discovery?.linkedin_not_found) {
    items.push({
      id: "linkedin:not-found",
      importance: "attention",
      title: language === "pl"
        ? "Wykonane wyszukiwania nie zachowały pasującego profilu LinkedIn."
        : "The completed searches did not retain a matching LinkedIn profile.",
      reason: discovery.not_found_caveat,
      source: "linkedin",
    });
  }
  return items;
}

const OUTSIDE_EU_CATEGORIES = new Set([
  "phone_outside_eu",
  "stated_location_outside_eu",
  "combined_location_outside_eu",
  "education_outside_eu",
]);

function joinList(items: string[]) {
  if (items.length < 2) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items.at(-1)}`;
}

function groupOutsideEuFlags(flags: ReviewFlag[]): ReviewFlag[] {
  const outsideEu = flags.filter((flag) => OUTSIDE_EU_CATEGORIES.has(flag.category));
  const combinedLocation = outsideEu.some((flag) => flag.category === "combined_location_outside_eu");
  const sources = [
    outsideEu.some((flag) => flag.category === "stated_location_outside_eu") || combinedLocation
      ? "stated location"
      : null,
    outsideEu.some((flag) => flag.category === "phone_outside_eu") || combinedLocation
      ? "phone number"
      : null,
    outsideEu.some((flag) => flag.category === "education_outside_eu")
      ? "education"
      : null,
  ].filter((source): source is string => Boolean(source));

  if (sources.length < 2) return flags;

  const evidence = outsideEu.flatMap((flag) => flag.evidence).filter((item, index, all) =>
    all.findIndex((candidate) =>
      candidate.page_id === item.page_id
      && candidate.line_id === item.line_id
      && candidate.excerpt === item.excerpt
    ) === index,
  );
  const summary: ReviewFlag = {
    id: "outside-eu:summary",
    source: "code",
    authority: "code",
    category: "outside_eu_summary",
    status: "observed",
    importance: "worth_knowing",
    confidence: "combined",
    observation: `The ${joinList(sources)} ${sources.length === 2 ? "both" : "all"} point outside the EU.`,
    reason: "These details agree. They do not show nationality, residence, or work permission.",
    limitation: "Confirm the current location and work permission only when the role requires it.",
    evidence,
  };
  const duplicateIds = new Set(outsideEu.map((flag) => flag.id));
  if (combinedLocation) {
    for (const flag of flags) {
      if (flag.category === "phone_country" && flag.importance === "worth_knowing") {
        duplicateIds.add(flag.id);
      }
    }
  }
  const firstDuplicateIndex = flags.findIndex((flag) => duplicateIds.has(flag.id));
  return flags.flatMap((flag, index) => {
    if (index === firstDuplicateIndex) return [summary];
    return duplicateIds.has(flag.id) ? [] : [flag];
  });
}

export function recruiterReviewFlags(
  report: Pick<AnalysisReport, "checklist" | "company_research" | "education_research" | "linkedin_discovery">,
  language: ReportLanguage = "en",
): ReviewFlag[] {
  const researchFlags: ReviewFlag[] = researchChecklistItems(report, language).map((item) => ({
    id: item.id,
    source: "research",
    authority: "ai",
    category: `${item.source}_research`,
    status: item.importance === "attention" ? "review" : "informational",
    importance: item.importance,
    confidence: "research",
    observation: item.title,
    reason: item.reason,
    limitation: researchReviewLimitation(language),
    evidence: [],
  }));
  const seen = new Set<string>();
  const flags = [...report.checklist.flags, ...researchFlags].filter((flag) => {
    if (flag.category.startsWith("link_")) return false;
    if (seen.has(flag.id)) return false;
    seen.add(flag.id);
    return true;
  });
  return groupOutsideEuFlags(flags);
}

export type ReviewCopy = {
  whatWeFound: string;
  whyItMatters: string;
  whatToCheck: string;
};

const deterministicTemplates: Record<string, (flag: ReviewFlag) => ReviewCopy> = {
  phone_country: (flag) => {
    const observed = flag.presentation_context?.observed ?? flag.observation;
    const claimed = flag.presentation_context?.claimed;
    const conflicts = flag.presentation_context?.direction === "conflicts";
    return {
      whatWeFound: claimed
        ? `The phone points to ${observed}. The stated location is ${claimed}.`
        : `The phone points to ${observed}.`,
      whyItMatters: conflicts
        ? "These details point to different countries. This does not prove where the candidate lives."
        : "These details point to the same country. This does not verify the candidate's location.",
      whatToCheck: "Confirm the phone number and the candidate's current location.",
    };
  },
  address_postal: (flag) => {
    const observed = flag.presentation_context?.observed ?? flag.observation;
    const claimed = flag.presentation_context?.claimed;
    const conflicts = flag.presentation_context?.direction === "conflicts";
    return {
      whatWeFound: claimed
        ? `The postal code format points to ${observed}. The stated location is ${claimed}.`
        : `The postal code format points to ${observed}.`,
      whyItMatters: conflicts
        ? "These details point to different countries. Postal formats can be shared, so this is only a consistency check."
        : "These details point to the same country. Postal formats can be shared, so this is only a consistency check.",
      whatToCheck: "Confirm the full address only when it is relevant to the role.",
    };
  },
  possible_email_domain_typo: (flag) => ({
    whatWeFound: `The email domain may contain a typo: ${flag.presentation_context?.observed ?? flag.observation}.`,
    whyItMatters: "A typo can prevent contact. It does not mean that the address is false.",
    whatToCheck: "Confirm the email address with the candidate.",
  }),
  mixed_eu_location_evidence: () => ({
    whatWeFound: "The stated location and phone country are on different sides of the EU boundary.",
    whyItMatters: "This may need context. It does not show nationality, residence, or work permission.",
    whatToCheck: "Confirm the current location and ask for work-permission facts only when the role requires them.",
  }),
  phone_outside_eu: (flag) => ({
    whatWeFound: `The phone points outside the EU: ${flag.presentation_context?.observed ?? flag.observation}.`,
    whyItMatters: "A phone country does not show nationality, residence, or work permission.",
    whatToCheck: "Confirm that the phone number is current.",
  }),
  stated_location_outside_eu: (flag) => ({
    whatWeFound: `The CV states a location outside the EU: ${flag.presentation_context?.observed ?? flag.observation}.`,
    whyItMatters: "A stated location does not show nationality or work permission.",
    whatToCheck: "Confirm the candidate's current location.",
  }),
  small_locality_outside_eu: (flag) => ({
    whatWeFound: `The stated location is a small locality outside the EU: ${flag.presentation_context?.observed ?? flag.observation}.`,
    whyItMatters: "This is useful context for manual review. Locality size does not show nationality, residence, work permission, or fraud.",
    whatToCheck: "Confirm the current location when it is relevant to the role.",
  }),
  combined_location_outside_eu: () => ({
    whatWeFound: "The stated location and phone both point outside the EU.",
    whyItMatters: "These details do not prove nationality, residence, or work permission.",
    whatToCheck: "Confirm the current location and collect work-permission facts directly when needed.",
  }),
  outside_eu_summary: (flag) => ({
    whatWeFound: flag.observation,
    whyItMatters: flag.reason,
    whatToCheck: flag.limitation ?? "Confirm the current location only when it is relevant to the role.",
  }),
  combined_location_inside_eu: () => ({
    whatWeFound: "The stated location and phone both point to countries in the EU.",
    whyItMatters: "These details are consistent, but they do not prove nationality, residence, or work permission.",
    whatToCheck: "Confirm the current location and work permission only when the role requires it.",
  }),
  right_to_work: (flag) => ({
    whatWeFound: `The CV includes a work-permission statement: ${flag.presentation_context?.observed ?? flag.observation}.`,
    whyItMatters: "The statement is useful context, but it is not proof.",
    whatToCheck: "Confirm work permission directly if the role requires it.",
  }),
  postal_compatibility: (flag) => ({
    whatWeFound: `The CV includes this postal detail: ${flag.presentation_context?.observed ?? flag.observation}.`,
    whyItMatters: "Postal formats can be shared by several countries. This detail is not scored.",
    whatToCheck: "Check the full address only when it is relevant to the role.",
  }),
  national_id: () => ({
    whatWeFound: "The CV contains a national ID value. The value was hidden before analysis.",
    whyItMatters: "This is sensitive personal data. It is not a risk signal and is not scored.",
    whatToCheck: "Do not request or copy the value unless an approved process requires it.",
  }),
  small_locality_not_evaluated: () => ({
    whatWeFound: "The system did not assess the size or typicality of the stated place.",
    whyItMatters: "There is no approved rule for this check. No positive or negative conclusion is available.",
    whatToCheck: "Confirm the stated location only when it is relevant to the role.",
  }),
};

export function presentReviewFlag(
  flag: ReviewFlag,
  reportLanguage: "en" | "pl" = "en",
): ReviewCopy {
  if (flag.source === "code" && reportLanguage === "en") {
    const template = deterministicTemplates[flag.category];
    if (template) return template(flag);
    return {
      whatWeFound: flag.observation,
      whyItMatters: "This detail may need context. It does not prove a problem and is not a hiring decision.",
      whatToCheck: "Check the cited CV text with the candidate.",
    };
  }
  if (flag.source === "ai" && flag.category === "timeline_overlap" && reportLanguage === "en") {
    return {
      whatWeFound: simplifyTimelineOverlap(flag.observation),
      whyItMatters: "The roles may be parallel, part-time, or contract work. The overlap is not proof of a problem.",
      whatToCheck: "Ask whether both roles were active at the same time and how the work was arranged.",
    };
  }
  if (flag.source === "ai" && flag.category === "education_outside_eu" && reportLanguage === "en") {
    return {
      whatWeFound: "The CV lists education outside the EU.",
      whyItMatters: "This is useful context when reviewing the candidate's education history. It does not establish nationality or current location.",
      whatToCheck: "Verify the institution, programme, dates, and this period of the candidate's history.",
    };
  }
  return {
    whatWeFound: flag.observation,
    whyItMatters: flag.reason,
    whatToCheck: flag.limitation ?? "Check the cited CV text with the candidate.",
  };
}

function simplifyTimelineOverlap(observation: string): string {
  const detail = observation
    .replace(/^The dated (?:employment )?records show overlapping periods:\s*/i, "")
    .replace(/,\s+and\s+/i, ". ")
    .trim();
  if (!detail || detail === observation.trim()) return observation;
  return `The CV shows overlapping roles. ${detail}`;
}

export function aiStatusMessage(
  status: AIAnalysis["status"],
  reason: AIAnalysis["failure_reason"],
  language: "en" | "pl" = "en",
) {
  if (status === "pending") {
    return language === "pl"
      ? "Dane sprawdzone kodem są gotowe. Dodajemy analizę AI…"
      : "Code-checked facts are ready. Adding AI analysis…";
  }
  if (status === "disabled") {
    return language === "pl"
      ? "Analiza AI jest wyłączona. Sprawdź stan systemu w Ustawieniach."
      : "AI analysis is disabled. Check System health in Settings.";
  }
  if (status === "failed" && reason === "refusal") {
    return language === "pl"
      ? "Model odmówił analizy tego dokumentu."
      : "The model declined to analyze this document.";
  }
  if (status === "failed") {
    return language === "pl"
      ? "Nie udało się wykonać analizy AI. Spróbuj ponownie lub sprawdź stan systemu."
      : "AI analysis failed. Try again or check System health.";
  }
  return null;
}
