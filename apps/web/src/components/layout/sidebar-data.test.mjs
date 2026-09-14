import assert from "node:assert/strict";
import test from "node:test";

import { buildSidebarNav, isSidebarItemActive, titleFromPathname } from "./sidebar-data.ts";

test("keeps Profile Builder visible but disabled and shows feedback for feedback members", () => {
  assert.deepEqual(
    buildSidebarNav(true)[0].items.map(({ title, url, disabled }) => ({ title, url, disabled: Boolean(disabled) })),
    [
      { title: "Analyze", url: "/analyze", disabled: false },
      { title: "Profile Builder", url: "/profile-builder", disabled: true },
      { title: "Dashboard", url: "/dashboard", disabled: false },
      { title: "Feedback", url: "/feedback", disabled: false },
      { title: "Settings", url: "/settings", disabled: false },
    ],
  );
});

test("does not expose Feedback to users without feedback access", () => {
  assert.deepEqual(
    buildSidebarNav(false)[0].items.map(({ title }) => title),
    ["Analyze", "Profile Builder", "Dashboard", "Settings"],
  );
});

test("keeps sidebar sections active on nested routes", () => {
  assert.equal(isSidebarItemActive("/profiles", "/profile-builder"), true);
  assert.equal(isSidebarItemActive("/profiles/", "/profile-builder"), true);
  assert.equal(isSidebarItemActive("/profiles-export", "/profile-builder"), false);
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
