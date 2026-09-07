import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import test from "node:test";
import { profileBuilderOwnerToken } from "./profile-builder-owner.ts";

function environment(t, values) {
  const previous = Object.fromEntries(Object.keys(values).map(key => [key, process.env[key]]));
  const apply = entries => {
    for (const [key, value] of Object.entries(entries)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  };
  apply(values);
  t.after(() => apply(previous));
}

test("existing profile/template owner keys keep their original server-only namespace", t => {
  environment(t, { BETTER_AUTH_SECRET: "synthetic-profile-secret", NODE_ENV: "production" });
  const expected = createHmac("sha256", "synthetic-profile-secret")
    .update("cv-analysis-history:synthetic-owner").digest("hex");
  assert.equal(profileBuilderOwnerToken("synthetic-owner"), expected);
  assert.notEqual(profileBuilderOwnerToken("other-owner"), expected);
});

test("production cannot silently fall back to a public development secret", t => {
  environment(t, { BETTER_AUTH_SECRET: undefined, NODE_ENV: "production" });
  assert.throws(() => profileBuilderOwnerToken("synthetic-owner"), /BETTER_AUTH_SECRET is required/);
});

test("local development keeps access to profiles created with the old default", t => {
  environment(t, { BETTER_AUTH_SECRET: undefined, NODE_ENV: "development" });
  const expected = createHmac("sha256", "local-dev-secret-change-this-0123456789")
    .update("cv-analysis-history:local-dev-user").digest("hex");
  assert.equal(profileBuilderOwnerToken("local-dev-user"), expected);
});
