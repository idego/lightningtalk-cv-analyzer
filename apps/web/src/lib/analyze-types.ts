export type Band = "green" | "amber" | "red" | "gray";

export type ComponentVersion = {
  name: string;
  version: string;
  source_url?: string;
};

export type Evidence = {
  page_id: string;
  page_number: number;
  start_offset: number;
  end_offset: number;
  excerpt: string;
};

type ProvenanceFields = {
  authority: "code";
  evidence: Evidence[];
  extractor_version: ComponentVersion;
  reference_data_version: ComponentVersion | null;
};

export type Finding = {
  signal: string;
  strength: string;
  observed: string;
  claimed: string | null;
  direction: string;
  weight: number;
  rationale: string;
  authority: "code" | null;
  evidence: Evidence[];
  extractor_version: ComponentVersion | null;
  reference_data_version: ComponentVersion | null;
  rule_id: string | null;
  score_impact: "weighted" | "none" | null;
  supporting_fact_ids: string[];
};

export type DeterministicCandidate = ProvenanceFields & {
  id: string;
  kind: string;
  value: string;
  subject: string;
  relation: string | null;
  source_context: string | null;
  label: string | null;
  relation_evidence: Evidence[];
  value_evidence: Evidence[];
};

export type DeterministicFact = DeterministicCandidate & {
  subject: string;
  source_candidate_ids: string[];
  resolved_level: string | null;
  resolved_name: string | null;
  resolved_record_ids: string[];
};

export type DeterministicObservation = ProvenanceFields & {
  id: string;
  kind: string;
  status: string;
  subject_ids: string[];
  values: string[];
  reason: string;
  relation: string | null;
  source_context: string | null;
  label: string | null;
  relation_evidence: Evidence[];
  value_evidence: Evidence[];
};

export type DeterministicScoringSignal = ProvenanceFields & {
  id: string;
  kind: string;
  value: string;
  supporting_fact_ids: string[];
  rule_id: string;
  ruleset_version: string;
  relation: string | null;
  source_context: string | null;
  label: string | null;
};

export type AnalysisReport = {
  score: number;
  band: Band;
  claimed_location: {
    raw: string | null;
    country_code: string | null;
    region: string | null;
    confidence: string;
  };
  findings: Finding[];
  ruleset_version: {
    version: string;
    weights_path: string;
    scoring_policy_version: string;
  };
  summary: string;
  disclaimer: string;
  signal_count: number;
  supporting_count: number;
  conflicting_count: number;
  deterministic: {
    ruleset_version: string;
    candidates: DeterministicCandidate[];
    facts: DeterministicFact[];
    observations: DeterministicObservation[];
    scoring_signals: DeterministicScoringSignal[];
  };
};

export type AnalyzeItemResult =
  | {
      filename: string;
      status: "ok";
      report: AnalysisReport;
    }
  | {
      filename: string;
      status: "error";
      error: string;
    };

export type AnalyzeBatchResponse = {
  results: AnalyzeItemResult[];
};
