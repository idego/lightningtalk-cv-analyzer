import type { AnalysisReport } from "@/lib/analyze-types";
import type { AppSettings } from "@/lib/app-settings";

export const AUTO_RESEARCH_MAX_CONCURRENCY = 2;
export type AutoResearchKind = "company" | "education" | "linkedin";
export type AutoResearchStatus = "pending" | "running" | "succeeded" | "failed" | "manual-action";
export type AutoResearchState = { status: AutoResearchStatus; result?: unknown; message?: string; httpStatus?: number };

const LEDGER_PREFIX = "cv-auto-research-v1:";
const RESULT_KEYS = { company: "company_research", education: "education_research", linkedin: "linkedin_discovery" } as const;

export function withAnalysisAccessToken(
  report: AnalysisReport,
  accessToken: string | undefined,
): AnalysisReport {
  if (report.analysis_access_token || !accessToken) return report;
  return { ...report, analysis_access_token: accessToken };
}

function supported(field: { value: string; status: string } | null | undefined) {
  return field?.status === "supported" && field.value.trim().length > 0;
}

export function researchEligibility(report: AnalysisReport) {
  if (report.base_analysis.status === "failed" || report.base_analysis.status === "unavailable") {
    return { company: false, education: false, linkedin: false };
  }
  const employment = report.base_analysis.employment.some(
    (record) => record.status === "accepted" && supported(record.organization),
  );
  const education = report.base_analysis.education.some(
    (record) => record.status === "accepted"
      && supported(record.institution),
  );
  const linkedin = supported(report.base_analysis.profile.candidate_name);
  return {
    company: report.ai_capabilities?.company_research !== false && employment,
    education: report.ai_capabilities?.education_research !== false && education,
    linkedin: report.ai_capabilities?.linkedin_research !== false && linkedin,
  };
}

export function effectiveAutoResearchKinds(settings: Pick<AppSettings, "aiEnabled" | "autoResearchEnabled" | "autoCompanyResearch" | "autoEducationResearch" | "autoLinkedinDiscovery">): AutoResearchKind[] {
  if (settings.aiEnabled === false || !settings.autoResearchEnabled) return [];
  return [settings.autoCompanyResearch && "company", settings.autoEducationResearch && "education", settings.autoLinkedinDiscovery && "linkedin"].filter(Boolean) as AutoResearchKind[];
}

export function eligibleAutoResearchKinds(report: AnalysisReport): Set<AutoResearchKind> {
  if (!report.analysis_access_token || report.ai_features_enabled === false) return new Set();
  const eligible = researchEligibility(report);
  return new Set([
    eligible.company && "company",
    eligible.education && "education",
    eligible.linkedin && "linkedin",
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
  const requests = new Map<string, Promise<void>>();
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

  function request(report: AnalysisReport, settings: AppSettings, kind: AutoResearchKind, allowRetry: boolean, refresh = false) {
    const requestKey = key(report.analysis_id, kind);
    const reportResult = report[RESULT_KEYS[kind]];
    if (reportResult && !refresh) {
      publish(report.analysis_id, kind, { status: "succeeded", result: reportResult });
      return Promise.resolve();
    }
    const activeRequest = requests.get(requestKey);
    if (activeRequest) return activeRequest;
    const existing = states.get(requestKey);
    if (existing && (existing.status === "pending" || existing.status === "running" || existing.status === "succeeded")) return Promise.resolve();
    if (existing && !allowRetry) return Promise.resolve();
    const persisted = readLedger(report.analysis_id, kind);
    if (persisted && !allowRetry) {
      publish(report.analysis_id, kind, { status: persisted === "succeeded" ? "succeeded" : "manual-action", message: persisted === "succeeded" ? undefined : "Automatic research was already attempted. Use the manual action to try again." });
      return Promise.resolve();
    }
    writeLedger(report.analysis_id, kind, "pending");
    publish(report.analysis_id, kind, { status: "pending" });
    const completion = new Promise<void>((resolve) => enqueue(async () => {
      writeLedger(report.analysis_id, kind, "running");
      publish(report.analysis_id, kind, { status: "running" });
      try {
        const suffix = kind === "linkedin" ? "linkedin/discovery" : kind;
        const response = await fetcher(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/${suffix}`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ accessToken: report.analysis_access_token, aiEnabled: settings.aiEnabled, refresh }),
        });
        const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
        if (!response.ok) throw Object.assign(new Error(`Automatic ${kind} research failed (${response.status}).`), { httpStatus: response.status });
        writeLedger(report.analysis_id, kind, "succeeded");
        publish(report.analysis_id, kind, { status: "succeeded", result: payload[RESULT_KEYS[kind]] });
      } catch (cause) {
        writeLedger(report.analysis_id, kind, "failed");
        publish(report.analysis_id, kind, { status: "failed", message: cause instanceof Error ? cause.message : `Automatic ${kind} research failed.`, httpStatus: (cause as { httpStatus?: number }).httpStatus });
      } finally { requests.delete(requestKey); resolve(); }
    }));
    requests.set(requestKey, completion);
    return completion;
  }

  async function schedule(report: AnalysisReport, settings: AppSettings) {
    if (settings.aiEnabled === false || report.ai_features_enabled === false) return;
    const eligible = eligibleAutoResearchKinds(report);
    const completions = effectiveAutoResearchKinds(settings)
      .filter((kind) => eligible.has(kind))
      .map((kind) => request(report, settings, kind, false));
    await Promise.all(completions);
  }

  function runManual(report: AnalysisReport, settings: AppSettings, kind: AutoResearchKind) {
    if (settings.aiEnabled === false || report.ai_features_enabled === false || !eligibleAutoResearchKinds(report).has(kind)) return Promise.resolve();
    return request(report, settings, kind, true);
  }

  function runRefresh(report: AnalysisReport, settings: AppSettings, kind: AutoResearchKind) {
    if (settings.aiEnabled === false || report.ai_features_enabled === false || !eligibleAutoResearchKinds(report).has(kind)) return Promise.resolve();
    states.delete(key(report.analysis_id, kind));
    return request(report, settings, kind, true, true);
  }

  return {
    schedule,
    runManual,
    runRefresh,
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
