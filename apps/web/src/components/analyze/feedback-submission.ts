import type { AnalysisReport } from "@/lib/analyze-types";
import type { FeedbackResponse } from "@/lib/feedback-types";

export type FeedbackSubmissionBody = {
  rating: "helpful" | "not_helpful" | null;
  reason: "operation_failed" | "other" | null;
  comment: string | null;
  context_label: string | null;
  context_text: string | null;
  context_report: AnalysisReport | null;
};

export async function submitFeedback({
  analysisId,
  targetId,
  body,
  fetcher = fetch,
}: {
  analysisId: string;
  targetId: string;
  body: FeedbackSubmissionBody;
  fetcher?: typeof fetch;
}): Promise<FeedbackResponse> {
  const response = await fetcher(
    `/api/analyses/${encodeURIComponent(analysisId)}/feedback/${encodeURIComponent(targetId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) throw new Error(`feedback_submit_${response.status}`);
  return response.json() as Promise<FeedbackResponse>;
}
