import assert from "node:assert/strict";
import test from "node:test";

import {
  completedBatchIds,
  currentBatchIndex,
  deriveBatchStatuses,
  hasPendingBatchFiles,
  resolveDocumentSource,
} from "./batch-progress.ts";

const ok = (id) => ({ filename: `${id}.pdf`, status: "ok", report: { analysis_id: id } });
const failed = { filename: "b.pdf", status: "error", error: "boom" };

test("statuses follow the sequential position of the batch", () => {
  const filenames = ["a.pdf", "b.pdf", "c.pdf"];
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [], phase: "running" }), ["analyzing", "waiting", "waiting"]);
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [ok("a")], phase: "running" }), ["completed", "analyzing", "waiting"]);
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [ok("a"), failed], phase: "running" }), ["completed", "failed", "analyzing"]);
  assert.deepEqual(deriveBatchStatuses({ filenames, results: [ok("a"), failed, ok("c")], phase: "complete" }), ["completed", "failed", "completed"]);
});

test("current index and pending flag track finished results", () => {
  const filenames = ["a.pdf", "b.pdf"];
  assert.equal(currentBatchIndex({ results: [ok("a")] }), 1);
  assert.equal(hasPendingBatchFiles({ filenames, results: [ok("a")], phase: "running" }), true);
  assert.equal(hasPendingBatchFiles({ filenames, results: [ok("a"), failed], phase: "running" }), false);
  assert.equal(hasPendingBatchFiles({ filenames, results: [ok("a"), failed], phase: "complete" }), false);
});

test("completed ids skip failed files", () => {
  assert.deepEqual(completedBatchIds([ok("a"), failed, ok("c")]), ["a", "c"]);
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
