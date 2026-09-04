import assert from "node:assert/strict";
import test from "node:test";

import { translateCopy } from "./app-settings.ts";
import { feedbackContext } from "./feedback-context.ts";

const t = (key, values) => translateCopy("en", key, values);

test("describes feedback location and subject", () => {
  assert.deepEqual(
    feedbackContext({ source_category: "attention", source_key: "comparison-different-0" }, t),
    { section: "Needs attention", subject: "Declared country and phone country differ" },
  );
  assert.deepEqual(
    feedbackContext({ source_category: "report", source_key: "overall" }, t),
    { section: "CV overview", subject: "CV overview" },
  );
});


test("uses the shared Polish copy for feedback context", () => {
  const pl = (key, values) => translateCopy("pl", key, values);
  assert.deepEqual(
    feedbackContext({ source_category: "report", source_key: "overall" }, pl),
    { section: "Podsumowanie CV", subject: "Podsumowanie CV" },
  );
});
