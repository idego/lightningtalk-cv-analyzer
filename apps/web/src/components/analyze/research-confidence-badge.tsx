"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy, type CopyKey } from "@/lib/app-settings";

function confidenceKey(confidence: string): CopyKey {
  if (confidence === "high") return "confidenceHigh";
  if (confidence === "medium") return "confidenceMedium";
  return "confidenceLow";
}

function confidenceTone(confidence: string) {
  if (confidence === "high") {
    return { shell: "bg-emerald-500/10", dot: "bg-emerald-600 dark:bg-emerald-400" };
  }
  if (confidence === "medium") {
    return { shell: "bg-amber-500/10", dot: "bg-amber-600 dark:bg-amber-400" };
  }
  return { shell: "bg-rose-500/10", dot: "bg-rose-600 dark:bg-rose-400" };
}

export function ResearchConfidenceBadge({ confidence }: { confidence: string }) {
  const { t } = useCopy();
  const level = confidence === "high" ? 3 : confidence === "medium" ? 2 : 1;
  const tone = confidenceTone(confidence);
  const label = t("confidenceWithValue", { value: t(confidenceKey(confidence)) });

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            aria-label={label}
            className={`inline-flex h-6 items-center gap-1 rounded-full px-2 outline-none focus-visible:ring-2 focus-visible:ring-ring ${tone.shell}`}
          >
            {[1, 2, 3].map((dot) => (
              <span
                key={dot}
                aria-hidden="true"
                className={`size-1.5 rounded-full ${dot <= level ? tone.dot : "bg-muted-foreground/20"}`}
              />
            ))}
          </span>
        }
      />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function sortByResearchConfidence<T extends { confidence: string }>(items: readonly T[]): T[] {
  const rank: Record<string, number> = { high: 0, medium: 1, low: 2 };
  return items
    .map((item, index) => ({ item, index }))
    .sort((left, right) => (rank[left.item.confidence] ?? 3) - (rank[right.item.confidence] ?? 3) || left.index - right.index)
    .map(({ item }) => item);
}
