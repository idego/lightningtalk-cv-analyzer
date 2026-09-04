"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import { Check, CircleAlert, Clock3, LoaderCircle, Trash2 } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import type { AnalysisHistoryItem, AnalysisReport, AnalyzeItemResult, DocumentSource } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnalysisWorkspace, type AnalyzedFile } from "@/components/analyze/analysis-workspace";
import { RecentAnalyses } from "@/components/analyze/recent-analyses";
import { useCopy } from "@/lib/app-settings";
import { getAutoResearchOrchestrator } from "@/lib/auto-research";
import { type BatchProgress, currentBatchIndex, deriveBatchStatuses, getBatchSessionStore, isSupportedCvFilename, resolveDocumentSource } from "@/lib/batch-progress";
import { parseAnalysisRoute, relativeHref, withAnalysisRoute, withoutAnalysisRoute } from "@/lib/analysis-route";

const ACCEPT = ".pdf,.docx";
const ESTIMATED_SECONDS_PER_CV = 35;
const COMPLETE_CARD_MS = 1200;
const CANCELLED_STATUS = 409;

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function reportResult(filename: string, report: AnalysisReport): AnalyzeItemResult {
  return {
    filename,
    status: report.base_analysis?.status === "partial" ? "partial" : "ok",
    report,
  };
}

