export type UsageTotals = {
  requests: number;
  paid_requests: number;
  unpriced_requests: number;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: string | null;
  estimated_cost_pln: string | null;
  fx_rate: string;
  fx_version: string;
};

export type UsageOperationSummary = {
  key: string;
  attempts: number;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: string | null;
  estimated_cost_pln: string | null;
};

export type DeploymentUsageSummary = UsageTotals & {
  reports_processed: number;
  average_tokens_per_report: number;
  average_estimated_cost_usd: string | null;
  average_estimated_cost_pln: string | null;
  operations: UsageOperationSummary[];
};
