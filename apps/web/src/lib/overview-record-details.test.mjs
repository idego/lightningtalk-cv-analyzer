import assert from "node:assert/strict";
import test from "node:test";
import { educationOverviewDetail, employmentOverviewDetail } from "./overview-record-details.ts";

test("compact education detail contains semantic values without authority metadata", () => {
  const detail = educationOverviewDetail({
    authority: "code", confidence: "high", unknown_fields: ["result"],
    program: "Computer Science", degree: "MSc", study_dates: "2020 - 2022",
  });

  assert.equal(detail, "Computer Science · MSc · 2020 - 2022");
  assert.doesNotMatch(detail, /code|high|unknown:/);
});

test("compact employment detail puts dates first and omits non-semantic metadata", () => {
  const detail = employmentOverviewDetail({
    authority: "code", confidence: "high", unknown_fields: ["location"],
    employment_dates: "2022 - Present", organization: "Example Ltd", location: "Warsaw",
  });

  assert.equal(detail, "2022 - Present · Example Ltd · Warsaw");
  assert.doesNotMatch(detail, /code|high|unknown:|Led migration/);
});
