"use client";

import { useCallback, useSyncExternalStore } from "react";
import { getAutoResearchOrchestrator, type AutoResearchKind, type AutoResearchState } from "@/lib/auto-research";

export function useAutoResearchState(analysisId: string, kind: AutoResearchKind) {
  const subscribe = useCallback((notify: () => void) => {
    const orchestrator = getAutoResearchOrchestrator();
    if (!orchestrator) return () => undefined;
    return orchestrator.subscribe((changedAnalysisId, changedKind) => {
      if (changedAnalysisId === analysisId && changedKind === kind) notify();
    });
  }, [analysisId, kind]);
  const getSnapshot = useCallback(
    (): AutoResearchState | undefined => getAutoResearchOrchestrator()?.getState(analysisId, kind),
    [analysisId, kind],
  );
  return useSyncExternalStore(subscribe, getSnapshot, () => undefined);
}
