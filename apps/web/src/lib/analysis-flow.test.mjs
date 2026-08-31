import assert from "node:assert/strict";
import test from "node:test";

import { enrichThenScheduleResearch } from "./analysis-flow.ts";
import { eligibleAutoResearchKinds } from "./auto-research.ts";

test("failed AI enrichment still schedules code-owned company and education research", async () => {
  const initial = {
    status: "ok",
    filename: "anonymous.docx",
    report: {
      analysis_id: "analysis-1",
      analysis_access_token: "token",
      ai_analysis: { status: "pending", research_candidates: [] },
      document_understanding: { code_research_subjects: [
        { category: "company", subject: "Example Company" },
        { category: "education", subject: "Example University" },
      ] },
      ai_capabilities: { company_research: true, education_research: true, linkedin_research: true },
    },
  };
  const scheduled = [];
  const outcome = await enrichThenScheduleResearch(
    initial,
    { aiEnabled: true },
    async () => { throw new Error("AI unavailable"); },
    (report) => scheduled.push([...eligibleAutoResearchKinds(report)]),
  );

  assert.equal(outcome.result.report.ai_analysis.status, "failed");
  assert.deepEqual(scheduled, [["company", "education"]]);
});
