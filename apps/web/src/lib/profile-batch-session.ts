export type ProfileBatchItemStatus = "queued" | "processing" | "completed" | "failed";

export type ProfileBatchItem = {
  id: string;
  file: File;
  status: ProfileBatchItemStatus;
  profile_id: string | null;
  candidate_name: string | null;
  error: string | null;
};

export type ProfileBatch = {
  items: readonly ProfileBatchItem[];
  startedAt: number;
  phase: "running" | "complete";
};

export type ProfileBatchFailure = { filename: string; error: string };

/**
 * Module-level store for the Profile Builder upload queue and the in-flight
 * conversion batch. Like the Analyze batch store it outlives the page, so the
 * recruiter can open a finished profile or navigate elsewhere while the rest
 * of the batch keeps converting.
 */
export type ProfileBatchSession = {
  queue: readonly File[];
  batch: ProfileBatch | null;
  /** Profiles created by this browser session, highlighted as "New" in Recent profiles. */
  sessionIds: ReadonlySet<string>;
  /** Failures from the most recent finished batch; their files are back in the queue. */
  failures: readonly ProfileBatchFailure[];
};

type Listener = () => void;

export const PROFILE_BATCH_MAX_FILES = 10;
export const PROFILE_BATCH_MAX_BYTES = 10 * 1024 * 1024;

export function isProfileBatchFileTooLarge(file: Pick<File, "size">) {
  return file.size > PROFILE_BATCH_MAX_BYTES;
}

export function isSupportedCvFilename(filename: string) {
  return /\.(pdf|docx)$/i.test(filename);
}

export class ProfileBatchSessionStore {
  private state: ProfileBatchSession = { queue: [], batch: null, sessionIds: new Set(), failures: [] };
  private listeners = new Set<Listener>();
  private generation = 0;

  getSnapshot = (): ProfileBatchSession => this.state;

  subscribe = (listener: Listener) => {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  };

  enqueue(files: readonly File[]) {
    if (files.length) this.update({ queue: [...this.state.queue, ...files], failures: [] });
  }

  removeQueued(index: number) {
    this.update({ queue: this.state.queue.filter((_, position) => position !== index) });
  }

  clearQueue() {
    if (this.state.queue.length || this.state.failures.length) this.update({ queue: [], failures: [] });
  }

  /** Begin a batch; the returned token identifies it so a cancelled batch cannot record into a later one. */
  start(files: readonly File[], startedAt = Date.now(), makeId: () => string = () => globalThis.crypto.randomUUID()): number {
    this.generation += 1;
    const items = files.map((file): ProfileBatchItem => ({
      id: makeId(), file, status: "queued", profile_id: null, candidate_name: null, error: null,
    }));
    this.update({ queue: [], failures: [], batch: { items, startedAt, phase: "running" } });
    return this.generation;
  }

  /** True while `token` still names the running batch. */
  isCurrent(token: number) {
    return token === this.generation && this.state.batch?.phase === "running";
  }

  beginItem(token: number, itemId: string) {
    this.patchItem(token, itemId, { status: "processing", error: null });
  }

  completeItem(token: number, itemId: string, profileId: string, candidateName: string | null) {
    if (!this.isCurrent(token)) {
      // A success that landed after cancel still exists server-side; highlight it.
      this.update({ sessionIds: new Set([...this.state.sessionIds, profileId]) });
      return;
    }
    this.patchItem(token, itemId, { status: "completed", profile_id: profileId, candidate_name: candidateName, error: null });
    this.update({ sessionIds: new Set([...this.state.sessionIds, profileId]) });
  }

  failItem(token: number, itemId: string, error: string) {
    this.patchItem(token, itemId, { status: "failed", error });
  }

  /** Stop the running batch; unfinished files return to the queue in upload order. */
  cancel() {
    const { batch, queue } = this.state;
    if (!batch || batch.phase !== "running") return;
    this.generation += 1;
    const remaining = batch.items.filter((item) => item.status !== "completed").map((item) => item.file);
    this.update({ batch: null, queue: [...remaining, ...queue] });
  }

  complete(token: number) {
    const { batch } = this.state;
    if (token === this.generation && batch) this.update({ batch: { ...batch, phase: "complete" } });
  }

  /**
   * Remove the finished batch card. Failed files return to the queue so the
   * recruiter can retry them, and their errors are kept for display.
   */
  clearBatch(token: number) {
    const { batch, queue } = this.state;
    if (token !== this.generation || !batch) return;
    const failed = batch.items.filter((item) => item.status === "failed");
    this.update({
      batch: null,
      queue: [...failed.map((item) => item.file), ...queue],
      failures: failed.map((item) => ({ filename: item.file.name, error: item.error ?? "Conversion failed." })),
    });
  }

  private patchItem(token: number, itemId: string, patch: Partial<ProfileBatchItem>) {
    const { batch } = this.state;
    if (!this.isCurrent(token) || !batch) return;
    this.update({ batch: { ...batch, items: batch.items.map((item) => (item.id === itemId ? { ...item, ...patch } : item)) } });
  }

  private update(patch: Partial<ProfileBatchSession>) {
    this.state = { ...this.state, ...patch };
    for (const listener of this.listeners) listener();
  }
}

let store: ProfileBatchSessionStore | null = null;

export function getProfileBatchSessionStore() {
  return (store ??= new ProfileBatchSessionStore());
}
