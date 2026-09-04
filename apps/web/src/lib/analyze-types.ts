export type AnalysisStatus = "completed" | "partial" | "failed" | "unavailable";

export type Evidence = {
  source_id: string;
  excerpt: string;
  page_number?: number | null;
  start_offset?: number | null;
  end_offset?: number | null;
};

export type SupportedField = {
  value: string;
  status: "supported" | "ambiguous";
  evidence: Evidence[];
};

export type Profile = {
  candidate_name: SupportedField | null;
  declared_location: SupportedField | null;
  headline: SupportedField | null;
  summary: SupportedField | null;
  skills: SupportedField[];
  languages: SupportedField[];
};

export type AnalysisRecord = {
  id: string;
  status: "accepted" | "ambiguous";
  relation_status: "supported" | "ambiguous";
  added_by_reviewer: boolean;
};

export type EmploymentRecord = AnalysisRecord & {
  organization: SupportedField | null;
  role: SupportedField | null;
  start_date: SupportedField | null;
  end_date: SupportedField | null;
  location: SupportedField | null;
  relationship_type: SupportedField | null;
};

export type EducationRecord = AnalysisRecord & {
  institution: SupportedField | null;
  program: SupportedField | null;
  degree: SupportedField | null;
  certificate: SupportedField | null;
  start_date: SupportedField | null;
  end_date: SupportedField | null;
  location: SupportedField | null;
};

export type CompanyResearch = {
  status: "completed";
  outcome: "completed" | "insufficient_evidence";
  accessed_at: string;
  searches_performed: string[];
  search_limitations: string[];
  cache?: ResearchCacheProvenance;
  organizations: Array<{
    query_subject: string;
    existence: "supported" | "conflicting" | "insufficient_evidence";
    activity: string | null;
    operating_periods: Array<{
      from: string | null;
      to: string | null;
      ongoing: boolean;
      comment: string | null;
    }>;
    offices: Array<{
      address: string;
      comment: string | null;
    }>;
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
  cache?: ResearchCacheProvenance;
  credentials: Array<{
    institution: string | null;
    program: string | null;
    degree: string | null;
    program_exists: "supported" | "mismatch" | "evidence_unavailable";
    degree_exists: "supported" | "mismatch" | "evidence_unavailable";
    dates: string | null;
    city: string | null;
    country: string | null;
    cv_consistency: "supported" | "mismatch" | "evidence_unavailable";
    location_difference_for_review: string | null;
    confidence: "low" | "medium" | "high";
    uncertainty: string;
    findings: Array<{
      kind: string;
      summary: string;
      source_urls: string[];
      confidence: string;
      uncertainty: string;
    }>;
  }>;
};

export type ResearchCacheProvenance = {
  status: "hit" | "partial_hit" | "miss";
  format_version: string;
  subjects?: Array<{
    normalized_subject: string;
    status: "hit" | "miss";
    accessed_at: string | null;
  }>;
};

export type LinkedInDiscovery = {
  status: "completed";
  outcome: "completed" | "ambiguous" | "insufficient_evidence";
  linkedin_not_found: boolean;
  not_found_caveat: string;
  searches_performed: string[];
  search_limitations: string[];
  possible_profiles: Array<{
    profile_url: string;
    source_urls: string[];
    confidence: "low" | "medium" | "high";
    uncertainty: string;
    photo_visible: "true" | "false" | "unknown";
    photo_source_url: string | null;
    connection_count: {
      visibility: "visible" | "unknown";
      minimum: number | null;
      maximum: number | null;
      display: string | null;
      source_url: string | null;
    };
    connection_completeness_flag: boolean;
  }>;
};

export type AnalysisReport = {
  contract_version: "base-analysis-v2";
  analysis_id: string;
  analysis_access_token?: string;
  ai_features_enabled?: boolean;
  ai_capabilities?: {
    document_analysis: boolean;
    company_research: boolean;
    education_research: boolean;
    linkedin_research: boolean;
  };
  strategy: {
    name: "document-analysis";
    version: string;
  };
  source: {
    format: "pdf" | "docx";
    sha256: string;
    identity: string;
    block_count: number;
    conversion_status: "completed" | "partial" | "unsupported" | "failed";
  };
  base_analysis: {
    status: AnalysisStatus;
    profile: Profile;
    employment: EmploymentRecord[];
    education: EducationRecord[];
    pass_statuses: Record<string, {
      status: AnalysisStatus;
      attempt_count: number;
      latency_ms: number | null;
      failure_reason?: string | null;
      usage: Record<string, number>;
      model: string | null;
      reasoning_effort: "none" | "low";
      section_status?: "completed_with_records" | "not_present" | "unresolved" | "failed";
    }>;
    review: {
      status: AnalysisStatus;
      accepted_ids: string[];
      rejected: Array<Record<string, unknown>>;
      annotations?: Array<{ record_id: string; kind: "suspected_hallucination" | "unsupported_evidence" | "uncertain_relation" | "conflicting_relation" | "duplicate"; reason_code: string }>;
      merged_ids: string[][];
      merge_projections: Array<Record<string, unknown>>;
      relation_corrections: Array<Record<string, unknown>>;
      added_profile_fields: Array<"candidate_name" | "declared_location" | "headline" | "summary" | "skills" | "languages">;
      added_candidate_ids: string[];
      conflicts: Array<Record<string, unknown>>;
      coverage_gaps: Array<Record<string, unknown>>;
    };
  };
  mechanical: {
    phones: Array<Record<string, unknown>>;
    emails: Array<Record<string, unknown>>;
    literal_links: Array<Record<string, unknown>>;
    postal_candidates: Array<Record<string, unknown>>;
    accepted_postal_addresses: Array<Record<string, unknown>>;
    email_findings: Array<Record<string, unknown>>;
    location_resolution: Array<Record<string, unknown>>;
    eu_status: Record<string, unknown> | null;
    comparisons: Array<Record<string, unknown>>;
  };
  research: Record<string, unknown>;
  limitations: string[];
  versions: Record<string, string>;
  usage: Record<string, string | number | boolean | null>;
  company_research?: CompanyResearch;
  education_research?: EducationResearch;
  linkedin_discovery?: LinkedInDiscovery;
};

export type AnalyzeItemResult =
  | {
      filename: string;
      status: "ok" | "partial";
      report: AnalysisReport;
    }
  | {
      filename: string;
      status: "error";
      error: string;
    };

export type AnalysisHistoryItem = {
  analysis_id: string;
  filename: string;
  candidate_name: string | null;
  status: AnalysisStatus;
  strategy: AnalysisReport["strategy"]["name"] | null;
  created_at: string;
  /** True when the original uploaded document is still stored and can be fetched from `/api/analyses/{analysis_id}/document`. */
  has_document?: boolean;
};

/** A document the preview can render: the in-memory upload for this session, or a stored copy served by the API. */
export type StoredDocument = { url: string; name: string; headers?: Record<string, string> };
export type DocumentSource = File | StoredDocument;
