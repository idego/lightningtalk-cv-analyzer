import assert from "node:assert/strict";
import test from "node:test";

import {
  createAutoResearchOrchestrator,
  eligibleAutoResearchKinds,
} from "./auto-research.ts";

function field(value) {
  return { value, status: "supported", evidence: [{ source_id: "s1", excerpt: value }] };
}

function report() {
  return {
    analysis_id: "analysis-1",
    analysis_access_token: "token",
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
        organization: field("Example Systems"),
      }],
      education: [{
        id: "education-1",
        status: "accepted",
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
    body: { accessToken: "token", aiEnabled: true, refresh: true },
  }]);
});
