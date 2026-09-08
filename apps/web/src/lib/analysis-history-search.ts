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

/** Delete a group. The synthetic "Unassigned" group stays but loses its analyses. */
export function withoutGroup(groups: readonly AnalysisGroup[], groupId: string): AnalysisGroup[] {
  return groups.flatMap((group) => {
    if (group.group_id !== groupId) return [group];
    return group.is_unassigned ? [{ ...group, analyses: [] }] : [];
  });
}

/** Move one analysis into another group, keeping newest-first order inside the target. */
export function withMovedAnalysis(groups: readonly AnalysisGroup[], analysisId: string, targetGroupId: string): AnalysisGroup[] {
  const moved = groups.flatMap((group) => group.analyses).find((item) => item.analysis_id === analysisId);
  if (!moved) return [...groups];
  return groups.map((group) => {
    const analyses = group.analyses.filter((item) => item.analysis_id !== analysisId);
    if (group.group_id !== targetGroupId) return { ...group, analyses };
    const updated = { ...moved, group_id: group.is_unassigned ? null : group.group_id };
    return { ...group, analyses: [...analyses, updated].sort((a, b) => b.created_at.localeCompare(a.created_at)) };
  });
}

/** Update the has-note indicator of one analysis wherever it sits. */
export function withNoteState(groups: readonly AnalysisGroup[], analysisId: string, hasNote: boolean): AnalysisGroup[] {
  return groups.map((group) => ({
    ...group,
    analyses: group.analyses.map((item) => (item.analysis_id === analysisId ? { ...item, has_note: hasNote } : item)),
  }));
}
