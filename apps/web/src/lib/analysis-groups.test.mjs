import assert from "node:assert/strict";
import test from "node:test";

import { countAnalyses, searchAnalysisGroups, withoutAnalysis, withoutGroup } from "./analysis-history-search.ts";

const item = (analysis_id, candidate_name, filename) => ({
  analysis_id, candidate_name, filename, status: "completed", strategy: "document-analysis", created_at: "2026-09-08T10:00:00Z",
});
const groups = [
  { group_id: "g1", name: "Junior backend", created_at: "2026-09-01T00:00:00Z", is_rest: false, analyses: [item("a1", "Anna Kowalska", "anna.pdf"), item("a2", null, "cv-bob.docx")] },
  { group_id: "g2", name: "Empty offer", created_at: "2026-09-02T00:00:00Z", is_rest: false, analyses: [] },
  { group_id: "rest", name: "Rest", created_at: null, is_rest: true, analyses: [item("a3", "Łukasz Nowak", "lukasz.pdf")] },
];

test("empty query keeps every group, including empty ones, in order", () => {
  assert.deepEqual(searchAnalysisGroups(groups, "  ").map((g) => g.group_id), ["g1", "g2", "rest"]);
});

test("query narrows groups to matching candidates or filenames and drops empty groups", () => {
  const result = searchAnalysisGroups(groups, "lukasz");
  assert.deepEqual(result.map((g) => g.group_id), ["rest"]);
  assert.deepEqual(result[0].analyses.map((a) => a.analysis_id), ["a3"]);
  assert.deepEqual(searchAnalysisGroups(groups, "bob")[0].analyses.map((a) => a.analysis_id), ["a2"]);
});

test("counts analyses across groups and removes single analyses", () => {
  assert.equal(countAnalyses(groups), 3);
  const next = withoutAnalysis(groups, "a1");
  assert.deepEqual(next[0].analyses.map((a) => a.analysis_id), ["a2"]);
  assert.equal(countAnalyses(next), 2);
});

test("deleting a group removes it, but Rest only empties", () => {
  assert.deepEqual(withoutGroup(groups, "g1").map((g) => g.group_id), ["g2", "rest"]);
  const rest = withoutGroup(groups, "rest");
  assert.deepEqual(rest.map((g) => g.group_id), ["g1", "g2", "rest"]);
  assert.deepEqual(rest[2].analyses, []);
});
