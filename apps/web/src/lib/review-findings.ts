import type { AIAnalysis, AnalysisReport, ReviewFlag } from "@/lib/analyze-types";

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
  combined_location_outside_eu: () => ({
    whatWeFound: "The stated location and phone both point outside the EU.",
    whyItMatters: "These details do not prove nationality, residence, or work permission.",
    whatToCheck: "Confirm the current location and collect work-permission facts directly when needed.",
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

export function aiValidationWarning(analysis: Pick<AIAnalysis, "validation_warnings">) {
  return analysis.validation_warnings.length
    ? analysis.validation_warnings[0]
    : null;
}

export function aiValidationState(
  analysis: Pick<AIAnalysis, "status" | "validation_warnings">,
) {
  return {
    warning: aiValidationWarning(analysis),
    showAcceptedOutput: analysis.status === "succeeded",
  };
}
