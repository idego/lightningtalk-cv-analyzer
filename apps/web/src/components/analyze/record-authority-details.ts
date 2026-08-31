import { createElement, type ReactNode } from "react";
import type { DisplayRecord } from "@/lib/understanding-selectors";

export type RecordAuthorityDetailLabels = {
  authority: string;
  confidence: string;
  aiEnrichment: string;
  conflict: string;
  unknownFields: string;
  codeValue: string;
  aiValue: string;
};

export function recordAuthorityDetailParts(
  record: DisplayRecord,
  labels: RecordAuthorityDetailLabels,
  leading: Array<string | null | undefined> = [],
) {
  return {
    leading: leading.filter((value): value is string => Boolean(value)),
    authority: labels.authority,
    confidence: labels.confidence,
    enrichments: (record.ai_enrichments ?? []).map(
      (item) => `${labels.aiEnrichment}: ${item.name} = ${item.value}`,
    ),
    conflicts: (record.conflicts ?? []).map(
      (item) => `${labels.conflict}: ${item.name} · ${labels.codeValue}: ${item.code_value} · ${labels.aiValue}: ${item.ai_value}`,
    ),
    unknownFields: record.unknown_fields.length
      ? `${labels.unknownFields}: ${record.unknown_fields.join(", ")}`
      : null,
  };
}

/**
 * Renders the semantic record summary together with provenance metadata.
 * The summary stays compact, while the pills keep code and AI values visibly
 * distinct for human review.
 */
export function RecordAuthorityDetails({
  record,
  labels,
  leading = [],
}: {
  record: DisplayRecord;
  labels: RecordAuthorityDetailLabels;
  leading?: Array<string | null | undefined>;
}) {
  const parts = recordAuthorityDetailParts(record, labels, leading);
  const pills: ReactNode[] = [
    createElement(
      "span",
      { key: "authority", className: "rounded-full bg-muted px-2 py-0.5 text-[0.68rem] font-medium text-foreground" },
      parts.authority,
    ),
    createElement(
      "span",
      { key: "confidence", className: "rounded-full bg-muted px-2 py-0.5 text-[0.68rem] text-muted-foreground" },
      parts.confidence,
    ),
    ...parts.enrichments.map((value, index) => createElement(
      "span",
      { key: `enrichment-${index}`, className: "rounded-full bg-sky-500/10 px-2 py-0.5 text-[0.68rem] text-sky-700 dark:text-sky-300" },
      value,
    )),
    ...parts.conflicts.map((value, index) => createElement(
      "span",
      { key: `conflict-${index}`, className: "rounded-full bg-amber-500/10 px-2 py-0.5 text-[0.68rem] text-amber-800 dark:text-amber-200" },
      value,
    )),
    parts.unknownFields ? createElement(
      "span",
      { key: "unknown-fields", className: "rounded-full bg-muted px-2 py-0.5 text-[0.68rem] text-muted-foreground" },
      parts.unknownFields,
    ) : null,
  ];

  return createElement(
    "span",
    { "data-record-authority-details": record.kind, className: "inline-flex flex-wrap items-center gap-1.5" },
    parts.leading.length
      ? createElement("span", { key: "summary" }, parts.leading.join(" · "))
      : null,
    ...pills,
  );
}
