import assert from "node:assert/strict";
import test from "node:test";

import {
  automaticallySkippedKinds,
  createAutoResearchOrchestrator,
  eligibleAutoResearchKinds,
  researchEligibility,
} from "./auto-research.ts";

function field(value) {
  return { value, status: "supported", evidence: [{ source_id: "s1", excerpt: value }] };
}

function report() {
  return {
    analysis_id: "analysis-1",
    ai_features_enabled: true,
    ai_capabilities: {
      document_analysis: true,
      company_research: true,
      education_research: true,
      linkedin_research: true,
    },
    base_analysis: {
      profile: { candidate_name: field("Jane Example") },
      employment: [{
        id: "work-1",
        status: "accepted",
        relation_status: "supported",
        organization: field("Example Systems"),
      }],
      education: [{
        id: "education-1",
        status: "accepted",
        relation_status: "supported",
        institution: field("Example University"),
        certificate: null,
      }],
    },
  };
}

function settings(patch = {}) {
  return {
    aiEnabled: true,
    autoResearchEnabled: true,
    autoCompanyResearch: true,
    autoEducationResearch: true,
    autoLinkedinDiscovery: true,
    ...patch,
  };
}

function storage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
}

test("accepted base analysis records enable all eligible research", () => {
  assert.deepEqual(
    [...eligibleAutoResearchKinds(report())].sort(),
    ["company", "education", "linkedin"],
  );
});

function withLinks(links) {
  const value = report();
  value.mechanical = { literal_links: links };
  return value;
}

const LINKEDIN_LINK = { value: "linkedin.com/in/jane", normalized_url: "https://linkedin.com/in/jane", known_host: "linkedin" };
const PERSONAL_LINK = { value: "www.jane.dev", normalized_url: "https://www.jane.dev", known_host: "personal" };

function recordingOrchestrator(calls) {
  return createAutoResearchOrchestrator({
    storage: storage(),
    maxConcurrency: 3,
    fetcher: async (url) => {
      calls.push(url);
      return { ok: true, status: 200, json: async () => ({ linkedin_discovery: {}, company_research: {}, education_research: {} }) };
    },
  });
}

test("a LinkedIn link in the CV keeps LinkedIn discovery eligible but skips the automatic start", async () => {
  const value = withLinks([PERSONAL_LINK, LINKEDIN_LINK]);
  assert.equal(researchEligibility(value).linkedin, true);
  assert.deepEqual([...automaticallySkippedKinds(value)], ["linkedin"]);

  const calls = [];
  await recordingOrchestrator(calls).schedule(value, settings());

  assert.deepEqual(calls.sort(), [
    "/api/analyses/analysis-1/research/company",
    "/api/analyses/analysis-1/research/education",
  ]);
});

test("manual LinkedIn discovery still runs when the CV links a profile", async () => {
  const calls = [];
  await recordingOrchestrator(calls).runManual(withLinks([LINKEDIN_LINK]), settings(), "linkedin");

  assert.deepEqual(calls, ["/api/analyses/analysis-1/research/linkedin/discovery"]);
});

test("a LinkedIn link inside the experience section does not count as provided", () => {
  const value = withLinks([{ ...LINKEDIN_LINK, section: "employment" }]);
  assert.deepEqual([...automaticallySkippedKinds(value)], []);
});

test("non-LinkedIn links do not skip any automatic research", () => {
  assert.deepEqual([...automaticallySkippedKinds(withLinks([PERSONAL_LINK]))], []);
});

test("ambiguous records are not research subjects", () => {
  const value = report();
  value.base_analysis.employment[0].status = "ambiguous";
  value.base_analysis.education[0].status = "ambiguous";
  value.base_analysis.profile.candidate_name.status = "ambiguous";

  assert.deepEqual([...eligibleAutoResearchKinds(value)], []);
});

