export type Band = "green" | "amber" | "red" | "gray";

export type Finding = {
  signal: string;
  strength: string;
  observed: string;
  claimed: string | null;
  direction: string;
  weight: number;
  rationale: string;
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
  summary: string;
  disclaimer: string;
  signal_count: number;
  supporting_count: number;
  conflicting_count: number;
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
