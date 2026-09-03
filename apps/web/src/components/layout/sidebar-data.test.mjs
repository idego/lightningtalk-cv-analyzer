import assert from "node:assert/strict";
import test from "node:test";

import { buildSidebarNav, isSidebarItemActive } from "./sidebar-data.ts";

test("uses Analyze, Dashboard, Settings as the top-level navigation", () => {
  assert.deepEqual(
    buildSidebarNav()[0].items.map(({ title, url }) => ({ title, url })),
    [
      { title: "Analyze", url: "/analyze" },
      { title: "Dashboard", url: "/dashboard" },
      { title: "Settings", url: "/settings" },
    ],
  );
});

test("keeps a sidebar section active on nested routes", () => {
  assert.equal(isSidebarItemActive("/dashboard", "/dashboard"), true);
  assert.equal(isSidebarItemActive("/dashboard/usage", "/dashboard"), true);
  assert.equal(isSidebarItemActive("/dashboard/usage/", "/dashboard/"), true);
});

test("does not match unrelated routes with the same prefix", () => {
  assert.equal(isSidebarItemActive("/dashboard-export", "/dashboard"), false);
  assert.equal(isSidebarItemActive("/analyze", "/dashboard"), false);
});
