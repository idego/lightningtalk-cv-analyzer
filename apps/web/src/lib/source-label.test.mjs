import assert from "node:assert/strict";
import test from "node:test";

import { sourceLabel } from "./source-label.ts";

test("uses a readable hostname instead of an ordinal source label", () => {
  assert.equal(sourceLabel("https://www.example.edu/program?id=1"), "example.edu");
  assert.equal(sourceLabel("not a url"), "not a url");
});