test("automatic research honors settings and capabilities", async () => {
  const calls = [];
  const orchestrator = createAutoResearchOrchestrator({
    storage: storage(),
    fetcher: async (url) => {
      calls.push(url);
      return { ok: true, status: 200, json: async () => ({ company_research: {} }) };
    },
  });
  const value = report();
  value.ai_capabilities.education_research = false;

  await orchestrator.schedule(
    value,
    settings({ autoLinkedinDiscovery: false }),
  );

  assert.deepEqual(calls, ["/api/analyses/analysis-1/research/company"]);
});

test("automatic research calls every eligible research endpoint after base analysis", async () => {
  const calls = [];
  const orchestrator = createAutoResearchOrchestrator({
    storage: storage(),
    maxConcurrency: 3,
    fetcher: async (url) => {
      calls.push(url);
      const resultKey = url.endsWith("/company")
        ? "company_research"
        : url.endsWith("/education")
          ? "education_research"
          : "linkedin_discovery";
      return { ok: true, status: 200, json: async () => ({ [resultKey]: {} }) };
    },
  });

  await orchestrator.schedule(report(), settings());

  assert.deepEqual(calls.sort(), [
    "/api/analyses/analysis-1/research/company",
    "/api/analyses/analysis-1/research/education",
    "/api/analyses/analysis-1/research/linkedin/discovery",
  ]);
});

test("automatic research eligibility does not require a browser capability token", () => {
  const value = report();
  assert.equal(Object.hasOwn(value, "analysis_access_token"), false);
  assert.deepEqual(
    [...eligibleAutoResearchKinds(value)].sort(),
    ["company", "education", "linkedin"],
  );
});

test("rerender does not repeat completed automatic research", async () => {
  let calls = 0;
  const orchestrator = createAutoResearchOrchestrator({
    storage: storage(),
    fetcher: async () => {
      calls += 1;
      return { ok: true, status: 200, json: async () => ({ company_research: {} }) };
    },
  });
  const selected = settings({
    autoEducationResearch: false,
    autoLinkedinDiscovery: false,
  });

  await orchestrator.schedule(report(), selected);
  await orchestrator.schedule(report(), selected);

  assert.equal(calls, 1);
});

test("disabled public research makes no request", async () => {
  let calls = 0;
  const orchestrator = createAutoResearchOrchestrator({
    storage: storage(),
    fetcher: async () => {
      calls += 1;
      return { ok: true, status: 200, json: async () => ({}) };
    },
  });

  await orchestrator.schedule(report(), settings({ aiEnabled: false }));

  assert.equal(calls, 0);
});

test("refresh bypasses a report result and requests fresh research", async () => {
  const calls = [];
  const orchestrator = createAutoResearchOrchestrator({
    storage: storage(),
    fetcher: async (url, init) => {
      calls.push({ url, body: JSON.parse(init.body) });
      return { ok: true, status: 200, json: async () => ({ company_research: { cache: { status: "miss" } } }) };
    },
  });
  const value = report();
  value.company_research = { cache: { status: "hit" } };

  await orchestrator.runRefresh(value, settings(), "company");

  assert.deepEqual(calls, [{
    url: "/api/analyses/analysis-1/research/company",
    body: { refresh: true },
  }]);
});

test("certificate-only entries never trigger education research", () => {
  const value = report();
  value.base_analysis.education[0].institution = null;
  value.base_analysis.education[0].certificate = {value: "Example Certificate", status: "supported"};
  assert.equal(eligibleAutoResearchKinds(value).has("education"), false);
});

test("failed research preserves safe diagnostic details for copying", async () => {
  const value = report();
  const orchestrator = createAutoResearchOrchestrator({
    storage: storage(),
    fetcher: async () => ({ok:false, status:502, json:async () => ({detail:"company_research_invalid_response", error_reason:"subject_mismatch"})}),
  });
  await orchestrator.runManual(value, settings(), "company");
  const failure = orchestrator.getState(value.analysis_id, "company");
  assert.equal(failure.status, "failed");
  assert.equal(failure.diagnostics.reason, "subject_mismatch");
  assert.equal(failure.diagnostics.code, "company_research_invalid_response");
  assert.equal(failure.diagnostics.analysisId, value.analysis_id);
  assert.ok(!Number.isNaN(Date.parse(failure.diagnostics.occurredAt)));
});
