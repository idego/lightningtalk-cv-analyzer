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

/**
 * Module-level store for the upload queue and the in-flight batch. It outlives
 * the analyze page so navigating away via the sidebar and back keeps the
 * queued files, the progress card, the "New" highlights, and the in-memory
 * uploads used for preview.
 */
export type BatchSession = {
  queue: readonly File[];
  batch: BatchProgress | null;
  sessionIds: ReadonlySet<string>;
  sessionFiles: ReadonlyMap<string, File>;
};

export type CancelledBatch = { requestId: string | null };

type Listener = () => void;

export class BatchSessionStore {
  private state: BatchSession = { queue: [], batch: null, sessionIds: new Set(), sessionFiles: new Map() };
  private listeners = new Set<Listener>();
  private running: File[] = [];
  private inFlight: { file: File; requestId: string } | null = null;
  private generation = 0;

  getSnapshot = (): BatchSession => this.state;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  enqueue(files: readonly File[]) {
    if (files.length) this.update({ queue: [...this.state.queue, ...files] });
  }

  removeQueued(index: number) {
    this.update({ queue: this.state.queue.filter((_, position) => position !== index) });
  }

  clearQueue() {
    if (this.state.queue.length) this.update({ queue: [] });
  }

  /** Begin a batch; the returned token identifies it so a cancelled batch cannot record into a later one. */
  start(files: File[], startedAt = Date.now()): number {
    this.running = files;
    this.inFlight = null;
    this.generation += 1;
    this.update({ queue: [], batch: { filenames: files.map((file) => file.name), results: [], startedAt, phase: "running" } });
    return this.generation;
  }

  /** Mark the file whose request is about to be sent, so a cancel can name it to the API. */
  beginFile(token: number, file: File, requestId: string) {
    if (token === this.generation) this.inFlight = { file, requestId };
  }

  /**
   * Stop the running batch. Every unfinished file, including the one in flight,
   * returns to the queue in upload order; the caller forwards the returned
   * request id to the API so that analysis is discarded before persistence.
   */
  cancel(): CancelledBatch {
    const { batch, queue } = this.state;
    if (!batch || batch.phase !== "running") return { requestId: null };
    const remaining = this.running.slice(batch.results.length);
    const requestId = this.inFlight?.requestId ?? null;
    this.generation += 1;
    this.running = [];
    this.inFlight = null;
    this.update({ batch: null, queue: [...remaining, ...queue] });
    return { requestId };
  }

  /**
   * Record a finished file. Returns false when the batch was cancelled meanwhile.
   * A success that slipped through before the cancel took effect is still
   * highlighted, and its file leaves the queue so it is not analyzed twice.
   */
  record(result: AnalyzeItemResult, file: File, token: number): boolean {
    const { batch, queue, sessionIds, sessionFiles } = this.state;
    const current = token === this.generation && batch !== null;
    if (!current && result.status === "error") return false;
    const results = current ? [...batch.results, result] : [result];
    const nextFiles = new Map(sessionFiles);
    if (result.status !== "error") nextFiles.set(result.report.analysis_id, file);
    this.update({
      batch: current ? { ...batch, results } : batch,
      queue: current ? queue : queue.filter((queued) => queued !== file),
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
