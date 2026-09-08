import type { AnalysisGroup, AnalysisHistoryItem } from "./analyze-types";

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

/**
 * Apply a candidate/filename search to every group without reordering groups.
 * With an empty query every group is returned as-is; with a query only groups
 * that still contain a match are kept, each narrowed to its matching analyses.
 */
export function searchAnalysisGroups(groups: readonly AnalysisGroup[], query: string): AnalysisGroup[] {
  if (!query.trim()) return [...groups];
  return groups
    .map((group) => ({ ...group, analyses: searchAnalysisHistory(group.analyses, query) }))
    .filter((group) => group.analyses.length > 0);
}

/** Total number of analyses across groups. */
export function countAnalyses(groups: readonly AnalysisGroup[]): number {
  return groups.reduce((total, group) => total + group.analyses.length, 0);
}

/** Remove one analysis from whichever group holds it. */
export function withoutAnalysis(groups: readonly AnalysisGroup[], analysisId: string): AnalysisGroup[] {
  return groups.map((group) => ({
    ...group,
    analyses: group.analyses.filter((item) => item.analysis_id !== analysisId),
  }));
}

/** Delete a group. The synthetic "Rest" group stays but loses its analyses. */
export function withoutGroup(groups: readonly AnalysisGroup[], groupId: string): AnalysisGroup[] {
  return groups.flatMap((group) => {
    if (group.group_id !== groupId) return [group];
    return group.is_rest ? [{ ...group, analyses: [] }] : [];
  });
}
