"use client";

import { Badge } from "@/components/ui/badge";
import { useCopy, type CopyKey } from "@/lib/app-settings";

function confidenceKey(confidence: string): CopyKey {
  if (confidence === "high") return "confidenceHigh";
  if (confidence === "medium") return "confidenceMedium";
  return "confidenceLow";
}

function confidenceClass(confidence: string) {
  if (confidence === "high") {
    return "border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200";
  }
  if (confidence === "medium") {
    return "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200";
  }
  return "border-rose-500/40 bg-rose-500/10 text-rose-800 dark:text-rose-200";
}

export function ResearchConfidenceBadge({ confidence }: { confidence: string }) {
  const { t } = useCopy();

  return (
    <Badge variant="outline" className={confidenceClass(confidence)}>
      {t("confidenceWithValue", { value: t(confidenceKey(confidence)) })}
    </Badge>
  );
}

export function sortByResearchConfidence<T extends { confidence: string }>(items: readonly T[]): T[] {
  const rank: Record<string, number> = { high: 0, medium: 1, low: 2 };
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => (rank[left.item.confidence] ?? 3) - (rank[right.item.confidence] ?? 3) || left.index - right.index)
    .map(({ item }) => item);
}
