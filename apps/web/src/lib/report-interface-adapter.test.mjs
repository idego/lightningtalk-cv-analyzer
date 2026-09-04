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
    strategy: { name: "document-analysis", version: "test" },
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
        rejected: [
          { id: "employment-ambiguous", reason_code: "invalid_literal_evidence" },
          { id: "unknown-id", reason_code: "reviewer_added_candidate_invalid_evidence" },
        ],
        annotations: [{ record_id: "employment-ambiguous", kind: "suspected_hallucination", reason_code: "technology_not_employer" }],
        merged_ids: [["employment-1", "employment-duplicate"]],
        merge_projections: [],
        relation_corrections: [],
        added_profile_fields: ["candidate_name"],
        added_candidate_ids: ["education-1"],
        conflicts: [
          { reason_code: "invalid_literal_evidence" },
          { reason_code: "unknown_reviewer_patch_id" },
        ],
        coverage_gaps: [
          { target: "education", reason_code: "missing_education", source_block_ids: ["block-1"], evidence: field("Education section").evidence },
          { target: "education", reason_code: "missing_education", source_block_ids: ["block-1"], evidence: field("Education section").evidence },
          { target: "education", reason_code: "invalid_addition", source_block_ids: [] },
        ],
      },
    },
    mechanical: {
      phones: [{ value: "+48 123 456 789", country_code: "PL", evidence: field("+48 123 456 789").evidence }],
      emails: [],
      literal_links: [],
      postal_candidates: [],
      accepted_postal_addresses: [{ value: "00-001", possible_country_codes: ["PL"] }],
      email_findings: [
        { kind: "possible_common_provider_typo", observed_domain: "gmial.com", suggested_domain: "gmail.com", evidence: field("gmial.com").evidence },
        { kind: "possible_common_provider_typo", observed_domain: "gmial.com", suggested_domain: "gmail.com", evidence: field("gmial.com").evidence },
      ],
      location_resolution: [{ subject: "declared_location", canonical_name: "Warsaw", country_code: "PL" }],
      eu_status: { countries: ["PL"], inside_eu: ["PL"], outside_eu: [], informational_only: true },
      comparisons: [
        { kind: "declared_location_phone_country", relationship: "same", declared_country_codes: ["PL"], phone_country_codes: ["PL"] },
        { kind: "declared_location_phone_country", relationship: "same", declared_country_codes: ["PL"], phone_country_codes: ["PL"] },
        { kind: "declared_location_phone_country", relationship: "different", declared_country_codes: ["PL"], phone_country_codes: ["DE"] },
        { kind: "declared_location_phone_country", relationship: "different", declared_country_codes: ["PL"], phone_country_codes: ["DE"] },
      ],
    },
    research: {},
    limitations: [],
    versions: {},
    usage: {},
  };
}

test("shows only deduplicated recruiter-facing signals", () => {
  const presentation = adaptReportInterface(report(), "en");

  assert.equal(presentation.attention.length, 2);
  assert.equal(presentation.worthKnowing.length, 1);
  assert.equal(presentation.attention[1].evidence[0].source_id, "block-1");
  assert.equal(
    [...presentation.attention, ...presentation.worthKnowing]
      .every((item) => item.evidence.length > 0),
    true,
  );
  const rendered = JSON.stringify(presentation);
  assert.doesNotMatch(rendered, /invalid_literal_evidence|invalid addition|unknown reviewer|rejected/i);
});

test("CV overview includes accepted and annotated records and intentionally omits skills", () => {
  const overview = adaptReportInterface(report(), "en").overview;

  assert.equal(overview.candidateName, "Alex Example");
  assert.equal(overview.phoneCountry, "PL");
  assert.equal(overview.education[0].value, "Example University");
  assert.equal(overview.employment[0].value, "Engineer");
  assert.equal(overview.employment.length, 1);
  assert.equal(overview.attentionRecords[0].value, "MongoDB");
  assert.equal(overview.attentionRecords[0].needsReview, true);
  assert.equal(Object.hasOwn(overview, "skills"), false);
});

test("CV overview renders certificates, including certificate-only education records", () => {
  const value = report();
  value.base_analysis.education[0].certificate = field("AWS Cloud Practitioner");
  value.base_analysis.education.push({
    ...value.base_analysis.education[0],
    id: "certificate-only",
    institution: null,
    program: null,
    certificate: field("Azure Fundamentals"),
  });

  const overview = adaptReportInterface(value, "en").overview;

  assert.equal(overview.education.length, 1);
  assert.match(JSON.stringify(overview.education), /AWS Cloud Practitioner/);
  assert.equal(overview.certifications.length, 1);
  assert.equal(overview.certifications[0].value, "Azure Fundamentals");
});

