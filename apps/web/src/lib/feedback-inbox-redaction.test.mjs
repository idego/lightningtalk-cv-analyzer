import assert from "node:assert/strict";
import test from "node:test";

const { redactInboxForRole } = await import("./feedback-inbox-redaction.ts");

const payload = {
  items: [
    { target_id: "t1", actor_hash: "h1", actor_email: "author@idego.io", comment: "x" },
    { target_id: "t2", actor_hash: "h2", actor_email: null },
  ],
  counts: { new: 2 },
  next_cursor: null,
};

test("owners keep the author email", () => {
  assert.deepEqual(redactInboxForRole(payload, "owner"), payload);
});

test("reviewers never receive author emails", () => {
  const redacted = redactInboxForRole(payload, "reviewer");
  assert.deepEqual(redacted, {
    items: [
      { target_id: "t1", actor_hash: "h1", comment: "x" },
      { target_id: "t2", actor_hash: "h2" },
    ],
    counts: { new: 2 },
    next_cursor: null,
  });
  assert.equal(JSON.stringify(redacted).includes("actor_email"), false);
});

test("non-inbox payloads pass through untouched", () => {
  assert.deepEqual(redactInboxForRole({ detail: "internal_secret_required" }, "reviewer"), { detail: "internal_secret_required" });
  assert.equal(redactInboxForRole(null, "reviewer"), null);
});
