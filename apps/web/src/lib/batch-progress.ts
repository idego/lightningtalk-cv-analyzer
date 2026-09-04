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

/**
 * Module-level store for the in-flight upload batch. It outlives the analyze
 * page so navigating away via the sidebar and back keeps the progress card,
 * the "New" highlights, and the in-memory uploads used for preview.
 */
export type BatchSession = {
  batch: BatchProgress | null;
  sessionIds: ReadonlySet<string>;
  sessionFiles: ReadonlyMap<string, File>;
};

type Listener = () => void;

export class BatchSessionStore {
  private state: BatchSession = { batch: null, sessionIds: new Set(), sessionFiles: new Map() };
  private listeners = new Set<Listener>();
  private queue: File[] = [];
  private generation = 0;

  getSnapshot = (): BatchSession => this.state;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  /** Begin a batch; the returned token identifies it so a cancelled batch cannot record into a later one. */
  start(queue: File[], startedAt = Date.now()): number {
    this.queue = queue;
    this.generation += 1;
    this.update({ batch: { filenames: queue.map((file) => file.name), results: [], startedAt, phase: "running" } });
    return this.generation;
  }

  /**
   * Stop the running batch and hand back the files that were still waiting.
   * The file currently being analyzed is not returned: the API keeps working
   * on it, and its result is highlighted as new when it lands.
   */
  cancel(): File[] {
    const { batch } = this.state;
    if (!batch || batch.phase !== "running") return [];
    const remaining = this.queue.slice(batch.results.length + 1);
    this.generation += 1;
    this.queue = [];
    this.update({ batch: null });
    return remaining;
  }

  /** Record a finished file. Returns false when the batch was cancelled meanwhile; the result is still highlighted. */
  record(result: AnalyzeItemResult, file: File, token: number): boolean {
    const { batch, sessionIds, sessionFiles } = this.state;
    const current = token === this.generation && batch !== null;
    const results = current ? [...batch.results, result] : [result];
    const nextFiles = new Map(sessionFiles);
    if (result.status !== "error") nextFiles.set(result.report.analysis_id, file);
    this.update({
      batch: current ? { ...batch, results } : batch,
      sessionIds: new Set([...sessionIds, ...completedBatchIds(results)]),
      sessionFiles: nextFiles,
    });
    return current;
  }

  complete() {
    const { batch } = this.state;
    if (batch) this.update({ batch: { ...batch, phase: "complete" } });
  }

  clearBatch() {
    if (this.state.batch) this.update({ batch: null });
  }

  private update(patch: Partial<BatchSession>) {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener();
  }
}

let store: BatchSessionStore | null = null;

export function getBatchSessionStore() {
  return (store ??= new BatchSessionStore());
}
