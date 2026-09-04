import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

const directory = mkdtempSync(path.join(tmpdir(), "feedback-access-"));
process.env.BETTER_AUTH_DB_PATH = path.join(directory, "auth.db");
process.env.ALLOWED_EMAIL_DOMAINS = "idego.io";
const access = await import("./feedback-access.ts");

test.after(() => rmSync(directory, { recursive: true, force: true }));

test("access is assigned directly by normalized email", () => {
  access.grantFeedbackAccess(" Owner@Idego.io ", "owner", "admin@idego.io");
  assert.equal(access.feedbackRole("owner@idego.io"), "owner");
  assert.equal(access.feedbackRole("OWNER@IDEGO.IO"), "owner");
  assert.equal(access.feedbackRole("other@idego.io"), null);
});

test("access rejects addresses outside allowed domains", () => {
  assert.throws(() => access.grantFeedbackAccess("person@example.com", "reviewer", "owner@idego.io"), /email_domain_not_allowed/);
});

test("the last owner cannot be removed", () => {
  assert.throws(() => access.revokeFeedbackAccess("owner@idego.io"), /last_owner_protected/);
  assert.throws(() => access.grantFeedbackAccess("owner@idego.io", "reviewer", "owner@idego.io"), /last_owner_protected/);
  access.grantFeedbackAccess("second@idego.io", "owner", "owner@idego.io");
  assert.equal(access.revokeFeedbackAccess("owner@idego.io"), true);
  assert.equal(access.feedbackRole("owner@idego.io"), null);
});

test("feedback collection setting is persistent", () => {
  assert.equal(access.feedbackCollectionEnabled(), true);
  access.setFeedbackCollectionEnabled(false, "second@idego.io");
  assert.equal(access.feedbackCollectionEnabled(), false);
});
