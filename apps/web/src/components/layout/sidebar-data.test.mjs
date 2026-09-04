import assert from "node:assert/strict";
import test from "node:test";

import { buildSidebarNav, isSidebarItemActive } from "./sidebar-data.ts";

test("uses Analyze, Dashboard, Feedback, Settings for feedback members", () => {
  assert.deepEqual(
    buildSidebarNav(true)[0].items.map(({ title, url }) => ({ title, url })),
    [
      { title: "Analyze", url: "/analyze" },
      { title: "Dashboard", url: "/dashboard" },
      { title: "Feedback", url: "/feedback" },
      { title: "Settings", url: "/settings" },
    ],
  );
});

test("does not expose Feedback to users without feedback access", () => {
  assert.deepEqual(
    buildSidebarNav(false)[0].items.map(({ title }) => title),
    ["Analyze", "Dashboard", "Settings"],
  );
});

test("keeps sidebar sections active on nested routes", () => {
  assert.equal(isSidebarItemActive("/dashboard/usage", "/dashboard"), true);
  assert.equal(isSidebarItemActive("/feedback/access", "/feedback"), true);
  assert.equal(isSidebarItemActive("/feedback/access/", "/feedback/"), true);
});

test("does not match unrelated routes with the same prefix", () => {
  assert.equal(isSidebarItemActive("/feedback-export", "/feedback"), false);
  assert.equal(isSidebarItemActive("/dashboard-export", "/dashboard"), false);
  assert.equal(isSidebarItemActive("/analyze", "/feedback"), false);
});
