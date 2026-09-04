import assert from "node:assert/strict";
import test from "node:test";

import { BatchSessionStore } from "./batch-progress.ts";

const ok = (id) => ({ filename: `${id}.pdf`, status: "ok", report: { analysis_id: id } });
const failed = { filename: "b.pdf", status: "error", error: "boom" };
const file = (name) => ({ name });

test("batch progress and highlights survive unsubscribing and resubscribing", () => {
  const store = new BatchSessionStore();
  let notified = 0;
  const unsubscribe = store.subscribe(() => { notified += 1; });
  store.start([file("a.pdf"), file("b.pdf"), file("c.pdf")], 100);
  store.record(ok("a"), file("a.pdf"));
  unsubscribe();
  store.record(failed, file("b.pdf"));
  const snapshot = store.getSnapshot();
  assert.equal(notified, 2);
  assert.deepEqual(snapshot.batch, { filenames: ["a.pdf", "b.pdf", "c.pdf"], results: [ok("a"), failed], startedAt: 100, phase: "running" });
  assert.deepEqual([...snapshot.sessionIds], ["a"]);
  assert.equal(snapshot.sessionFiles.get("a").name, "a.pdf");
  assert.equal(snapshot.sessionFiles.has("b"), false);
});

test("snapshot identity changes only on updates", () => {
  const store = new BatchSessionStore();
  const before = store.getSnapshot();
  store.clearBatch();
  assert.equal(store.getSnapshot(), before);
  store.start([file("a.pdf")]);
  assert.notEqual(store.getSnapshot(), before);
});

test("complete then clear keeps highlights and files", () => {
  const store = new BatchSessionStore();
  store.start([file("a.pdf")]);
  store.record(ok("a"), file("a.pdf"));
  store.complete();
  assert.equal(store.getSnapshot().batch.phase, "complete");
  store.clearBatch();
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a"]);
  assert.equal(store.getSnapshot().sessionFiles.get("a").name, "a.pdf");
});

test("cancel aborts the signal, clears the batch, and returns unfinished files", () => {
  const store = new BatchSessionStore();
  const files = [file("a.pdf"), file("b.pdf"), file("c.pdf")];
  const signal = store.start(files);
  store.record(ok("a"), files[0]);
  assert.deepEqual(store.cancel(), [files[1], files[2]]);
  assert.equal(signal.aborted, true);
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a"]);
  assert.deepEqual(store.cancel(), []);
});
