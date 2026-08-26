import assert from "node:assert/strict";
import test from "node:test";

import { aiStatusMessage, aiValidationState, aiValidationWarning, partitionReviewFlags, presentReviewFlag, structuredFactLines } from "./review-findings.ts";

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

test("surfaces partial AI validation without hiding valid output", () => {
  const warning = "Część danych nie została pokazana, ponieważ nie udało się potwierdzić ich w tekście CV.";
  assert.equal(aiValidationWarning({ validation_warnings: [warning] }), warning);
  assert.equal(aiValidationWarning({ validation_warnings: [] }), null);
  assert.deepEqual(aiValidationState({ status: "succeeded", validation_warnings: [warning] }), {
    warning,
    showAcceptedOutput: true,
  });
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
