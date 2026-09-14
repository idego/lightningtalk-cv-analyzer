import assert from "node:assert/strict";
import test from "node:test";

import {
  completedBatchIds,
  deriveBatchStatuses,
  isSupportedCvFilename,
  resolveDocumentSource,
} from "./batch-progress.ts";

const ok = (id) => ({ filename: `${id}.pdf`, status: "ok", report: { analysis_id: id } });
const failed = { filename: "b.pdf", status: "error", error: "boom" };

test("statuses follow the sequential position of the batch", () => {
  const filenames = ["a.pdf", "b.pdf", "c.pdf"];
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [null, null, null], active: [0, 1], phase: "running" }), ["analyzing", "analyzing", "waiting"]);
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [null, ok("b"), null], active: [0, 2], phase: "running" }), ["analyzing", "completed", "analyzing"]);
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [ok("a"), failed, null], active: [2], phase: "running" }), ["completed", "failed", "analyzing"]);
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [ok("a"), failed, ok("c")], active: [], phase: "complete" }), ["completed", "failed", "completed"]);
});

test("completed ids skip failed files", () => {
  assert.deepEqual(completedBatchIds([ok("a"), failed, null, ok("c")]), ["a", "c"]);
});

test("supported CV filenames accept only PDF and DOCX extensions", () => {
  assert.equal(isSupportedCvFilename("candidate.pdf"), true);
  assert.equal(isSupportedCvFilename("candidate.DOCX"), true);
  assert.equal(isSupportedCvFilename("candidate.png"), false);
  assert.equal(isSupportedCvFilename("candidate.txt"), false);
  assert.equal(isSupportedCvFilename("candidate.pdf.exe"), false);
});

test("document source prefers the session upload, then the stored copy", () => {
  const file = { name: "local.pdf" };
  const sessionFiles = new Map([["a", file]]);
  assert.equal(resolveDocumentSource({ analysis_id: "a", filename: "a.pdf", has_document: true }, sessionFiles), file);
  assert.deepEqual(
    resolveDocumentSource({ analysis_id: "b/c", filename: "b.pdf", has_document: true }, sessionFiles),
    { url: "/api/analyses/b%2Fc/document", name: "b.pdf" },
  );
  assert.equal(resolveDocumentSource({ analysis_id: "d", filename: "d.pdf", has_document: false }, sessionFiles), null);
  assert.equal(resolveDocumentSource({ analysis_id: "e", filename: "e.pdf" }, sessionFiles), null);
});
