"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, CircleAlert, Clock3 } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import type { AnalysisHistoryItem, AnalysisReport, AnalyzeBatchResponse, AnalyzeItemResult } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnalysisWorkspace, type AnalyzedFile } from "@/components/analyze/analysis-workspace";
import { RecentAnalyses } from "@/components/analyze/recent-analyses";
import { useCopy } from "@/lib/app-settings";
import { getAutoResearchOrchestrator, withAnalysisAccessToken } from "@/lib/auto-research";
import { type BatchProgress, completedBatchIds, currentBatchIndex, deriveBatchStatuses, resolveDocumentSource } from "@/lib/batch-progress";

const ACCEPT = ".pdf,.docx";
const ESTIMATED_SECONDS_PER_CV = 35;
const COMPLETE_CARD_MS = 1200;

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function AnalysisProgress({ batch, elapsedSeconds }: { batch: BatchProgress; elapsedSeconds: number }) {
  const { t } = useCopy();
  const complete = batch.phase === "complete";
  const currentIndex = currentBatchIndex(batch);
  const statuses = deriveBatchStatuses(batch);
  const total = batch.filenames.length;
  const estimatedRemaining = total * ESTIMATED_SECONDS_PER_CV - elapsedSeconds;
  return <Card aria-live="polite" className="analysis-flow-enter mx-auto max-w-3xl"><CardContent className="py-8">
    <div key={complete ? "complete" : "working"} className="analysis-status-swap flex flex-col items-center gap-4 text-center">{complete ? <span className="flex size-16 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"><Check className="size-7" /></span> : <ThinkingOrb state="working" size={64} theme="auto" aria-label={t("analyzing", { current: currentIndex + 1, total })} />}<div><h2 className="text-lg font-semibold">{complete ? t("analysisComplete") : t("analyzing", { current: currentIndex + 1, total })}</h2><p className="mt-1 max-w-lg truncate text-sm text-muted-foreground">{complete ? t("batchResultsInHistory") : batch.filenames[currentIndex]}</p></div>{!complete ? <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="size-4" />{t("elapsed", { time: formatElapsed(elapsedSeconds) })} · {estimatedRemaining > 0 ? t("estimatedRemaining", { time: formatElapsed(estimatedRemaining) }) : t("takingLonger")}</div> : null}</div>
    <ol className="mt-4 divide-y rounded-lg border px-3">{batch.filenames.map((name, index) => { const status = statuses[index]; return <li key={`${name}-${index}`} className="flex min-w-0 items-center gap-3 py-2.5 text-sm"><span className={`flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${status === "completed" ? "bg-emerald-500/15 text-emerald-700" : status === "failed" ? "bg-destructive/10 text-destructive" : status === "analyzing" ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>{status === "completed" ? <Check className="size-3.5" /> : status === "failed" ? <CircleAlert className="size-3.5" /> : index + 1}</span><span className="min-w-0 flex-1 truncate">{name}</span><span className="shrink-0 text-xs text-muted-foreground">{status === "completed" ? t("completed") : status === "failed" ? t("failed") : status === "analyzing" ? t("analyzingStatus") : t("waiting")}</span></li>; })}</ol>
  </CardContent></Card>;
}

export function UploadPanel() {
  const { settings, t } = useCopy();
  const [files, setFiles] = useState<File[]>([]);
  const [batch, setBatch] = useState<BatchProgress | null>(null);
  const [opened, setOpened] = useState<AnalyzedFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [historyVersion, setHistoryVersion] = useState(0);
  const [sessionIds, setSessionIds] = useState<ReadonlySet<string>>(() => new Set());
  const sessionFiles = useRef(new Map<string, File>());
  const running = batch?.phase === "running";

  useEffect(() => {
    if (!running || !batch) return;
    const { startedAt } = batch;
    const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [running, batch]);
  const acceptedFiles = useMemo(() => files.filter((file) => /\.(pdf|docx)$/i.test(file.name)), [files]);
  function onFilesSelected(list: FileList | null) { if (list) setFiles((previous) => [...previous, ...Array.from(list)]); }

  async function analyzeFile(file: File): Promise<AnalyzeItemResult> {
    const form = new FormData(); form.append("files", file, file.name);
    const response = await fetch("/api/analyze", { method: "POST", body: form, headers: { "X-Report-Language": settings.reportLanguage } });
    const payload = await response.json().catch(() => ({})) as AnalyzeBatchResponse & { error?: string };
    if (!response.ok) throw new Error(t("analysisFailedWithStatus", { status: response.status }));
    const result = payload.results?.[0];
    if (!result) return { filename: file.name, status: "error", error: t("noResult") };
    return result.status === "error"
      ? { ...result, error: t("analysisFailed") }
      : {
          ...result,
          report: withAnalysisAccessToken(
            result.report,
            payload.analysis_access_token,
          ),
        };
  }

  async function submit() {
    setError(null); if (!acceptedFiles.length) { setError(t("addFile")); return; }
    if (running) return;
    const queue = acceptedFiles;
    setFiles([]); setElapsedSeconds(0);
    setBatch({ filenames: queue.map((file) => file.name), results: [], startedAt: Date.now(), phase: "running" });
    const results: AnalyzeItemResult[] = [];
    for (const file of queue) {
      let result: AnalyzeItemResult;
      try { result = await analyzeFile(file); } catch (cause) { result = { filename: file.name, status: "error", error: cause instanceof Error ? cause.message : t("unexpectedAnalysisError") }; }
      results.push(result);
      if (result.status !== "error") {
        sessionFiles.current.set(result.report.analysis_id, file);
        void getAutoResearchOrchestrator()?.schedule(result.report, settings);
      }
      setBatch((previous) => previous && { ...previous, results: [...results] });
      setSessionIds((previous) => new Set([...previous, ...completedBatchIds(results)]));
      setHistoryVersion((version) => version + 1);
    }
    setBatch((previous) => previous && { ...previous, phase: "complete" });
    await new Promise((resolve) => window.setTimeout(resolve, COMPLETE_CARD_MS));
    setBatch(null);
  }

  function reset() { if (running) return; setFiles([]); setError(null); }
  function openHistorical(item: AnalysisHistoryItem, report: AnalysisReport) {
    setOpened({ file: resolveDocumentSource(item, sessionFiles.current), result: { filename: item.filename, status: "ok", report } });
  }
  if (opened) return <AnalysisWorkspace entries={[opened]} onBack={() => setOpened(null)} />;

  return <div className="mx-auto max-w-5xl space-y-6">
    {batch ? <AnalysisProgress batch={batch} elapsedSeconds={elapsedSeconds} /> : <Card>
      <CardHeader><CardTitle>{t("uploadTitle")}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <label className="flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-6 text-center" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); onFilesSelected(event.dataTransfer.files); }}>
          <input type="file" className="hidden" multiple accept={ACCEPT} onChange={(event) => onFilesSelected(event.target.files)} />
          <p className="text-sm font-medium">{t("drop")}</p><p className="mt-1 text-xs text-muted-foreground">{t("accepted")}</p>
        </label>
        {files.length ? <div className="rounded-md border p-3 text-sm"><p className="mb-2 font-medium">{t("queued")} ({acceptedFiles.length} {t("valid")})</p><ul className="space-y-1 text-muted-foreground">{files.map((file, index) => <li key={`${file.name}-${index}`}>• {file.name}</li>)}</ul></div> : null}
        <div className="flex items-center gap-3"><Button onClick={submit} disabled={!acceptedFiles.length}>{t("analyzeFiles")}</Button><Button variant="outline" onClick={reset}>{t("reset")}</Button></div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </CardContent>
    </Card>}
    <RecentAnalyses onOpen={openHistorical} refreshKey={historyVersion} highlightIds={sessionIds} />
  </div>;
}