test("CV overview renders when optional review annotations are absent", () => {
  const value = report();
  delete value.base_analysis.review.annotations;

  const overview = adaptReportInterface(value, "en").overview;

  assert.equal(overview.employment.length, 2);
  assert.equal(overview.attentionRecords.length, 0);
});

test("completed LinkedIn not-found result becomes one cautious checklist finding", () => {
  const value = report();
  value.linkedin_discovery = {
    status: "completed",
    outcome: "insufficient_evidence",
    linkedin_not_found: true,
    not_found_caveat: "Limited public search does not prove absence.",
    searches_performed: [],
    search_limitations: [],
    possible_profiles: [],
  };

  const presentation = adaptReportInterface(value, "en");
  const linkedin = presentation.attention.find((item) => item.id === "linkedin-not-found");

  assert.match(linkedin.whatWeFound, /limited search/i);
  assert.match(linkedin.whyItMatters, /does not mean.*does not exist/i);
  assert.equal(linkedin.evidence[0].excerpt, "Alex Example");
});

test("outside-EU status is neutral overview information, not a finding", () => {
  const value = report();
  value.mechanical.eu_status = {
    countries: ["US", "CA"],
    inside_eu: [],
    outside_eu: ["CA", "US"],
    primary_source: "declared_location",
    informational_only: true,
    sources: [{
      kind: "declared_location",
      country_code: "US",
      evidence: field("Austin, United States").evidence,
    }, {
      kind: "phone_prefix",
      country_code: "CA",
      evidence: field("+1 416 555 0100", "block-phone").evidence,
    }],
  };

  const presentation = adaptReportInterface(value, "en");
  assert.equal(presentation.overview.euStatus, "outside");
  assert.equal(presentation.attention.some((item) => item.id === "outside-eu"), false);
  assert.equal(presentation.worthKnowing.some((item) => item.id === "outside-eu"), false);

  value.mechanical.eu_status.sources[0].country_code = "PL";
  value.mechanical.eu_status.inside_eu = ["PL"];
  assert.equal(adaptReportInterface(value, "en").overview.euStatus, "outside");

  value.mechanical.eu_status.sources = [value.mechanical.eu_status.sources[1]];
  value.mechanical.eu_status.primary_source = "phone_prefix";
  value.mechanical.eu_status.inside_eu = [];
  value.mechanical.eu_status.outside_eu = ["CA"];
  assert.equal(adaptReportInterface(value, "en").overview.euStatus, "outside");
});

test("GeoNames and postal outcomes use evidence and cautious status-specific copy", () => {
  const value = report();
  value.mechanical.location_resolution = [{
    subject: "declared_location",
    value: "Berlin, Poland",
    city: "Berlin",
    country: "Poland",
    status: "resolved",
    city_country_relationship: "different",
    evidence: field("Berlin, Poland").evidence,
  }];
  value.mechanical.accepted_postal_addresses = [{
    value: "00-001",
    city: "Berlin",
    country: "Poland",
    evidence: field("00-001").evidence,
    address_evidence: field("Berlin, Poland").evidence,
    validation: { status: "unavailable" },
  }];

  const presentation = adaptReportInterface(value, "en");

  assert.match(presentation.attention.find((item) => item.id.startsWith("location-")).whatWeFound, /different countries/i);
  assert.equal(presentation.overview.postalConsistency, null);
  assert.equal(presentation.worthKnowing.some((item) => item.id.startsWith("postal-")), false);

  value.mechanical.accepted_postal_addresses[0].validation.status = "resolved";
  assert.equal(adaptReportInterface(value, "en").overview.postalConsistency, "consistent");
  value.mechanical.accepted_postal_addresses[0].validation.status = "mismatch";
  assert.equal(adaptReportInterface(value, "en").overview.postalConsistency, "mismatch");

  value.mechanical.location_resolution[0].status = "unresolved";
  value.mechanical.location_resolution[0].city_country_relationship = "unresolved";
  const unresolved = adaptReportInterface(value, "en").worthKnowing.find((item) => item.id.startsWith("location-"));
  assert.match(unresolved.whatWeFound, /not confirmed in the limited GeoNames index/i);
  assert.doesNotMatch(unresolved.whatWeFound, /does not exist/i);
});
