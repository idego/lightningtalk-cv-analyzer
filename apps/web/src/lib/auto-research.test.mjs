import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTO_RESEARCH_MAX_CONCURRENCY,
  createAutoResearchOrchestrator,
  effectiveAutoResearchKinds,
} from "./auto-research.ts";

const settings = {
  autoResearchEnabled: true,
  autoCompanyResearch: true,
  autoEducationResearch: true,
  autoLinkedinDiscovery: true,
};

function report(id, categories = ["company", "education_or_certification", "linkedin"]) {
  return {
    analysis_id: id,
    analysis_access_token: `token-${id}`,
    ai_analysis: { status: "succeeded", research_candidates: categories.map((category) => ({ category, query_subject: "safe" })) },
  };
}

function memoryStorage() {
  const values = new Map();
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}

test("children are effective only when the master toggle is on", () => {
  assert.deepEqual(effectiveAutoResearchKinds({ ...settings, autoResearchEnabled: false }), []);
  assert.deepEqual(effectiveAutoResearchKinds({ ...settings, autoEducationResearch: false }), ["company", "linkedin"]);
});

test("runs eligible research with one global concurrency limit", async () => {
  assert.equal(AUTO_RESEARCH_MAX_CONCURRENCY, 2);
  let active = 0;
  let peak = 0;
  const releases = [];
  const fetcher = async (url) => {
    active += 1;
    peak = Math.max(peak, active);
    await new Promise((resolve) => releases.push(resolve));
    active -= 1;
    const key = url.includes("company") ? "company_research" : url.includes("education") ? "education_research" : "linkedin_discovery";
    return { ok: true, json: async () => ({ [key]: { status: "completed" } }) };
  };
  const orchestrator = createAutoResearchOrchestrator({ fetcher, storage: memoryStorage(), maxConcurrency: 2 });
  const completion = orchestrator.schedule(report("one"), settings);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(active, 2);
  releases.shift()();
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(peak, 2);
  while (releases.length) releases.shift()();
  await completion;
  assert.equal(orchestrator.getState("one", "company").status, "succeeded");
  assert.equal(orchestrator.getState("one", "education").status, "succeeded");
  assert.equal(orchestrator.getState("one", "linkedin").status, "succeeded");
});

test("deduplicates rerenders and refreshes without retrying failed work", async () => {
  const storage = memoryStorage();
  let calls = 0;
  const fetcher = async () => { calls += 1; return { ok: false, status: 503, json: async () => ({}) }; };
  const first = createAutoResearchOrchestrator({ fetcher, storage, maxConcurrency: 2 });
  await Promise.all([first.schedule(report("same", ["company"]), settings), first.schedule(report("same", ["company"]), settings)]);
  assert.equal(calls, 1);
  assert.equal(first.getState("same", "company").status, "failed");

  const afterRefresh = createAutoResearchOrchestrator({ fetcher, storage, maxConcurrency: 2 });
  await afterRefresh.schedule(report("same", ["company"]), settings);
  assert.equal(calls, 1);
  assert.equal(afterRefresh.getState("same", "company").status, "manual-action");
});

test("isolates one failed kind and never starts LinkedIn comparison", async () => {
  const urls = [];
  const orchestrator = createAutoResearchOrchestrator({
    storage: memoryStorage(), maxConcurrency: 2,
    fetcher: async (url) => {
      urls.push(url);
      if (url.includes("company")) return { ok: false, status: 500, json: async () => ({}) };
      const key = url.includes("education") ? "education_research" : "linkedin_discovery";
      return { ok: true, json: async () => ({ [key]: { status: "completed" } }) };
    },
  });
  await orchestrator.schedule(report("isolated"), settings);
  assert.equal(orchestrator.getState("isolated", "company").status, "failed");
  assert.equal(orchestrator.getState("isolated", "education").status, "succeeded");
  assert.equal(orchestrator.getState("isolated", "linkedin").status, "succeeded");
  assert.equal(urls.some((url) => url.includes("comparison")), false);
});
