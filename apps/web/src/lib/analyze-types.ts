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

export type ReviewEvidence = {
  page_id: string;
  page_number?: number;
  line_id?: string;
  start_offset?: number;
  end_offset?: number;
  excerpt: string;
};

export type ReviewImportance = "attention" | "worth_knowing" | "remaining";

export type ReviewFlag = {
  id: string;
  source: "code" | "ai";
  authority: "code" | "ai";
  category: string;
  status: string;
  importance: ReviewImportance;
  confidence: string;
  observation: string;
  reason: string;
  limitation: string | null;
  evidence: ReviewEvidence[];
};

export type ChecklistId =
  | "contact"
  | "education"
  | "employment"
  | "timeline"
  | "duration_claims"
  | "relationships"
  | "document_quality"
  | "protected_boundaries";

type AIFactBase = {
  status: "present" | "ambiguous";
  authority: "ai";
  source: "document_analyzer";
  evidence: ReviewEvidence[];
};

export type AIContactFact = AIFactBase & {
  kind: "phone" | "stated_location";
  value: string;
};

export type AIEducationFact = AIFactBase & {
  kind: "education";
  institution: string;
  program: string | null;
  study_dates: string | null;
};

export type AIEmploymentFact = AIFactBase & {
  kind: "employment";
  organization: string;
  role: string;
  employment_dates: string | null;
  location: string | null;
  relationship_type: string | null;
};

export type AIAnalysis = {
  status: "disabled" | "succeeded" | "failed";
  failure_reason: "timeout" | "refusal" | "invalid_response" | "client_error" | null;
  authority: "ai";
  source: "document_analyzer";
  model: {
    provider: "openai";
    configured: string;
    response: string | null;
    reasoning_effort: string;
  };
  versions: {
    prompt: string;
    schema: string;
    input_contract: string;
    deterministic_observations: string;
  };
  usage: Record<string, unknown> | null;
  facts: {
    contact: AIContactFact[];
    education: AIEducationFact[];
    employment: AIEmploymentFact[];
  };
  findings: unknown[];
  unknowns: unknown[];
  research_candidates: Array<{
    category: "company" | "education_or_certification" | "linkedin";
    query_subject: string;
  }>;
  checklist: Record<ChecklistId, { checked: boolean; issue_count: number }>;
  analysis_limitations: string[];
};

export type CompanyResearch = {
  status: "completed";
  outcome: "completed" | "insufficient_evidence";
  accessed_at: string;
  searches_performed: string[];
  search_limitations: string[];
  organizations: Array<{
    query_subject: string;
    existence: "supported" | "conflicting" | "insufficient_evidence";
    activity: string | null;
    operating_dates: string | null;
    location: string | null;
    relationship: string | null;
    official_website: string | null;
    company_pages: string[];
    registries: string[];
    confidence: "low" | "medium" | "high";
    uncertainty: string;
    findings: Array<{
      kind: string;
      summary: string;
      source_urls: string[];
      confidence: string;
      uncertainty: string;
    }>;
    limited_online_presence: boolean;
    limited_online_presence_reason: string | null;
  }>;
};

export type EducationResearch = {
  status: "completed";
  outcome: "completed" | "insufficient_evidence";
  accessed_at: string;
  searches_performed: string[];
  search_limitations: string[];
  credentials: Array<{
    institution: string | null;
    program: string | null;
    degree: string | null;
    certificate: string | null;
    institution_exists: "supported" | "mismatch" | "evidence_unavailable";
    program_exists: "supported" | "mismatch" | "evidence_unavailable";
    degree_exists: "supported" | "mismatch" | "evidence_unavailable";
    certificate_exists: "supported" | "mismatch" | "evidence_unavailable";
    dates: string | null;
    accreditation_status: "established" | "not_established" | "evidence_unavailable";
    city: string | null;
    country: string | null;
    cv_consistency: "supported" | "mismatch" | "evidence_unavailable";
    location_difference_for_review: string | null;
    confidence: "low" | "medium" | "high";
    uncertainty: string;
    findings: Array<{ kind: string; summary: string; source_urls: string[]; confidence: string; uncertainty: string }>;
  }>;
};

export type LinkedInDiscovery = {
  status: "completed"; outcome: "completed" | "ambiguous" | "insufficient_evidence";
  linkedin_not_found: boolean; not_found_caveat: string; searches_performed: string[]; search_limitations: string[];
  possible_profiles: Array<{ profile_url: string; confidence: "low" | "medium" | "high"; uncertainty: string;
    match_evidence: Array<{ field: string; cv_value: string; profile_value: string; source_urls: string[] }>;
    conflicts: Array<{ field: string; summary: string; source_urls: string[] }>;
    photo_visible: "true" | "false" | "unknown"; photo_source_url: string | null;
    connection_count: { visibility: "visible" | "unknown"; minimum: number | null; maximum: number | null; display: string | null; source_url: string | null };
    connection_completeness_flag: boolean }>;
};

export type LinkedInComparison = { status: "completed"; profile_url: string; searches_performed: string[]; limitations: string[]; comparisons: Array<{
  field: "companies" | "roles" | "dates" | "stated_location" | "education"; status: "consistent" | "mismatch_for_review" | "unknown";
  cv_value: string | null; profile_value: string | null; summary: string; source_urls: string[]; confidence: string; uncertainty: string }> };

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
  analysis_id: string;
  analysis_access_token?: string;
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
  ai_analysis: AIAnalysis;
  checklist: {
    checks: Record<ChecklistId, { checked: boolean; issue_count: number }>;
    flags: ReviewFlag[];
  };
  company_research?: CompanyResearch;
  education_research?: EducationResearch;
  linkedin_discovery?: LinkedInDiscovery;
  linkedin_comparison?: LinkedInComparison;
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
