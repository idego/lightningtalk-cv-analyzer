import assert from "node:assert/strict";
import test from "node:test";
import { researchEligibility, selectStructuredRecords, timelineRecordMap } from "./understanding-selectors.ts";

const ai = (status = "succeeded") => ({ status, facts: { education: [], employment: [], contact: [] }, research_candidates: [] });
const field = (name, value, status = value == null ? "unknown" : "supported") => ({ name, value, status, authority: "code", confidence: "high", evidence: [] });

test("new reports prefer code records, preserve unknown fields, and suppress duplicate AI identities", () => {
  const report = {
    document_understanding: { records: [{ id: "code-1", kind: "education", section_id: "s", confidence: "high", date_range_ids: [], fields: [field("institution", "Example University"), field("program", null)] }], code_research_subjects: [], timeline_record_links: [] },
    ai_analysis: { ...ai(), facts: { contact: [], employment: [], education: [{ institution: "Example University", program: "AI Program", study_dates: null }] } },
  };
  const records = selectStructuredRecords(report);
  assert.equal(records.length, 1); assert.equal(records[0].authority, "code"); assert.deepEqual(records[0].unknown_fields, ["program"]);
});

test("legacy reports retain AI fallback", () => {
  const report = { document_understanding: null, ai_analysis: { ...ai(), facts: { contact: [], employment: [{ organization: "Legacy Ltd", role: "Engineer", employment_dates: null, location: null }], education: [] } } };
  assert.deepEqual(selectStructuredRecords(report).map(item => [item.organization, item.authority]), [["Legacy Ltd", "ai"]]);
});

test("code subjects keep public research eligible after document AI failure but overall switch wins", () => {
  const report = { document_understanding: { code_research_subjects: [{ category: "company" }], records: [], timeline_record_links: [] }, ai_analysis: ai("failed"), ai_features_enabled: true, ai_capabilities: { company_research: true } };
  assert.equal(researchEligibility(report).company, true);
  report.ai_features_enabled = false; assert.equal(researchEligibility(report).company, false);
});

test("explicit timeline relationships preserve identical displayed periods", () => {
  const report = { document_understanding: { timeline_record_links: [{ timeline_entry_id: "timeline-1", record_id: "record-1" }, { timeline_entry_id: "timeline-2", record_id: "record-2" }] } };
  assert.deepEqual([...timelineRecordMap(report)], [["timeline-1", "record-1"], ["timeline-2", "record-2"]]);
});
