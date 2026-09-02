"use client";

import { useEffect, useMemo, useState } from "react";
import { Collapsible } from "@base-ui/react/collapsible";
import { Check, CircleAlert, Clock3 } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import type { AnalyzeBatchResponse, AnalyzeItemResult } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnalysisWorkspace, type AnalyzedFile } from "@/components/analyze/analysis-workspace";
import { RecentAnalyses } from "@/components/analyze/recent-analyses";
import { useCopy } from "@/lib/app-settings";
import { getAutoResearchOrchestrator, withAnalysisAccessToken } from "@/lib/auto-research";

const ACCEPT = ".pdf,.docx";
const ESTIMATED_SECONDS_PER_CV = 35;

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function AnalysisProgress({ files, completed, currentIndex, elapsedSeconds, complete }: { files: File[]; completed: AnalyzedFile[]; currentIndex: number; elapsedSeconds: number; complete: boolean }) {
  const { t } = useCopy();
  const completedByName = new Map(completed.map((entry) => [entry.file?.name ?? entry.result.filename, entry.result]));
  const estimatedRemaining = files.length * ESTIMATED_SECONDS_PER_CV - elapsedSeconds;
  return <Card aria-live="polite" className="analysis-flow-enter mx-auto max-w-3xl"><CardContent className="py-8">
    <div key={complete ? "complete" : "working"} className="analysis-status-swap flex flex-col items-center gap-4 text-center">{complete ? <span className="flex size-16 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"><Check className="size-7" /></span> : <ThinkingOrb state="working" size={64} theme="auto" aria-label={t("analyzing", { current: currentIndex + 1, total: files.length })} />}<div><h2 className="text-lg font-semibold">{complete ? t("analysisComplete") : t("analyzing", { current: currentIndex + 1, total: files.length })}</h2><p className="mt-1 max-w-lg truncate text-sm text-muted-foreground">{complete ? t("reportReady") : files[currentIndex]?.name}</p></div>{!complete ? <div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="size-4" />{t("elapsed", { time: formatElapsed(elapsedSeconds) })} · {estimatedRemaining > 0 ? t("estimatedRemaining", { time: formatElapsed(estimatedRemaining) }) : t("takingLonger")}</div> : null}</div>
    <ol className="mt-4 divide-y rounded-lg border px-3">{files.map((file, index) => { const result = completedByName.get(file.name); const active = index === currentIndex && !result; const usable = result && result.status !== "error"; return <li key={`${file.name}-${index}`} className="flex min-w-0 items-center gap-3 py-2.5 text-sm"><span className={`flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${usable ? "bg-emerald-500/15 text-emerald-700" : result?.status === "error" ? "bg-destructive/10 text-destructive" : active ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>{usable ? <Check className="size-3.5" /> : result?.status === "error" ? <CircleAlert className="size-3.5" /> : index + 1}</span><span className="min-w-0 flex-1 truncate">{file.name}</span><span className="shrink-0 text-xs text-muted-foreground">{result ? (usable ? t("completed") : t("failed")) : active ? t("analyzingStatus") : t("waiting")}</span></li>; })}</ol>
  </CardContent></Card>;
}

export function UploadPanel() {
  const { settings, t } = useCopy();
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [entries, setEntries] = useState<AnalyzedFile[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [completionPhase, setCompletionPhase] = useState<"analyzing" | "complete" | "collapsing">("analyzing");

  useEffect(() => { if (!loading) return; const startedAt = Date.now(); const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000); return () => window.clearInterval(timer); }, [loading]);
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
    setLoading(true); setCompletionPhase("analyzing"); setEntries([]); setCurrentIndex(0); setElapsedSeconds(0);
    for (let index = 0; index < acceptedFiles.length; index += 1) {
      const file = acceptedFiles[index]; setCurrentIndex(index); let result: AnalyzeItemResult;
      try { result = await analyzeFile(file); } catch (cause) { result = { filename: file.name, status: "error", error: cause instanceof Error ? cause.message : t("unexpectedAnalysisError") }; }
      setEntries((previous) => [...previous, { file, result }]);
      if (result.status !== "error") {
        void getAutoResearchOrchestrator()?.schedule(result.report, settings);
      }
    }
    setCompletionPhase("complete");
    await new Promise((resolve) => window.setTimeout(resolve, 450));
    setCompletionPhase("collapsing");
    await new Promise((resolve) => window.setTimeout(resolve, 180));
    setLoading(false);
    setCompletionPhase("analyzing");
  }

  function reset() { setFiles([]); setEntries([]); setError(null); setElapsedSeconds(0); setCurrentIndex(0); }
  function openHistorical(filename: string, report: Extract<AnalyzeItemResult, { report: unknown }>["report"]) {
    setEntries([{ file: null, result: { filename, status: "ok", report } }]);
  }
  if (loading) return <div className="space-y-6">
    <Collapsible.Root open={completionPhase !== "collapsing"}>
      <Collapsible.Panel className="h-[var(--collapsible-panel-height)] overflow-hidden opacity-100 transition-[height,opacity] duration-[180ms] ease-[var(--motion-ease-out)] data-ending-style:h-0 data-ending-style:opacity-0 data-starting-style:h-0 data-starting-style:opacity-0 motion-reduce:transition-none">
        <div className="p-px">
          <AnalysisProgress files={acceptedFiles} completed={entries} currentIndex={currentIndex} elapsedSeconds={elapsedSeconds} complete={completionPhase === "complete"} />
        </div>
      </Collapsible.Panel>
    </Collapsible.Root>
  </div>;
  if (entries.length) return <AnalysisWorkspace
    entries={entries}
    onBack={reset}
    analyzedCount={entries.length > 1 ? t("analyzedCount", { completed: entries.filter(({ result }) => result.status !== "error").length, total: entries.length }) : undefined}
  />;

  return <div className="mx-auto max-w-5xl space-y-6">
    <Card>
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
    </Card>
    <RecentAnalyses onOpen={openHistorical} />
  </div>;
}
