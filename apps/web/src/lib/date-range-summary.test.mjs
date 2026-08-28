import assert from "node:assert/strict";
import test from "node:test";

import { summarizeDateRanges } from "./date-range-summary.ts";

test("summarizes adjacent education ranges without double counting the boundary year", () => {
  assert.equal(
    summarizeDateRanges(["2017 – 2020", "2013 – 2017"]),
    "2013–2020 · 7 yrs",
  );
});

test("merges overlapping employment ranges and counts present through the current month", () => {
  assert.equal(
    summarizeDateRanges(
      ["Feb 2025 – Jul 2025", "Oct 2024 – Dec 2025", "Jan 2022 – Sep 2024", "July 2019 – Present"],
      new Date("2026-08-26T12:00:00Z"),
    ),
    "2019–present · 7 yrs 2 mos",
  );
});

test("does not double count overlapping fixed month ranges", () => {
  assert.equal(
    summarizeDateRanges(["Jan 2020 – Dec 2020", "Jun 2020 – Dec 2021"]),
    "2020–2021 · 2 yrs",
  );
});

test("localizes Polish timeline summaries", () => {
  assert.equal(
    summarizeDateRanges(["Jan 2020 – Present"], new Date("2022-03-01T00:00:00Z"), "pl"),
    "2020–obecnie · 2 lata 3 miesiące",
  );
});

test("omits a summary when no complete range can be parsed", () => {
  assert.equal(summarizeDateRanges(["Graduated recently", "2020"]), null);
});
