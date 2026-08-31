import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { RecordAuthorityDetails } from "../components/analyze/record-authority-details.ts";

test("production record details render education enrichment and conflict in order", () => {
  const record = {
    kind: "education", authority: "code", confidence: "high", unknown_fields: ["result"],
    ai_enrichments: [{ name: "program", value: "Applied AI", authority: "ai" }],
    conflicts: [{ name: "study_dates", code_value: "2020", ai_value: "2021" }],
  };
  const html = renderToStaticMarkup(createElement(RecordAuthorityDetails, {
    record,
    leading: ["Example University", "2020"],
    labels: {
      authority: "Code-owned",
      confidence: "Confidence: high",
      aiEnrichment: "AI enrichment",
      conflict: "Conflict",
      unknownFields: "Unknown fields",
      codeValue: "Code",
      aiValue: "AI",
    },
  }));
  assert.match(html, /data-record-authority-details="education"/);
  const ordered = ["Example University", "2020", "Code-owned", "Confidence: high", "AI enrichment: program = Applied AI", "Conflict: study_dates · Code: 2020 · AI: 2021", "Unknown fields: result"];
  let cursor = -1;
  for (const value of ordered) {
    const next = html.indexOf(value);
    assert.ok(next > cursor, `${value} must render after the previous detail`);
    cursor = next;
  }
});
