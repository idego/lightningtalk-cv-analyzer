import assert from "node:assert/strict";
import test from "node:test";

import { adaptReportInterface } from "./report-interface-adapter.ts";

function field(value, sourceId = "block-1") {
  return { value, status: "supported", evidence: [{ source_id: sourceId, excerpt: value }] };
}

function report() {
  return {
    contract_version: "base-analysis-v2",
    analysis_id: "analysis-1",
    strategy: { name: "docling-luna", version: "test" },
    source: { format: "pdf", sha256: "anonymous", identity: "anonymous", block_count: 1, conversion_status: "completed" },
    base_analysis: {
      status: "partial",
      profile: {
        candidate_name: field("Alex Example"),
        declared_location: field("Warsaw, Poland"),
        headline: null,
        summary: null,
        skills: [field("Private skill that must not be shown")],
        languages: [],
      },
      employment: [{
        id: "employment-1",
        status: "accepted",
        relation_status: "supported",
        added_by_reviewer: false,
        organization: field("Example Systems"),
        role: field("Engineer"),
        start_date: field("2020"),
        end_date: field("2024"),
        location: field("Warsaw"),
        relationship_type: field("employer"),
      }, {
        id: "employment-ambiguous",
        status: "ambiguous",
        relation_status: "ambiguous",
        added_by_reviewer: false,
        organization: field("MongoDB"),
        role: null,
        start_date: null,
        end_date: null,
        location: null,
        relationship_type: null,
      }],
      education: [{
        id: "education-1",
        status: "accepted",
        relation_status: "supported",
        added_by_reviewer: true,
        institution: field("Example University"),
        program: field("Computer Science"),
        degree: null,
        certificate: null,
        start_date: null,
        end_date: null,
        location: field("Warsaw"),
      }],
      pass_statuses: {
        profile: { status: "completed", attempt_count: 1, latency_ms: 1, usage: {}, model: "fake", reasoning_effort: "none" },
        employment: { status: "partial", attempt_count: 2, latency_ms: 2, failure_reason: "bounded_failure", usage: {}, model: "fake", reasoning_effort: "none" },
      },
      review: {
        status: "partial",
        accepted_ids: ["employment-1", "education-1"],
        rejected: [{ reason_code: "technology_as_employer", evidence: field("MongoDB").evidence }],
        merged_ids: [["employment-1", "employment-duplicate"]],
        relation_corrections: [],
        added_profile_fields: ["candidate_name"],
        added_candidate_ids: ["education-1"],
        conflicts: [{ reason_code: "wrong_record_relation", evidence: field("Example Systems").evidence }],
        coverage_gaps: [{ reason_code: "missing_education" }],
      },
    },
    mechanical: {
      phones: [{ value: "+48 123 456 789", country_code: "PL", evidence: field("+48 123 456 789").evidence }],
      emails: [],
      literal_links: [],
      postal_candidates: [],
      accepted_postal_addresses: [{ value: "00-001", possible_country_codes: ["PL"] }],
      email_findings: [],
      location_resolution: [{ subject: "declared_location", canonical_name: "Warsaw", country_code: "PL" }],
      eu_status: { countries: ["PL"], inside_eu: ["PL"], outside_eu: [], informational_only: true },
      comparisons: [{ kind: "declared_location_phone_country", relationship: "same" }],
    },
    research: {},
    limitations: [],
    versions: {},
    usage: {},
  };
}

test("adapts base-analysis-v2 into the restored report sections", () => {
  const presentation = adaptReportInterface(report(), "en");

  assert.equal(presentation.attention.length, 3);
  assert.ok(presentation.worthKnowing.length >= 4);
  assert.equal(presentation.remaining.length, 2);
  assert.equal(presentation.attention[0].evidence[0].source_id, "block-1");
});

test("CV overview includes accepted records and intentionally omits skills", () => {
  const overview = adaptReportInterface(report(), "en").overview;

  assert.equal(overview.candidateName, "Alex Example");
  assert.equal(overview.phoneCountry, "PL");
  assert.equal(overview.education[0].value, "Example University");
  assert.equal(overview.employment[0].value, "Engineer");
  assert.equal(overview.employment.length, 1);
  assert.equal(Object.hasOwn(overview, "skills"), false);
});
