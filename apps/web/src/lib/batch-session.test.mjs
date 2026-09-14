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
  store.record(ok("a"), file("a.pdf"), token, 0);
  unsubscribe();
  store.record(failed, file("b.pdf"), token, 1);
  const snapshot = store.getSnapshot();
  assert.equal(notified, 2);
  assert.deepEqual(snapshot.batch, { filenames: ["a.pdf", "b.pdf", "c.pdf"], results: [ok("a"), failed, null], active: [], startedAt: 100, phase: "running" });
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
  store.record(ok("a"), file("a.pdf"), token, 0);
  store.complete();
  assert.equal(store.getSnapshot().batch.phase, "complete");
  store.clearBatch();
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a"]);
  assert.equal(store.getSnapshot().sessionFiles.get("a").name, "a.pdf");
});

test("queue edits persist in the store", () => {
  const store = new BatchSessionStore();
  const files = [file("a.pdf"), file("b.pdf"), file("c.pdf")];
  store.enqueue(files);
  store.removeQueued(1);
  assert.deepEqual(store.getSnapshot().queue, [files[0], files[2]]);
  store.clearQueue();
  assert.deepEqual(store.getSnapshot().queue, []);
});

test("cancel restores unfinished files ahead of the queue and names every in-flight request", () => {
  const store = new BatchSessionStore();
  const files = [file("a.pdf"), file("b.pdf"), file("c.pdf"), file("d.pdf")];
  const token = store.start(files);
  assert.deepEqual(store.getSnapshot().queue, []);
  store.beginFile(token, 0, "req-a");
  store.beginFile(token, 1, "req-b");
  assert.deepEqual(store.getSnapshot().batch.active, [0, 1]);
  assert.equal(store.record(ok("b"), files[1], token, 1), true);
  assert.deepEqual(store.getSnapshot().batch.active, [0]);
  store.beginFile(token, 2, "req-c");
  store.enqueue([file("late.pdf")]);
  assert.deepEqual(store.cancel(), { requestIds: ["req-a", "req-c"] });
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual(store.getSnapshot().queue.map((queued) => queued.name), ["a.pdf", "c.pdf", "d.pdf", "late.pdf"]);
  assert.deepEqual(store.cancel(), { requestIds: [] });
});

test("after cancel a discarded result is ignored and a late success leaves the queue", () => {
  const store = new BatchSessionStore();
  const files = [file("a.pdf"), file("b.pdf")];
  const token = store.start(files);
  store.beginFile(token, 0, "req-a");
  store.cancel();
  assert.equal(store.record({ filename: "a.pdf", status: "error", error: "cancelled" }, files[0], token, 0), false);
  assert.deepEqual(store.getSnapshot().queue, files);
  assert.deepEqual([...store.getSnapshot().sessionIds], []);
  assert.equal(store.record(ok("a"), files[0], token, 0), false);
  assert.deepEqual(store.getSnapshot().queue, [files[1]]);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a"]);
  assert.equal(store.getSnapshot().sessionFiles.get("a"), files[0]);
});

test("a stale token never records into a newer batch", () => {
  const store = new BatchSessionStore();
  const stale = store.start([file("a.pdf")]);
  store.cancel();
  const fresh = store.start([file("x.pdf")]);
  assert.equal(store.record(ok("a"), file("a.pdf"), stale, 0), false);
  assert.deepEqual(store.getSnapshot().batch.results, [null]);
  assert.equal(store.record(ok("x"), file("x.pdf"), fresh, 0), true);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["a", "x"]);
});
