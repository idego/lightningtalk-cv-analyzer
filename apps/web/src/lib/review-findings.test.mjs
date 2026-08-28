import assert from "node:assert/strict";
import test from "node:test";

import {
  aiStatusMessage,
  historyLocationSummary,
  locationConsistencyPresentation,
  mergeCompletedResearch,
  partitionReviewFlags,
  presentReviewFlag,
  recruiterReviewFlags,
  researchChecklistItems,
  structuredFactLines,
} from "./review-findings.ts";

const flag = (id, importance) => ({ id, importance });

test("partitions every flag into the recruiter-facing hierarchy", () => {
  const flags = [
    flag("a", "remaining"),
    flag("b", "attention"),
    flag("c", "worth_knowing"),
    flag("d", "remaining"),
  ];

  const grouped = partitionReviewFlags(flags);

  assert.deepEqual(grouped.attention.map((item) => item.id), ["b"]);
  assert.deepEqual(grouped.worthKnowing.map((item) => item.id), ["c"]);
  assert.deepEqual(grouped.remaining.map((item) => item.id), ["a", "d"]);
  assert.equal(
    grouped.attention.length + grouped.worthKnowing.length + grouped.remaining.length,
    flags.length,
  );
});

test("builds one recruiter checklist from completed research", () => {
  const items = researchChecklistItems({
    company_research: {
      organizations: [{
        query_subject: "Example Ltd", existence: "insufficient_evidence",
        official_website: null, uncertainty: "Only unrelated records were found.",
        limited_online_presence: true,
        limited_online_presence_reason: "No official company presence was retained.",
      }],
    },
    education_research: {
      credentials: [{
        institution: "Example University", program: null,
        institution_exists: "supported", city: "Hong Kong", country: "Hong Kong",
        uncertainty: "The institution is supported.",
        location_difference_for_review: "The CV states a different current country.",
      }],
    },
    linkedin_discovery: {
      linkedin_not_found: false,
      possible_profiles: [{
        profile_url: "https://www.linkedin.com/in/example",
        uncertainty: "Only the name is visible in public search results.",
        connection_completeness_flag: false,
      }],
    },
    linkedin_comparison: {
      comparisons: [{
        field: "education", status: "mismatch_for_review",
        summary: "The public profile lists a different university.",
      }],
    },
  });

  assert.deepEqual(items.map((item) => [item.source, item.importance, item.title]), [
    ["company", "attention", "Example Ltd was not confirmed by the completed searches."],
    ["education", "attention", "The location of Example University needs review."],
  ]);
});

test("does not surface legacy AI profile comparisons in the recruiter checklist", () => {
  const items = researchChecklistItems({
    company_research: null,
    education_research: null,
    linkedin_discovery: null,
    linkedin_comparison: {
      comparisons: [{
        field: "education",
        status: "mismatch_for_review",
        summary: "A legacy comparison result.",
      }],
    },
  });

  assert.deepEqual(items, []);
});

test("keeps field-level education details in the dedicated research section", () => {
  const items = researchChecklistItems({
    company_research: null,
    linkedin_discovery: null,
    education_research: {
      credentials: [{
        institution: "Example University",
        program: "Example Programme",
        degree: "Example Degree",
        certificate: "Example Certificate",
        institution_exists: "supported",
        program_exists: "mismatch",
        degree_exists: "evidence_unavailable",
        certificate_exists: "supported",
        dates: "2018-2020",
        accreditation_status: "not_established",
        city: "Example City",
        country: "Example Country",
        cv_consistency: "evidence_unavailable",
        location_difference_for_review: null,
        uncertainty: "Public sources were incomplete.",
        findings: [],
      }],
    },
  });

  assert.deepEqual(items.map((item) => [item.id, item.importance]), [
    ["education:0:accreditation", "attention"],
  ]);
});

test("merges code, AI and research into one deduplicated recruiter flag list", () => {
  const shared = {
    id: "code-1", source: "code", authority: "code", category: "phone_country",
    status: "agrees", importance: "worth_knowing", confidence: "deterministic",
    observation: "PL", reason: "The details agree.", limitation: null, evidence: [],
  };
  const report = {
    checklist: { flags: [shared, { ...shared }] },
    company_research: null,
    education_research: null,
    linkedin_discovery: {
      linkedin_not_found: true,
      not_found_caveat: "A bounded public search cannot prove that no profile exists.",
      possible_profiles: [],
    },
    linkedin_comparison: null,
  };

  const flags = recruiterReviewFlags(report);

  assert.deepEqual(flags.map((item) => item.id), ["code-1", "linkedin:not-found"]);
  assert.equal(flags[1].source, "research");
});

