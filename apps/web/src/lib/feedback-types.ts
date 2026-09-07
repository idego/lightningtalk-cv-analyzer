export type FeedbackTargetKind =
  | "review_finding"
  | "structured_fact"
  | "company_research_result"
  | "education_research_result"
  | "linkedin_research_result"
  | "operation_failure"
  | "report_overall";

export type FeedbackRating = "helpful" | "not_helpful";
export type FeedbackReason =
  | "inaccurate"
  | "missing_context"
  | "misleading_importance"
  | "duplicate"
  | "unclear"
  | "stale_research"
  | "wrong_source"
  | "other"
  | "operation_failed";

export type FeedbackResponse = {
  rating: FeedbackRating | null;
  reason: FeedbackReason | null;
  comment: string | null;
  updated_at: string;
};

export type FeedbackTarget = {
  target_id: string;
  kind: FeedbackTargetKind;
  source_category: string;
  source_key: string;
  versions: Record<string, string>;
  response: FeedbackResponse | null;
};

export type FeedbackManifest = {
  analysis_id: string;
  targets: FeedbackTarget[];
};

export function feedbackTarget(
  manifest: FeedbackManifest | null | undefined,
  kind: FeedbackTargetKind,
  sourceCategory: string,
  sourceKey: string,
) {
  return manifest?.targets.find(
    (target) =>
      target.kind === kind
      && target.source_category === sourceCategory
      && target.source_key === sourceKey,
  ) ?? null;
}
