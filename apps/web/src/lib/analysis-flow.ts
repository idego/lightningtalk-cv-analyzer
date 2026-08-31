import type { AnalyzeItemResult } from "@/lib/analyze-types";
import type { AppSettings } from "@/lib/app-settings";

type SuccessfulResult = Extract<AnalyzeItemResult, { status: "ok" }>;

export async function enrichThenScheduleResearch(
  result: SuccessfulResult,
  settings: AppSettings,
  enrich: (result: SuccessfulResult) => Promise<SuccessfulResult>,
  schedule: (report: SuccessfulResult["report"], settings: AppSettings) => void,
) {
  let next = result;
  let error: unknown;
  try {
    next = await enrich(result);
  } catch (cause) {
    error = cause;
    next = {
      ...result,
      report: {
        ...result.report,
        ai_analysis: {
          ...result.report.ai_analysis,
          status: "failed",
          failure_reason: "client_error",
          manual_retry_available: true,
        },
      },
    };
  }
  schedule(next.report, settings);
  return { result: next, error };
}