test("groups repeated outside-EU details into one recruiter finding", () => {
  const base = {
    source: "code", authority: "code", status: "observed",
    importance: "worth_knowing", confidence: "deterministic",
    reason: "Outside the EU.", limitation: null, evidence: [],
  };
  const outsideEuFlags = [
    { ...base, id: "phone-match", category: "phone_country", observation: "The phone and location agree." },
    { ...base, id: "location", category: "stated_location_outside_eu", observation: "Location outside the EU." },
    { ...base, id: "phone", category: "phone_outside_eu", observation: "Phone outside the EU." },
    { ...base, id: "combined", category: "combined_location_outside_eu", observation: "Both outside the EU." },
    { ...base, id: "education", source: "ai", authority: "ai", category: "education_outside_eu", observation: "Education outside the EU." },
  ];
  const linkedinFlag = { ...base, id: "linkedin", source: "ai", authority: "ai", category: "linkedin", observation: "3 profiles found." };

  const flags = recruiterReviewFlags({
    checklist: { flags: [...outsideEuFlags, linkedinFlag] },
    company_research: null,
    education_research: null,
    linkedin_discovery: null,
  });

  assert.deepEqual(flags.map((item) => item.id), ["outside-eu:summary", "linkedin"]);
  assert.deepEqual(presentReviewFlag(flags[0]), {
    whatWeFound: "The stated location, phone number, and education all point outside the EU.",
    whyItMatters: "These details agree. They do not show nationality, residence, or work permission.",
    whatToCheck: "Confirm the current location and work permission only when the role requires it.",
  });
});

test("keeps LinkedIn profile details out of the top recruiter checklist", () => {
  const base = {
    checklist: { flags: [] }, company_research: null, education_research: null,
    linkedin_comparison: null,
  };
  const profile = {
    profile_url: "https://www.linkedin.com/in/example",
    uncertainty: "Public details are limited.",
    photo_visible: "false",
    connection_completeness_flag: true,
  };

  const visible = recruiterReviewFlags({
    ...base,
    linkedin_discovery: { linkedin_not_found: false, not_found_caveat: "", possible_profiles: [profile] },
  });
  assert.deepEqual(visible, []);

  const unknown = recruiterReviewFlags({
    ...base,
    linkedin_discovery: { linkedin_not_found: false, not_found_caveat: "", possible_profiles: [{
      ...profile, photo_visible: "unknown", connection_completeness_flag: false,
    }] },
  });
  assert.deepEqual(unknown, []);
});

test("leaves multiple possible LinkedIn profiles in the dedicated section", () => {
  const possibleProfiles = [1, 2, 3].map((index) => ({
    profile_url: `https://www.linkedin.com/in/example-${index}`,
    uncertainty: `Public evidence for profile ${index} is limited.`,
    photo_visible: "unknown",
    connection_completeness_flag: false,
  }));

  const items = researchChecklistItems({
    company_research: null,
    education_research: null,
    linkedin_discovery: {
      linkedin_not_found: false,
      not_found_caveat: "",
      possible_profiles: possibleProfiles,
    },
    linkedin_comparison: null,
  });

  assert.deepEqual(items, []);
});

test("localizes frontend research checklist copy to Polish", () => {
  const items = researchChecklistItems({
    company_research: {
      organizations: [{
        query_subject: "Example",
        existence: "supported",
        official_website: "https://example.test",
        location: null,
        activity: null,
        operating_dates: null,
        relationship: null,
        company_pages: [],
        registries: [],
        confidence: "high",
        uncertainty: "Ograniczona pewność.",
        findings: [],
        limited_online_presence: false,
        limited_online_presence_reason: null,
      }],
    },
    education_research: null,
    linkedin_discovery: null,
  }, "pl");

  assert.deepEqual(items, []);
  assert.equal(
    recruiterReviewFlags({
      checklist: { flags: [] },
      company_research: null,
      education_research: null,
      linkedin_discovery: { linkedin_not_found: true, not_found_caveat: "Brak pewności.", possible_profiles: [] },
    }, "pl")[0].observation,
    "Wykonane wyszukiwania nie zachowały pasującego profilu LinkedIn.",
  );
});

