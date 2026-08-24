import assert from "node:assert/strict";
import test from "node:test";

import { aiStatusMessage, partitionReviewFlags } from "./review-findings.ts";

const flag = (id, importance) => ({ id, importance });

test("partitions every flag into the recruiter-facing hierarchy", () => {
  const flags = [
    flag("a", "remaining"),
    flag("b", "attention"),
    flag("c", "worth_knowing"),
    flag("d", "remaining"),
  ];

  const grouped = partitionReviewFlags(flags);

  assert.deepEqual(grouped.attention.map((item) => item.id), ["b"]);
  assert.deepEqual(grouped.worthKnowing.map((item) => item.id), ["c"]);
  assert.deepEqual(grouped.remaining.map((item) => item.id), ["a", "d"]);
  assert.equal(
    grouped.attention.length + grouped.worthKnowing.length + grouped.remaining.length,
    flags.length,
  );
});

test("describes disabled, refusal and technical failure without a verdict", () => {
  assert.match(aiStatusMessage("disabled", null), /wyłączona/i);
  assert.match(aiStatusMessage("failed", "refusal"), /odmówił/i);
  assert.match(aiStatusMessage("failed", "timeout"), /nie udało/i);
  assert.equal(aiStatusMessage("succeeded", null), null);
});
