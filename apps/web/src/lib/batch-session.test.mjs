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
  const token = store.start([file("a.pdf"), file("b.pdf"), file("c.pdf")], 100);
  store.record(ok("a"), file("a.pdf"), token);
  unsubscribe();
  store.record(failed, file("b.pdf"), token);
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
  const token = store.start([file("a.pdf")]);
  store.record(ok("a"), file("a.pdf"), token);
  store.complete();
  assert.equal(store.getSnapshot().batch.phase, "complete");
  store.clearBatch();
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a"]);
  assert.equal(store.getSnapshot().sessionFiles.get("a").name, "a.pdf");
});

test("cancel returns the waiting files and still highlights the in-flight result", () => {
  const store = new BatchSessionStore();
  const files = [file("a.pdf"), file("b.pdf"), file("c.pdf"), file("d.pdf")];
  const token = store.start(files);
  assert.equal(store.record(ok("a"), files[0], token), true);
  assert.deepEqual(store.cancel(), [files[2], files[3]]);
  assert.equal(store.getSnapshot().batch, null);
  assert.equal(store.record(ok("b"), files[1], token), false);
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a", "b"]);
  assert.equal(store.getSnapshot().sessionFiles.get("b").name, "b.pdf");
  assert.deepEqual(store.cancel(), []);
});

test("a stale token never records into a newer batch", () => {
  const store = new BatchSessionStore();
  const stale = store.start([file("a.pdf")]);
  store.cancel();
  const fresh = store.start([file("x.pdf")]);
  assert.equal(store.record(ok("a"), file("a.pdf"), stale), false);
  assert.deepEqual(store.getSnapshot().batch.results, []);
  assert.equal(store.record(ok("x"), file("x.pdf"), fresh), true);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a", "x"]);
});
