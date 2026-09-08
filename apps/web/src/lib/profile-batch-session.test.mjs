import assert from "node:assert/strict";
import test from "node:test";

import { ProfileBatchSessionStore } from "./profile-batch-session.ts";

const file = (name) => ({ name, size: 1 });
let counter = 0;
const nextId = () => `item-${++counter}`;

function startBatch(store, names) {
  counter = 0;
  return store.start(names.map(file), 100, nextId);
}

test("items move through processing, completed, and failed while the batch stays current", () => {
  const store = new ProfileBatchSessionStore();
  const token = startBatch(store, ["a.pdf", "b.pdf", "c.pdf"]);
  store.beginItem(token, "item-1");
  assert.equal(store.getSnapshot().batch.items[0].status, "processing");
  store.completeItem(token, "item-1", "profile-a", "Ada");
  store.beginItem(token, "item-2");
  store.failItem(token, "item-2", "boom");
  const { batch, sessionIds } = store.getSnapshot();
  assert.deepEqual(batch.items.map((item) => item.status), ["completed", "failed", "queued"]);
  assert.equal(batch.items[0].profile_id, "profile-a");
  assert.equal(batch.items[0].candidate_name, "Ada");
  assert.equal(batch.items[1].error, "boom");
  assert.deepEqual([...sessionIds], ["profile-a"]);
});

test("progress survives unsubscribing so the batch continues after leaving the page", () => {
  const store = new ProfileBatchSessionStore();
  let notified = 0;
  const unsubscribe = store.subscribe(() => { notified += 1; });
  const token = startBatch(store, ["a.pdf", "b.pdf"]);
  store.beginItem(token, "item-1");
  unsubscribe();
  store.completeItem(token, "item-1", "profile-a", null);
  assert.equal(notified, 2);
  assert.equal(store.getSnapshot().batch.items[0].status, "completed");
  assert.equal(store.isCurrent(token), true);
});

test("clearing a finished batch requeues failed files with their errors", () => {
  const store = new ProfileBatchSessionStore();
  const token = startBatch(store, ["a.pdf", "b.pdf"]);
  store.completeItem(token, "item-1", "profile-a", null);
  store.failItem(token, "item-2", "too sparse");
  store.complete(token);
  assert.equal(store.getSnapshot().batch.phase, "complete");
  store.clearBatch(token);
  const snapshot = store.getSnapshot();
  assert.equal(snapshot.batch, null);
  assert.deepEqual(snapshot.queue.map((queued) => queued.name), ["b.pdf"]);
  assert.deepEqual(snapshot.failures, [{ filename: "b.pdf", error: "too sparse" }]);
  assert.deepEqual([...snapshot.sessionIds], ["profile-a"]);
});

test("cancel returns unfinished files to the queue and ignores stale records", () => {
  const store = new ProfileBatchSessionStore();
  store.enqueue([file("z.pdf")]);
  const token = startBatch(store, ["a.pdf", "b.pdf", "c.pdf"]);
  assert.deepEqual(store.getSnapshot().queue, []);
  store.completeItem(token, "item-1", "profile-a", null);
  store.beginItem(token, "item-2");
  store.cancel();
  const afterCancel = store.getSnapshot();
  assert.equal(afterCancel.batch, null);
  assert.deepEqual(afterCancel.queue.map((queued) => queued.name), ["b.pdf", "c.pdf"]);
  assert.equal(store.isCurrent(token), false);
  store.failItem(token, "item-2", "late failure");
  store.completeItem(token, "item-2", "profile-b", null);
  assert.equal(store.getSnapshot().batch, null);
  assert.deepEqual([...store.getSnapshot().sessionIds], ["profile-a", "profile-b"]);
});

test("enqueue and clearQueue reset earlier failures", () => {
  const store = new ProfileBatchSessionStore();
  const token = startBatch(store, ["a.pdf"]);
  store.failItem(token, "item-1", "boom");
  store.complete(token);
  store.clearBatch(token);
  assert.equal(store.getSnapshot().failures.length, 1);
  store.enqueue([file("b.pdf")]);
  assert.deepEqual(store.getSnapshot().failures, []);
  assert.deepEqual(store.getSnapshot().queue.map((queued) => queued.name), ["a.pdf", "b.pdf"]);
  store.removeQueued(0);
  assert.deepEqual(store.getSnapshot().queue.map((queued) => queued.name), ["b.pdf"]);
  store.clearQueue();
  assert.deepEqual(store.getSnapshot().queue, []);
});
