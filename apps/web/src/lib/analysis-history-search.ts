import type { AnalysisHistoryItem } from "./analyze-types";

function normalize(value: string): string {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").replace(/[łŁ]/g, "l").toLowerCase();
}

/** Match every word across candidate name and filename, without changing history order. */
export function searchAnalysisHistory(items: readonly AnalysisHistoryItem[], query: string): AnalysisHistoryItem[] {
  const words = normalize(query).trim().split(/\s+/).filter(Boolean);
  return items.filter((item) => {
    const text = normalize(`${item.candidate_name ?? ""} ${item.filename}`);
    return words.every((word) => text.includes(word));
  });
}
