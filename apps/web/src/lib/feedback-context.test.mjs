import assert from "node:assert/strict";
import test from "node:test";

import { feedbackContext } from "./feedback-context.ts";

test("describes feedback location and subject", () => {
  assert.deepEqual(
    feedbackContext({ source_category: "attention", source_key: "comparison-different-0" }),
    { section: "Needs attention", subject: "Declared country and phone country differ" },
  );
  assert.deepEqual(
    feedbackContext({ source_category: "report", source_key: "overall" }),
    { section: "CV overview", subject: "CV overview" },
  );
});
