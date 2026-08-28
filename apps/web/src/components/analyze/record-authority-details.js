import { createElement } from "react";

/** @param {any} record @param {(string | null | undefined)[]} leading */
export function recordAuthorityDetail(record, leading = []) {
  return [
    ...leading,
    `${record.authority} · ${record.confidence}`,
    record.ai_enrichments?.map(item => `${item.name}: ${item.value} (ai)`).join(", "),
    record.conflicts?.map(item => `conflict ${item.name}: ${item.ai_value}`).join(", "),
    record.unknown_fields?.length ? `unknown: ${record.unknown_fields.join(", ")}` : null,
  ].filter(Boolean).join(" · ");
}

/** @param {{ record: any, leading?: (string | null | undefined)[] }} props */
export function RecordAuthorityDetails({ record, leading = [] }) {
  return createElement("span", { "data-record-authority-details": record.kind }, recordAuthorityDetail(record, leading));
}