test("describes disabled, refusal and technical failure without a verdict", () => {
  assert.match(aiStatusMessage("disabled", null), /disabled/i);
  assert.match(aiStatusMessage("failed", "refusal"), /declined/i);
  assert.match(aiStatusMessage("failed", "timeout"), /failed/i);
  assert.match(aiStatusMessage("disabled", null, "pl"), /wyłączona/i);
  assert.equal(aiStatusMessage("succeeded", null), null);
  assert.match(aiStatusMessage("pending", null), /adding AI/i);
});

test("shows deterministic facts before AI and merges AI facts afterward", () => {
  const baseReport = {
    deterministic: {
      candidates: [
        { kind: "phone", value: "+48 732 080 047", subject: "person" },
      ],
      facts: [
        { kind: "phone_country", value: "PL", subject: "person", resolved_name: null },
      ],
      observations: [],
    },
    ai_analysis: {
      facts: { contact: [], education: [], employment: [] },
    },
  };

  assert.deepEqual(structuredFactLines(baseReport), [
    "Phone: +48 732 080 047",
    "Phone country: Poland (PL)",
  ]);

  const enriched = structuredFactLines({
    ...baseReport,
    ai_analysis: {
      facts: {
        contact: [
          { kind: "phone", value: "+48 732 080 047" },
          { kind: "stated_location", value: "Opole, Poland" },
        ],
        education: [{ institution: "Example University", program: "Computer Science", study_dates: "2020-2024" }],
        employment: [{ organization: "Example Ltd", role: "Engineer", employment_dates: "2024-present" }],
      },
    },
  });

  assert.deepEqual(enriched, [
    "Phone: +48 732 080 047",
    "Phone country: Poland (PL)",
    "Stated location: Opole, Poland",
    "Example University — Computer Science — 2020-2024",
    "Example Ltd — Engineer — 2024-present",
  ]);
});

test("shows postal country, EU status and deterministic consistency", () => {
  const report = {
    deterministic: {
      candidates: [
        { id: "candidate:phone", kind: "phone", value: "+48 732 080 047", subject: "person" },
        { id: "candidate:postal", kind: "postal", value: "45-061", subject: "unknown" },
      ],
      facts: [
        { kind: "claimed_location", value: "PL", subject: "person", resolved_name: "Opole", source_candidate_ids: [] },
        { kind: "phone_country", value: "PL", subject: "person", resolved_name: null, source_candidate_ids: ["candidate:phone"] },
        { kind: "postal_country", value: "PL", subject: "person", resolved_name: null, source_candidate_ids: ["candidate:postal"] },
      ],
      observations: [{ kind: "combined_location_inside_eu" }],
      scoring_signals: [
        { kind: "phone_country", value: "PL" },
        { kind: "postal_country", value: "PL" },
      ],
    },
    ai_analysis: {
      facts: { contact: [], education: [], employment: [] },
    },
  };

  assert.deepEqual(structuredFactLines(report), [
    "Phone: +48 732 080 047",
    "Postal code: 45-061",
    "Resolved location: Opole (PL)",
    "Phone country: Poland (PL)",
    "Postal country: Poland (PL)",
    "EU status: Inside the EU",
    "Location consistency: Available deterministic details agree",
  ]);
});

test("uses plain code-owned copy without technical rule names", () => {
  const copy = presentReviewFlag({
    id: "code-1",
    source: "code",
    authority: "code",
    category: "phone_country",
    status: "conflicts",
    importance: "attention",
    confidence: "deterministic",
    observation: "PL",
    reason: "Aggregate explicitly person-owned phone country is compared with the code-owned claimed-location country",
    limitation: null,
    evidence: [],
    presentation_context: { observed: "PL", claimed: "Berlin, Germany", direction: "conflicts" },
  });

  assert.deepEqual(copy, {
    whatWeFound: "The phone points to PL. The stated location is Berlin, Germany.",
    whyItMatters: "These details point to different countries. This does not prove where the candidate lives.",
    whatToCheck: "Confirm the phone number and the candidate's current location.",
  });
  assert.doesNotMatch(JSON.stringify(copy), /phone_country|rule|extractor/i);
});

test("explains a postal-country comparison instead of showing a raw country code", () => {
  const copy = presentReviewFlag({
    id: "code-postal-1",
    source: "code",
    authority: "code",
    category: "address_postal",
    status: "supports",
    importance: "worth_knowing",
    confidence: "deterministic",
    observation: "PL",
    reason: "Technical scoring rationale",
    limitation: null,
    evidence: [],
    presentation_context: { observed: "PL", claimed: "Opole, Poland", direction: "supports" },
  });

  assert.deepEqual(copy, {
    whatWeFound: "The postal code format points to PL. The stated location is Opole, Poland.",
    whyItMatters: "These details point to the same country. Postal formats can be shared, so this is only a consistency check.",
    whatToCheck: "Confirm the full address only when it is relevant to the role.",
  });
});

