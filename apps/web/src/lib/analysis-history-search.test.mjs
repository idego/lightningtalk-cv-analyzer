import assert from "node:assert/strict";
import test from "node:test";
import { searchAnalysisHistory } from "./analysis-history-search.ts";
const items = [
  { analysis_id: "1", candidate_name: "Łukasz Żółć", filename: "CV-backend-2026.PDF" },
  { analysis_id: "2", candidate_name: "Avery Example", filename: "avery_product.docx" },
  { analysis_id: "3", candidate_name: null, filename: "design-portfolio.pdf" },
];
test("blank query preserves order and input", () => {
  assert.deepEqual(searchAnalysisHistory(items, "  "), items);
  assert.notEqual(searchAnalysisHistory(items, ""), items);
});
test("matches candidate and filename without case or Polish diacritics", () => {
  assert.deepEqual(searchAnalysisHistory(items, "LUKASZ zolc backend"), [items[0]]);
  assert.deepEqual(searchAnalysisHistory(items, "AVERY  product"), [items[1]]);
});
test("supports filename-only analyses, unmatched queries, and literal punctuation", () => {
  assert.deepEqual(searchAnalysisHistory(items, "portfolio.pdf"), [items[2]]);
  assert.deepEqual(searchAnalysisHistory(items, "["), []);
  assert.deepEqual(searchAnalysisHistory(items, "avery backend"), []);
});
test("searches entries beyond the former fifteen-row display cap", () => {
  const many = Array.from({ length: 40 }, (_, index) => ({ analysis_id: `${index}`, filename: `cv-${index}.pdf`, candidate_name: `Candidate ${index}` }));
  assert.deepEqual(searchAnalysisHistory(many, "Candidate 39"), [many[39]]);
});

const olderItems = Array.from({ length: 40 }, (_, index) => ({
  analysis_id: `analysis-${index}`,
  candidate_name: index === 37 ? "Łukasz Żółć" : `Candidate ${index}`,
  filename: index === 37 ? "Gdańsk_Developer_CV.DOCX" : `cv-${index}.pdf`,
  status: "completed", created_at: "2026-09-05T12:00:00Z", strategy: "document-analysis",
}));

test("blank history search keeps every record in its original order", () => {
  assert.deepEqual(searchAnalysisHistory(olderItems, "  "), olderItems);
  assert.deepEqual(searchAnalysisHistory([], "someone"), []);
});
test("history search finds older records beyond the former fifteen-record cutoff", () => {
  assert.equal(searchAnalysisHistory(olderItems, "lukasz")[0].analysis_id, "analysis-37");
});
test("history search ignores case and Polish diacritics and combines words across name and filename", () => {
  assert.deepEqual(searchAnalysisHistory(olderItems, "  gdansk   ZOLC  docx "), [olderItems[37]]);
  assert.deepEqual(searchAnalysisHistory(olderItems, "ŁUKASZ"), [olderItems[37]]);
});
test("history search supports filenames without a candidate name and requires every search term", () => {
  assert.equal(searchAnalysisHistory([{ ...olderItems[0], candidate_name: null }], "cv-0.pdf").length, 1);
  assert.equal(searchAnalysisHistory(olderItems, "lukasz designer").length, 0);
  assert.equal(searchAnalysisHistory(olderItems, "analysis-37").length, 0);
});
