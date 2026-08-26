"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, CircleAlert, Clock3 } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import type { AnalyzeBatchResponse, AnalyzeItemResult } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnalysisWorkspace, type AnalyzedFile } from "@/components/analyze/analysis-workspace";
import { RecentAnalyses } from "@/components/analyze/recent-analyses";
import { useCopy } from "@/lib/app-settings";
import { effectiveAutoResearchKinds, getAutoResearchOrchestrator, type AutoResearchKind } from "@/lib/auto-research";

const ACCEPT = ".pdf,.docx";
const ESTIMATED_SECONDS_PER_CV = 35;

function formatElapsed(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

const researchLabels: Record<AutoResearchKind, string> = { company: "company", education: "education", linkedin: "LinkedIn discovery" };
function ResearchNotice({ kinds }: { kinds: AutoResearchKind[] }) {
  if (!kinds.length) return null;
  return <p className="text-xs text-muted-foreground">Auto research: {kinds.map((kind) => researchLabels[kind]).join(", ")}.</p>;
}

function AnalysisProgress({ files, completed, currentIndex, elapsedSeconds, researchKinds }: { files: File[]; completed: AnalyzedFile[]; currentIndex: number; elapsedSeconds: number; researchKinds: AutoResearchKind[] }) {
  const completedByName = new Map(completed.map((entry) => [entry.file?.name ?? entry.result.filename, entry.result]));
  const estimatedRemaining = files.length * ESTIMATED_SECONDS_PER_CV - elapsedSeconds;
  return <Card aria-live="polite" className="mx-auto max-w-3xl"><CardContent className="py-8">
    <div className="flex flex-col items-center gap-4 text-center"><ThinkingOrb state="working" size={64} theme="auto" aria-label={`Analyzing CV ${currentIndex + 1} of ${files.length}`} /><div><h2 className="text-lg font-semibold">Analyzing {currentIndex + 1} of {files.length}</h2><p className="mt-1 max-w-lg truncate text-sm text-muted-foreground">{files[currentIndex]?.name}</p></div><div className="flex items-center gap-2 text-xs text-muted-foreground"><Clock3 className="size-4" />Elapsed {formatElapsed(elapsedSeconds)} · {estimatedRemaining > 0 ? `Estimated remaining about ${formatElapsed(estimatedRemaining)}` : "Taking longer than usual"}</div></div>
    {researchKinds.length ? <div className="mt-5 rounded-md bg-muted/30 p-3"><ResearchNotice kinds={researchKinds} /></div> : null}
    <ol className="mt-4 divide-y rounded-lg border px-3">{files.map((file, index) => { const result = completedByName.get(file.name); const active = index === currentIndex && !result; return <li key={`${file.name}-${index}`} className="flex min-w-0 items-center gap-3 py-2.5 text-sm"><span className={`flex size-5 shrink-0 items-center justify-center rounded-full text-xs ${result?.status === "ok" ? "bg-emerald-500/15 text-emerald-700" : result?.status === "error" ? "bg-destructive/10 text-destructive" : active ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"}`}>{result?.status === "ok" ? <Check className="size-3.5" /> : result?.status === "error" ? <CircleAlert className="size-3.5" /> : index + 1}</span><span className="min-w-0 flex-1 truncate">{file.name}</span><span className="shrink-0 text-xs text-muted-foreground">{result ? (result.status === "ok" ? "Completed" : "Failed") : active ? "Analyzing" : "Waiting"}</span></li>; })}</ol>
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

  useEffect(() => { if (!loading) return; const startedAt = Date.now(); const timer = window.setInterval(() => setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000)), 1000); return () => window.clearInterval(timer); }, [loading]);
  const acceptedFiles = useMemo(() => files.filter((file) => /\.(pdf|docx)$/i.test(file.name)), [files]);
  const researchKinds = effectiveAutoResearchKinds(settings);
  function onFilesSelected(list: FileList | null) { if (list) setFiles((previous) => [...previous, ...Array.from(list)]); }

  async function analyzeFile(file: File): Promise<AnalyzeItemResult> {
    const form = new FormData(); form.append("files", file, file.name);
    const response = await fetch("/api/analyze", { method: "POST", body: form, headers: { "X-Report-Language": settings.reportLanguage } });
    const payload = await response.json().catch(() => ({})) as AnalyzeBatchResponse & { error?: string };
    if (!response.ok) throw new Error(payload.error ?? `Analysis failed (${response.status})`);
    return payload.results?.[0] ?? { filename: file.name, status: "error", error: "No result was returned" };
  }

  async function enrichWithAi(
    result: Extract<AnalyzeItemResult, { status: "ok" }>,
  ): Promise<Extract<AnalyzeItemResult, { status: "ok" }>> {
    if (result.report.ai_analysis.status !== "pending") return result;
    const response = await fetch(
      `/api/analyses/${encodeURIComponent(result.report.analysis_id)}/ai/retry`,
      { method: "POST" },
    );
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.error ?? payload.detail ?? "AI analysis failed");
    }
    return { ...result, report: payload };
  }

  async function submit() {
    setError(null); if (!acceptedFiles.length) { setError("Add at least one PDF or DOCX file."); return; }
    setLoading(true); setEntries([]); setCurrentIndex(0); setElapsedSeconds(0);
    for (let index = 0; index < acceptedFiles.length; index += 1) {
      const file = acceptedFiles[index]; setCurrentIndex(index); let result: AnalyzeItemResult;
      try { result = await analyzeFile(file); } catch (cause) { result = { filename: file.name, status: "error", error: cause instanceof Error ? cause.message : "Unexpected analysis error" }; }
      setEntries((previous) => [...previous, { file, result }]);
      if (result.status === "ok") {
        try {
          const enriched = await enrichWithAi(result);
          result = enriched;
          setEntries((previous) => previous.map((entry) =>
            entry.result.status === "ok"
              && entry.result.report.analysis_id === enriched.report.analysis_id
              ? { ...entry, result: enriched }
              : entry,
          ));
          if (enriched.report.ai_analysis.status === "succeeded") {
            void getAutoResearchOrchestrator()?.schedule(enriched.report, settings);
          }
        } catch (cause) {
          const message = cause instanceof Error ? cause.message : "AI analysis failed";
          const failed: typeof result = {
            ...result,
            report: {
              ...result.report,
              ai_analysis: {
                ...result.report.ai_analysis,
                status: "failed",
                failure_reason: "client_error",
                manual_retry_available: true,
              },
            },
          };
          result = failed;
          setEntries((previous) => previous.map((entry) =>
            entry.result.status === "ok"
              && entry.result.report.analysis_id === failed.report.analysis_id
              ? { ...entry, result: failed }
              : entry,
          ));
          setError(message);
        }
      }
    }
    setLoading(false);
  }

  function reset() { setFiles([]); setEntries([]); setError(null); setElapsedSeconds(0); setCurrentIndex(0); }
  function openHistorical(filename: string, report: Extract<AnalyzeItemResult, { status: "ok" }>["report"]) {
    setEntries([{ file: null, result: { filename, status: "ok", report } }]);
  }
  if (loading) return <div className="space-y-6"><AnalysisProgress files={acceptedFiles} completed={entries} currentIndex={currentIndex} elapsedSeconds={elapsedSeconds} researchKinds={researchKinds} />{entries.length ? <AnalysisWorkspace entries={entries} compact /> : null}</div>;
  if (entries.length) return <div className="space-y-4"><div className="mx-auto flex max-w-7xl items-center gap-4"><Button variant="outline" onClick={reset}><ArrowLeft data-icon="inline-start" />{t("back")}</Button>{entries.length > 1 ? <p className="ml-auto text-sm text-muted-foreground">{entries.filter(({ result }) => result.status === "ok").length} of {entries.length} analyzed</p> : null}</div><AnalysisWorkspace entries={entries} /></div>;

  return <div className="mx-auto max-w-5xl space-y-6">
    <Card>
      <CardHeader><CardTitle>{t("uploadTitle")}</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <ResearchNotice kinds={researchKinds} />
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
