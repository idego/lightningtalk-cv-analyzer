import assert from "node:assert/strict";
import test from "node:test";

import { buildSidebarNav, isSidebarItemActive, titleFromPathname } from "./sidebar-data.ts";

test("includes restored builder and catalog alongside analyzer and feedback for feedback members", () => {
  assert.deepEqual(
    buildSidebarNav(true)[0].items.map(({ title, url }) => ({ title, url })),
    [
      { title: "Analyze", url: "/analyze" },
      { title: "Profile Builder", url: "/profile-builder" },
      { title: "Profiles", url: "/profiles" },
      { title: "Dashboard", url: "/dashboard" },
      { title: "Feedback", url: "/feedback" },
      { title: "Settings", url: "/settings" },
    ],
  );
});

test("does not expose Feedback to users without feedback access", () => {
  assert.deepEqual(
    buildSidebarNav(false)[0].items.map(({ title }) => title),
    ["Analyze", "Profile Builder", "Profiles", "Dashboard", "Settings"],
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

test("names nested template routes without changing analyzer navigation", () => {
  assert.equal(titleFromPathname("/profile-builder/templates/new"), "Template Creator");
  assert.equal(titleFromPathname("/profile-builder"), "Profile Builder");
  assert.equal(titleFromPathname("/profiles"), "Profiles");
});
