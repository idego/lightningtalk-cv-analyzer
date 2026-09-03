import assert from "node:assert/strict";
import test from "node:test";

import { isSidebarItemActive } from "./sidebar-data.ts";

test("keeps a sidebar section active on its nested routes", () => {
  assert.equal(isSidebarItemActive("/feedback", "/feedback"), true);
  assert.equal(isSidebarItemActive("/feedback/access", "/feedback"), true);
  assert.equal(isSidebarItemActive("/feedback/access/", "/feedback/"), true);
});

test("does not match unrelated routes with the same prefix", () => {
  assert.equal(isSidebarItemActive("/feedback-export", "/feedback"), false);
  assert.equal(isSidebarItemActive("/analyze", "/feedback"), false);
});
