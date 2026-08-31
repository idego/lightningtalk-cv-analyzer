import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTO_RESEARCH_MAX_CONCURRENCY,
  announcedAutoResearchKinds,
  createAutoResearchOrchestrator,
  effectiveAutoResearchKinds,
  eligibleAutoResearchKinds,
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
    ai_capabilities: { company_research: true, education_research: true, linkedin_research: true },
  };
}

function memoryStorage() {
  const values = new Map();
  return { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}

test("children are effective only when the master toggle is on", () => {
  assert.deepEqual(effectiveAutoResearchKinds({ ...settings, aiEnabled: false }), []);
  assert.deepEqual(effectiveAutoResearchKinds({ ...settings, autoResearchEnabled: false }), []);
  assert.deepEqual(effectiveAutoResearchKinds({ ...settings, autoEducationResearch: false }), ["company", "linkedin"]);
});

test("does not schedule any research when AI is disabled", async () => {
  let calls = 0;
  const orchestrator = createAutoResearchOrchestrator({
    storage: memoryStorage(),
    fetcher: async () => {
      calls += 1;
      return { ok: true, json: async () => ({}) };
    },
  });

  await orchestrator.schedule(report("ai-off"), { ...settings, aiEnabled: false });
  await orchestrator.schedule({ ...report("server-off"), ai_features_enabled: false }, settings);

  assert.equal(calls, 0);
});

test("unavailable AI or category capabilities are neither eligible nor scheduled", async () => {
  const unavailable = { ...report("unavailable"), ai_features_enabled: false };
  assert.deepEqual([...eligibleAutoResearchKinds(unavailable)], []);
  const categoryOff = { ...report("category-off"), ai_capabilities: { company_research: false, education_research: false, linkedin_research: false } };
  assert.deepEqual([...eligibleAutoResearchKinds(categoryOff)], []);
});

test("intersects automatic research with each server capability", async () => {
  const urls = [];
  const orchestrator = createAutoResearchOrchestrator({ storage: memoryStorage(), fetcher: async (url) => { urls.push(url); return { ok: true, json: async () => ({}) }; } });
  await orchestrator.schedule({ ...report("caps"), ai_capabilities: { company_research: false, education_research: true, linkedin_research: false } }, { ...settings, aiEnabled: true });
  assert.equal(urls.length, 1); assert.match(urls[0], /education/);
});

test("code-owned company and education subjects schedule after document AI failure", async () => {
  const urls = [];
  const failed = {
    ...report("code-after-ai-failure", []),
    ai_analysis: { status: "failed", research_candidates: [] },
    document_understanding: { code_research_subjects: [
      { category: "company", subject: "Code Company" },
      { category: "education", subject: "Code University" },
    ] },
  };
  const orchestrator = createAutoResearchOrchestrator({ storage: memoryStorage(), fetcher: async (url) => { urls.push(url); return { ok: true, json: async () => ({}) }; } });
  await orchestrator.schedule(failed, { ...settings, aiEnabled: true });
  assert.deepEqual(urls.map((url) => url.split("/").at(-1)).sort(), ["company", "education"]);
});

test("batch disclosure unions eligible research across every successful report", () => {
  const companyOnly = report("company", ["company"]);
  const educationOnly = report("education", ["education_or_certification"]);
  const linkedinOnly = report("linkedin", ["linkedin"]);
  assert.deepEqual(
    announcedAutoResearchKinds([companyOnly, educationOnly, linkedinOnly], { ...settings, aiEnabled: true }),
    ["company", "education", "linkedin"],
  );
});

test("authorization matrix never schedules a disabled setting or capability", async () => {
  for (const kind of ["company", "education", "linkedin"]) {
    for (const disabledBy of ["setting", "capability"]) {
      const urls = [];
      const localSettings = { ...settings, aiEnabled: true };
      const capabilities = { company_research: true, education_research: true, linkedin_research: true };
      if (disabledBy === "setting") localSettings[{ company: "autoCompanyResearch", education: "autoEducationResearch", linkedin: "autoLinkedinDiscovery" }[kind]] = false;
      else capabilities[`${kind}_research`] = false;
      const orchestrator = createAutoResearchOrchestrator({ storage: memoryStorage(), fetcher: async (url) => { urls.push(url); return { ok: true, json: async () => ({}) }; } });
      await orchestrator.schedule({ ...report(`${kind}-${disabledBy}`), ai_capabilities: capabilities }, localSettings);
      const suffix = kind === "linkedin" ? "linkedin/discovery" : kind;
      assert.equal(urls.some((url) => url.endsWith(`/research/${suffix}`)), false, `${kind} disabled by ${disabledBy}`);
    }
  }
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

test("manual and automatic starts share one atomic request claim", async () => {
  let calls = 0;
  let release;
  const orchestrator = createAutoResearchOrchestrator({
    storage: memoryStorage(),
    fetcher: async () => {
      calls += 1;
      await new Promise((resolve) => { release = resolve; });
      return { ok: true, status: 200, json: async () => ({ company_research: { status: "completed" } }) };
    },
  });
  const candidate = report("manual-auto", ["company"]);

  const manual = orchestrator.runManual(candidate, { ...settings, aiEnabled: true }, "company");
  const automatic = orchestrator.schedule(candidate, { ...settings, aiEnabled: true });
  const repeatedManual = orchestrator.runManual(candidate, { ...settings, aiEnabled: true }, "company");
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.equal(calls, 1);
  assert.equal(orchestrator.getState(candidate.analysis_id, "company").status, "running");
  release();
  await Promise.all([manual, automatic, repeatedManual]);
  assert.equal(calls, 1);
  assert.equal(orchestrator.getState(candidate.analysis_id, "company").status, "succeeded");
});

test("automatic then manual starts also share one atomic request claim", async () => {
  let calls = 0;
  let release;
  const orchestrator = createAutoResearchOrchestrator({
    storage: memoryStorage(),
    fetcher: async () => {
      calls += 1;
      await new Promise((resolve) => { release = resolve; });
      return { ok: true, status: 200, json: async () => ({ company_research: { status: "completed" } }) };
    },
  });
  const candidate = report("auto-manual", ["company"]);
  const automatic = orchestrator.schedule(candidate, { ...settings, aiEnabled: true });
  const manual = orchestrator.runManual(candidate, { ...settings, aiEnabled: true }, "company");
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.equal(calls, 1);
  release();
  await Promise.all([automatic, manual]);
  assert.equal(calls, 1);
});

test("completed report research never starts another network request", async () => {
  let calls = 0;
  const orchestrator = createAutoResearchOrchestrator({ storage: memoryStorage(), fetcher: async () => { calls += 1; return { ok: true, status: 200, json: async () => ({}) }; } });
  const candidate = { ...report("already-complete", ["company"]), company_research: { status: "completed" } };
  await orchestrator.runManual(candidate, { ...settings, aiEnabled: true }, "company");
  assert.equal(calls, 0);
  assert.equal(orchestrator.getState(candidate.analysis_id, "company").status, "succeeded");
});

test("manual retry is allowed after failure but not while running or after success", async () => {
  let calls = 0;
  const orchestrator = createAutoResearchOrchestrator({
    storage: memoryStorage(),
    fetcher: async () => {
      calls += 1;
      return calls === 1
        ? { ok: false, status: 503, json: async () => ({}) }
        : { ok: true, status: 200, json: async () => ({ company_research: { status: "completed" } }) };
    },
  });
  const candidate = report("manual-retry", ["company"]);

  await orchestrator.schedule(candidate, { ...settings, aiEnabled: true });
  assert.equal(orchestrator.getState(candidate.analysis_id, "company").status, "failed");
  await orchestrator.runManual(candidate, { ...settings, aiEnabled: true }, "company");
  await orchestrator.runManual(candidate, { ...settings, aiEnabled: true }, "company");

  assert.equal(calls, 2);
  assert.equal(orchestrator.getState(candidate.analysis_id, "company").status, "succeeded");
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
