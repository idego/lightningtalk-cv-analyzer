import type { AnalysisReport } from "@/lib/analyze-types";
import type { AppSettings } from "@/lib/app-settings";

export const AUTO_RESEARCH_MAX_CONCURRENCY = 2;
export type AutoResearchKind = "company" | "education" | "linkedin";
export type AutoResearchStatus = "pending" | "running" | "succeeded" | "failed" | "manual-action";
export type AutoResearchState = { status: AutoResearchStatus; result?: unknown; message?: string };

const LEDGER_PREFIX = "cv-auto-research-v1:";
const RESULT_KEYS = { company: "company_research", education: "education_research", linkedin: "linkedin_discovery" } as const;

export function effectiveAutoResearchKinds(settings: Pick<AppSettings, "aiEnabled" | "autoResearchEnabled" | "autoCompanyResearch" | "autoEducationResearch" | "autoLinkedinDiscovery">): AutoResearchKind[] {
  if (settings.aiEnabled === false || !settings.autoResearchEnabled) return [];
  return [settings.autoCompanyResearch && "company", settings.autoEducationResearch && "education", settings.autoLinkedinDiscovery && "linkedin"].filter(Boolean) as AutoResearchKind[];
}

export function eligibleAutoResearchKinds(report: AnalysisReport): Set<AutoResearchKind> {
  if (!report.analysis_access_token || report.ai_features_enabled === false) return new Set();
  const categories = new Set(report.ai_analysis.research_candidates.map((item) => item.category));
  const codeCategories = new Set(report.document_understanding?.code_research_subjects.map((item) => item.category) ?? []);
  return new Set([
    report.ai_capabilities?.company_research !== false && (categories.has("company") || codeCategories.has("company")) && "company",
    report.ai_capabilities?.education_research !== false && (categories.has("education_or_certification") || codeCategories.has("education")) && "education",
    report.ai_capabilities?.linkedin_research !== false && report.ai_analysis.status === "succeeded" && categories.has("linkedin") && "linkedin",
  ].filter(Boolean) as AutoResearchKind[]);
}

export function announcedAutoResearchKinds(
  reports: AnalysisReport[],
  settings: AppSettings,
): AutoResearchKind[] {
  const enabled = new Set(effectiveAutoResearchKinds(settings));
  const eligible = new Set(reports.flatMap((report) => [...eligibleAutoResearchKinds(report)]));
  return (["company", "education", "linkedin"] as AutoResearchKind[])
    .filter((kind) => enabled.has(kind) && eligible.has(kind));
}

type StorageLike = Pick<Storage, "getItem" | "setItem">;
type FetchLike = (input: string, init?: RequestInit) => Promise<Pick<Response, "ok" | "status" | "json">>;

export function createAutoResearchOrchestrator({
  fetcher,
  storage,
  maxConcurrency = AUTO_RESEARCH_MAX_CONCURRENCY,
}: { fetcher: FetchLike; storage: StorageLike; maxConcurrency?: number }) {
  const states = new Map<string, AutoResearchState>();
  const listeners = new Set<(analysisId: string, kind: AutoResearchKind, state: AutoResearchState) => void>();
  const queue: Array<() => Promise<void>> = [];
  let active = 0;
  const key = (analysisId: string, kind: AutoResearchKind) => `${analysisId}:${kind}`;
  const ledgerKey = (analysisId: string, kind: AutoResearchKind) => `${LEDGER_PREFIX}${key(analysisId, kind)}`;
  const readLedger = (analysisId: string, kind: AutoResearchKind) => {
    try { return storage.getItem(ledgerKey(analysisId, kind)); } catch { return null; }
  };
  const writeLedger = (analysisId: string, kind: AutoResearchKind, value: string) => {
    try { storage.setItem(ledgerKey(analysisId, kind), value); } catch { /* In-memory state still prevents duplicate requests in this page. */ }
  };

  function publish(analysisId: string, kind: AutoResearchKind, state: AutoResearchState) {
    states.set(key(analysisId, kind), state);
    listeners.forEach((listener) => listener(analysisId, kind, state));
  }
  function pump() {
    while (active < Math.max(1, maxConcurrency) && queue.length) {
      active += 1;
      const job = queue.shift()!;
      void job().finally(() => { active -= 1; pump(); });
    }
  }
  function enqueue(job: () => Promise<void>) { queue.push(job); pump(); }

  async function schedule(report: AnalysisReport, settings: AppSettings) {
    if (settings.aiEnabled === false || report.ai_features_enabled === false) return;
    const eligible = eligibleAutoResearchKinds(report);
    const completions = effectiveAutoResearchKinds(settings).filter((kind) => eligible.has(kind)).map((kind) => {
      const existing = states.get(key(report.analysis_id, kind));
      if (existing) return Promise.resolve();
      const persisted = readLedger(report.analysis_id, kind);
      if (persisted) {
        publish(report.analysis_id, kind, { status: persisted === "succeeded" ? "succeeded" : "manual-action", message: persisted === "succeeded" ? undefined : "Automatic research was already attempted. Use the manual action to try again." });
        return Promise.resolve();
      }
      writeLedger(report.analysis_id, kind, "pending");
      publish(report.analysis_id, kind, { status: "pending" });
      return new Promise<void>((resolve) => enqueue(async () => {
        writeLedger(report.analysis_id, kind, "running");
        publish(report.analysis_id, kind, { status: "running" });
        try {
          const suffix = kind === "linkedin" ? "linkedin/discovery" : kind;
          const response = await fetcher(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/${suffix}`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ accessToken: report.analysis_access_token, aiEnabled: settings.aiEnabled }),
          });
          const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
          if (!response.ok) throw new Error(`Automatic ${kind} research failed (${response.status}).`);
          writeLedger(report.analysis_id, kind, "succeeded");
          publish(report.analysis_id, kind, { status: "succeeded", result: payload[RESULT_KEYS[kind]] });
        } catch (cause) {
          writeLedger(report.analysis_id, kind, "failed");
          publish(report.analysis_id, kind, { status: "failed", message: cause instanceof Error ? cause.message : `Automatic ${kind} research failed.` });
        } finally { resolve(); }
      }));
    });
    await Promise.all(completions);
  }

  return {
    schedule,
    getState: (analysisId: string, kind: AutoResearchKind) => states.get(key(analysisId, kind)),
    subscribe(listener: (analysisId: string, kind: AutoResearchKind, state: AutoResearchState) => void) { listeners.add(listener); return () => { listeners.delete(listener); }; },
  };
}

let browserOrchestrator: ReturnType<typeof createAutoResearchOrchestrator> | undefined;
export function getAutoResearchOrchestrator() {
  if (typeof window === "undefined") return undefined;
  let storage: StorageLike;
  try { storage = window.sessionStorage; } catch {
    const values = new Map<string, string>();
    storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => { values.set(key, value); } };
  }
  browserOrchestrator ??= createAutoResearchOrchestrator({ fetcher: window.fetch.bind(window), storage });
  return browserOrchestrator;
}
