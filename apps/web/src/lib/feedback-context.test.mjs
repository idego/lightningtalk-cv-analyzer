import assert from "node:assert/strict";
import test from "node:test";

import { feedbackContext } from "./feedback-context.ts";

test("describes feedback location and subject", () => {
  assert.deepEqual(
    feedbackContext({ source_category: "remaining", source_key: "comparison-same-0" }),
    { section: "Remaining signals", subject: "Declared country and phone country are consistent" },
  );
  assert.deepEqual(
    feedbackContext({ source_category: "report", source_key: "overall" }),
    { section: "CV overview", subject: "CV overview" },
  );
});