function AnalysisProgress({ batch, elapsedSeconds, onCancel }: { batch: BatchProgress; elapsedSeconds: number; onCancel: () => void }) {
  const { t } = useCopy();
  const complete = batch.phase === "complete";
  const currentIndex = currentBatchIndex(batch);
  const statuses = deriveBatchStatuses(batch);
  const total = batch.filenames.length;
  const estimatedRemaining = total * ESTIMATED_SECONDS_PER_CV - elapsedSeconds;
  return <Card aria-live="polite" className="analysis-flow-enter mx-auto max-w-3xl"><CardContent className="py-8">
    <div key={complete ? "complete" : "working"} className="analysis-status-swap flex flex-col items-center gap-4 text-center">{complete ? <span className="flex size-16 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"><Check className="size-7" /></span> : <ThinkingOrb state="working" size={64} theme="auto" aria-label={t("analyzing", { current: currentIndex + 1, total })} />}<div><h2 className="text-lg font-semibold">{complete ? t("analysisComplete") : t("analyzing", { current: currentIndex + 1, total })}</h2><p className="mt-1 max-w-lg truncate text-sm text-muted-foreground">{complete ? t("batchResultsInHistory") : batch.filenames[currentIndex]}</p></div>{!complete ? <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="size-4" />{t("elapsed", { time: formatElapsed(elapsedSeconds) })} · {estimatedRemaining > 0 ? t("estimatedRemaining", { time: formatElapsed(estimatedRemaining) }) : t("takingLonger")}</div> : null}</div>
    <ol className="mt-4 divide-y rounded-lg border px-3">{batch.filenames.map((name, index) => { const status = statuses[index]; return <li key={`${name}-${index}`} className="flex min-w-0 items-center gap-3 py-2.5 text-sm"><span className={`flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${status === "completed" ? "bg-emerald-500/15 text-emerald-700" : status === "failed" ? "bg-destructive/10 text-destructive" : status === "analyzing" ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>{status === "completed" ? <Check className="size-3.5" /> : status === "failed" ? <CircleAlert className="size-3.5" /> : index + 1}</span><span className="min-w-0 flex-1 truncate">{name}</span><span className="shrink-0 text-xs text-muted-foreground">{status === "completed" ? t("completed") : status === "failed" ? t("failed") : status === "analyzing" ? t("analyzingStatus") : t("waiting")}</span></li>; })}</ol>
    {!complete ? <div className="mt-4 flex justify-center"><Button variant="outline" onClick={onCancel}>{t("cancel")}</Button></div> : null}
  </CardContent></Card>;
}

export function UploadPanel({ initialAnalysisId = null }: { initialAnalysisId?: string | null }) {
  const { settings, t } = useCopy();
  const store = getBatchSessionStore();
  const { queue: files, batch, sessionIds, sessionFiles } = useSyncExternalStore(store.subscribe, store.getSnapshot, store.getSnapshot);
  const [opened, setOpened] = useState<AnalyzedFile | null>(null);
  const [openedReadOnly, setOpenedReadOnly] = useState(false);
  const [routeLoading, setRouteLoading] = useState(Boolean(initialAnalysisId));
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const routeRequest = useRef(0);
  const openedFromHistoryPush = useRef(false);
  const running = batch?.phase === "running";
  const startedAt = batch?.startedAt;
  const historyVersion = sessionIds.size;

  useEffect(() => {
    if (!running || startedAt === undefined) return;
    const tick = () => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [running, startedAt]);

  const openRoutedAnalysis = useCallback(async (analysisId: string, shareToken: string | null) => {
    const requestId = ++routeRequest.current;
    setRouteLoading(true);
    setError(null);
    try {
      let nextOpened: AnalyzedFile;
      if (shareToken) {
        const headers = { "X-Analysis-Share-Token": shareToken };
        const response = await fetch(`/api/shared-analyses/${encodeURIComponent(analysisId)}`, { cache: "no-store", headers });
        if (!response.ok) throw new Error("analysis_unavailable");
        const body = await response.json() as { filename: string; has_document?: boolean; report: AnalysisReport };
        const file: DocumentSource | null = body.has_document
          ? { url: `/api/shared-analyses/${encodeURIComponent(analysisId)}/document`, name: body.filename, headers }
          : null;
        nextOpened = { file, result: reportResult(body.filename, body.report) };
      } else {
        const historyResponse = await fetch("/api/analyses", { cache: "no-store" });
        if (!historyResponse.ok) throw new Error("history_unavailable");
        const historyBody = await historyResponse.json() as { analyses?: AnalysisHistoryItem[] };
        const item = (historyBody.analyses ?? []).find((candidate) => candidate.analysis_id === analysisId);
        if (!item) throw new Error("analysis_unavailable");
        const response = await fetch(`/api/analyses/${encodeURIComponent(analysisId)}`, { cache: "no-store" });
        if (!response.ok) throw new Error("analysis_unavailable");
        const report = await response.json() as AnalysisReport;
        nextOpened = {
          file: resolveDocumentSource(item, store.getSnapshot().sessionFiles),
          result: reportResult(item.filename, report),
        };
      }
      if (routeRequest.current !== requestId) return;
      setOpened(nextOpened);
      setOpenedReadOnly(Boolean(shareToken));
    } catch {
      if (routeRequest.current !== requestId) return;
      setOpened(null);
      setOpenedReadOnly(false);
      setError(t("analysisUnavailable"));
    } finally {
      if (routeRequest.current === requestId) setRouteLoading(false);
    }
  }, [store, t]);

  useEffect(() => {
    function syncFromLocation() {
      openedFromHistoryPush.current = false;
      const { analysisId, shareToken } = parseAnalysisRoute(window.location.href);
      if (!analysisId) {
        routeRequest.current += 1;
        setOpened(null);
        setOpenedReadOnly(false);
        setRouteLoading(false);
        return;
      }
      void openRoutedAnalysis(analysisId, shareToken);
    }
    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    return () => window.removeEventListener("popstate", syncFromLocation);
  }, [openRoutedAnalysis]);

  const acceptedFiles = useMemo(() => files.filter((file) => isSupportedCvFilename(file.name)), [files]);
  const unsupportedFiles = useMemo(() => files.filter((file) => !isSupportedCvFilename(file.name)), [files]);
  function onFilesSelected(list: FileList | null) { if (list) store.enqueue(Array.from(list)); }

  async function analyzeFile(file: File, requestId: string): Promise<AnalyzeItemResult> {
    const form = new FormData(); form.append("file", file, file.name);
    const response = await fetch("/api/analyze", { method: "POST", body: form, headers: { "X-Report-Language": settings.reportLanguage, "X-Analysis-Request-Id": requestId } });
    const payload = await response.json().catch(() => null) as AnalysisReport | null;
    if (response.status === CANCELLED_STATUS) return { filename: file.name, status: "error", error: t("analysisCancelled") };
    if (!response.ok) throw new Error(t("analysisFailedWithStatus", { status: response.status }));
    if (!payload?.analysis_id) return { filename: file.name, status: "error", error: t("noResult") };
    return { filename: file.name, status: payload.base_analysis?.status === "partial" ? "partial" : "ok", report: payload };
  }

  async function submit() {
    setError(null); if (!acceptedFiles.length) { setError(t("addFile")); return; }
    if (running) return;
    const queue = acceptedFiles;
    setElapsedSeconds(0);
    const token = store.start(queue);
    for (const file of queue) {
      const requestId = crypto.randomUUID();
      store.beginFile(token, file, requestId);
      let result: AnalyzeItemResult;
      try { result = await analyzeFile(file, requestId); } catch (cause) { result = { filename: file.name, status: "error", error: cause instanceof Error ? cause.message : t("unexpectedAnalysisError") }; }
      if (result.status !== "error") void getAutoResearchOrchestrator()?.schedule(result.report, settings);
      if (!store.record(result, file, token)) return;
    }
    store.complete();
    await new Promise((resolve) => window.setTimeout(resolve, COMPLETE_CARD_MS));
    store.clearBatch();
  }

  function reset() { if (running) return; store.clearQueue(); setError(null); }
  function cancel() {
    const { requestId } = store.cancel();
    setElapsedSeconds(0);
    if (requestId) void fetch("/api/analyze/cancel", { method: "POST", headers: { "X-Analysis-Request-Id": requestId } }).catch(() => undefined);
  }
  function openHistorical(item: AnalysisHistoryItem, report: AnalysisReport) {
    routeRequest.current += 1;
    setError(null);
    setOpenedReadOnly(false);
    setOpened({ file: resolveDocumentSource(item, sessionFiles), result: reportResult(item.filename, report) });
    openedFromHistoryPush.current = true;
    window.history.pushState(null, "", relativeHref(withAnalysisRoute(window.location.href, item.analysis_id)));
  }
  function closeOpened() {
    if (openedFromHistoryPush.current) {
      openedFromHistoryPush.current = false;
      window.history.back();
      return;
    }
    routeRequest.current += 1;
    window.history.replaceState(null, "", relativeHref(withoutAnalysisRoute(window.location.href)));
    setOpened(null);
    setOpenedReadOnly(false);
    setRouteLoading(false);
    setError(null);
  }

  if (opened) return <AnalysisWorkspace entries={[opened]} onBack={closeOpened} readOnly={openedReadOnly} />;
  if (routeLoading) return <div className="mx-auto max-w-5xl"><Card><CardContent className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"><LoaderCircle className="size-5 animate-spin" />{t("loadingAnalysis")}</CardContent></Card></div>;

  return <div className="mx-auto max-w-5xl space-y-6">
    {batch ? <AnalysisProgress batch={batch} elapsedSeconds={elapsedSeconds} onCancel={cancel} /> : <Card>
      <CardHeader><CardTitle>{t("uploadTitle")}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <label className="flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-6 text-center" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onFilesSelected(event.dataTransfer.files); }}>
          <input type="file" className="hidden" multiple accept={ACCEPT} onChange={(event) => onFilesSelected(event.target.files)} />
          <p className="text-sm font-medium">{t("drop")}</p><p className="mt-1 text-xs text-muted-foreground">{t("accepted")}</p>
        </label>
        {files.length ? <div className="rounded-md border p-3 text-sm"><p className="mb-2 font-medium">{t("queued")} ({acceptedFiles.length} {t("valid")})</p><ul className="space-y-1 text-muted-foreground">{files.map((file, index) => <li key={`${file.name}-${index}`} className={`flex items-center gap-2 ${!isSupportedCvFilename(file.name) ? "text-destructive" : ""}`}><span className="min-w-0 flex-1 truncate">{file.name}</span><Button variant="ghost" size="icon" className="size-7 shrink-0 text-muted-foreground hover:text-destructive" aria-label={t("removeFile", { name: file.name })} onClick={() => store.removeQueued(index)}><Trash2 className="size-4" /></Button></li>)}</ul></div> : null}
        {unsupportedFiles.length ? <p className="text-sm text-destructive">{t("unsupportedFiles", { names: unsupportedFiles.map((file) => file.name).join(", ") })}</p> : null}
        <div className="flex items-center gap-3"><Button onClick={submit} disabled={!acceptedFiles.length}>{t("analyzeFiles")}</Button><Button variant="outline" onClick={reset}>{t("reset")}</Button></div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </CardContent>
    </Card>}
    <RecentAnalyses onOpen={openHistorical} refreshKey={historyVersion} highlightIds={sessionIds} />
  </div>;
}
