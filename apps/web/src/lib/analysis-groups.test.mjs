import assert from "node:assert/strict";
import test from "node:test";

import { countAnalyses, searchAnalysisGroups, withMovedAnalysis, withNoteState, withoutAnalysis, withoutGroup } from "./analysis-history-search.ts";

const item = (analysis_id, candidate_name, filename) => ({
  analysis_id, candidate_name, filename, status: "completed", strategy: "document-analysis", created_at: "2026-09-08T10:00:00Z",
});
const groups = [
  { group_id: "g1", name: "Junior backend", created_at: "2026-09-01T00:00:00Z", is_unassigned: false, analyses: [item("a1", "Anna Kowalska", "anna.pdf"), item("a2", null, "cv-bob.docx")] },
  { group_id: "g2", name: "Empty offer", created_at: "2026-09-02T00:00:00Z", is_unassigned: false, analyses: [] },
  { group_id: "unassigned", name: "Unassigned", created_at: null, is_unassigned: true, analyses: [item("a3", "Łukasz Nowak", "lukasz.pdf")] },
];

test("empty query keeps every group, including empty ones, in order", () => {
  assert.deepEqual(searchAnalysisGroups(groups, "  ").map((g) => g.group_id), ["g1", "g2", "unassigned"]);
});

test("query narrows groups to matching candidates or filenames and drops empty groups", () => {
  const result = searchAnalysisGroups(groups, "lukasz");
  assert.deepEqual(result.map((g) => g.group_id), ["unassigned"]);
  assert.deepEqual(result[0].analyses.map((a) => a.analysis_id), ["a3"]);
  assert.deepEqual(searchAnalysisGroups(groups, "bob")[0].analyses.map((a) => a.analysis_id), ["a2"]);
});

test("counts analyses across groups and removes single analyses", () => {
  assert.equal(countAnalyses(groups), 3);
  const next = withoutAnalysis(groups, "a1");
  assert.deepEqual(next[0].analyses.map((a) => a.analysis_id), ["a2"]);
  assert.equal(countAnalyses(next), 2);
});

test("deleting a group removes it, but Unassigned only empties", () => {
  assert.deepEqual(withoutGroup(groups, "g1").map((g) => g.group_id), ["g2", "unassigned"]);
  const rest = withoutGroup(groups, "unassigned");
  assert.deepEqual(rest.map((g) => g.group_id), ["g1", "g2", "unassigned"]);
  assert.deepEqual(rest[2].analyses, []);
});

test("moving an analysis changes its group and clears group_id for Unassigned", () => {
  const toEmpty = withMovedAnalysis(groups, "a3", "g2");
  assert.deepEqual(toEmpty[2].analyses, []);
  assert.deepEqual(toEmpty[1].analyses.map((a) => [a.analysis_id, a.group_id]), [["a3", "g2"]]);
  const toUnassigned = withMovedAnalysis(groups, "a1", "unassigned");
  assert.deepEqual(toUnassigned[0].analyses.map((a) => a.analysis_id), ["a2"]);
  assert.deepEqual(toUnassigned[2].analyses.map((a) => [a.analysis_id, a.group_id]), [["a3", undefined], ["a1", null]]);
  assert.deepEqual(withMovedAnalysis(groups, "missing", "g1"), groups);
});

test("note state updates only the matching analysis", () => {
  const next = withNoteState(groups, "a3", true);
  assert.equal(next[2].analyses[0].has_note, true);
  assert.equal(next[0].analyses[0].has_note, undefined);
  assert.equal(withNoteState(next, "a3", false)[2].analyses[0].has_note, false);
});