test("explains timeline overlap without treating it as a problem", () => {
  const copy = presentReviewFlag({
    id: "ai-1", source: "ai", authority: "ai", category: "timeline_overlap",
    status: "unconfirmed", importance: "worth_knowing", confidence: "medium",
    observation: "Infuse and STDev overlap from May to September 2024.",
    reason: "The dated employment records overlap.", limitation: "The CV does not explain the arrangement.", evidence: [],
  });

  assert.match(copy.whyItMatters, /parallel, part-time, or contract/);
  assert.match(copy.whatToCheck, /both roles were active/);
  assert.doesNotMatch(JSON.stringify(copy), /timeline_overlap/);
});

test("splits a verbose overlap into short role and period statements", () => {
  const copy = presentReviewFlag({
    id: "ai-3", source: "ai", authority: "ai", category: "timeline_overlap",
    status: "unconfirmed", importance: "worth_knowing", confidence: "medium",
    observation: "The dated employment records show overlapping periods: Infuse (02/2024-09/2024) overlaps STDev (05/2024-10/2024), and Infuse overlaps SoftConstruct (10/2023-03/2024).",
    reason: "The dated records overlap.", limitation: "The work arrangement is not stated.", evidence: [],
  });
  assert.equal(copy.whatWeFound, "The CV shows overlapping roles. Infuse (02/2024-09/2024) overlaps STDev (05/2024-10/2024). Infuse overlaps SoftConstruct (10/2023-03/2024).");
});

test("keeps model-authored language when the report is Polish", () => {
  const copy = presentReviewFlag({
    id: "ai-2", source: "ai", authority: "ai", category: "timeline_overlap",
    status: "unconfirmed", importance: "worth_knowing", confidence: "medium",
    observation: "Dwie role nakładają się w czasie.", reason: "Daty zatrudnienia się pokrywają.",
    limitation: "CV nie opisuje organizacji pracy.", evidence: [],
  }, "pl");
  assert.equal(copy.whyItMatters, "Daty zatrudnienia się pokrywają.");
  assert.equal(copy.whatToCheck, "CV nie opisuje organizacji pracy.");
});

test("presents education outside the EU as neutral worth-knowing context", () => {
  const copy = presentReviewFlag({
    id: "ai-education-1",
    source: "ai",
    authority: "ai",
    category: "education_outside_eu",
    status: "observed",
    importance: "worth_knowing",
    confidence: "high",
    observation: "Technical model output.",
    reason: "Technical model reason.",
    limitation: "Technical model limitation.",
    evidence: [],
  });

  assert.deepEqual(copy, {
    whatWeFound: "The CV lists education outside the EU.",
    whyItMatters: "This is useful context when reviewing the candidate's education history. It does not establish nationality or current location.",
    whatToCheck: "Verify the institution, programme, dates, and this period of the candidate's history.",
  });
});

test("does not present a deterministic location match as a candidate score", () => {
  const presentation = locationConsistencyPresentation({
    band: "green",
    score: 100,
    signal_count: 2,
    supporting_count: 2,
    conflicting_count: 0,
  });

  assert.deepEqual(presentation, {
    status: "Details agree",
    description: "The available details point to the same country. This does not verify the candidate's location.",
  });
  assert.doesNotMatch(JSON.stringify(presentation), /100|green|candidate score/i);
});

test("describes stored analyses as location checks instead of verdicts", () => {
  assert.equal(
    historyLocationSummary("green"),
    "Location consistency check: available details agree.",
  );
  assert.equal(
    historyLocationSummary("red"),
    "Location consistency check: some details conflict.",
  );
  assert.equal(
    historyLocationSummary("gray"),
    null,
  );
});

test("merges newly completed research without dropping earlier report results", () => {
  const report = {
    analysis_id: "analysis-1",
    company_research: { organizations: [{ existence: "supported" }] },
    education_research: undefined,
  };
  const education = {
    credentials: [{ institution_exists: "supported", cv_consistency: "consistent" }],
  };

  const updated = mergeCompletedResearch(report, { education_research: education });

  assert.equal(updated.analysis_id, "analysis-1");
  assert.equal(updated.company_research, report.company_research);
  assert.equal(updated.education_research, education);
  assert.notEqual(updated, report);
});
