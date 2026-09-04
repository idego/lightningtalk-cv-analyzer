import type { AnalysisHistoryItem, AnalyzeItemResult, DocumentSource } from "@/lib/analyze-types";

export type BatchFileStatus = "waiting" | "analyzing" | "completed" | "failed";

/** Sequential batch state: `results` holds one entry per finished file, in upload order. */
export type BatchProgress = {
  filenames: string[];
  results: AnalyzeItemResult[];
  startedAt: number;
  phase: "running" | "complete";
};

export function currentBatchIndex(batch: Pick<BatchProgress, "results">) {
  return batch.results.length;
}

export function hasPendingBatchFiles(batch: Pick<BatchProgress, "filenames" | "results" | "phase">) {
  return batch.phase === "running" && batch.results.length < batch.filenames.length;
}

export function deriveBatchStatuses(batch: Pick<BatchProgress, "filenames" | "results" | "phase">): BatchFileStatus[] {
  return batch.filenames.map((_, index) => {
    const result = batch.results[index];
    if (result) return result.status === "error" ? "failed" : "completed";
    return index === batch.results.length && batch.phase === "running" ? "analyzing" : "waiting";
  });
}

export function completedBatchIds(results: AnalyzeItemResult[]) {
  return results.flatMap((result) => (result.status === "error" ? [] : [result.report.analysis_id]));
}

export function isSupportedCvFilename(filename: string) {
  return /\.(pdf|docx)$/i.test(filename);
}

/** Prefer this session's in-memory upload, then the stored copy served by the API, else no preview. */
export function resolveDocumentSource(
  item: Pick<AnalysisHistoryItem, "analysis_id" | "filename" | "has_document">,
  sessionFiles: ReadonlyMap<string, File>,
): DocumentSource | null {
  const file = sessionFiles.get(item.analysis_id);
  if (file) return file;
  if (item.has_document) return { url: `/api/analyses/${encodeURIComponent(item.analysis_id)}/document`, name: item.filename };
  return null;
}
