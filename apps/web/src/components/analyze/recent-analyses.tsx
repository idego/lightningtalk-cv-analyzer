"use client";

import { useCallback, useEffect, useState } from "react";
import { History, LoaderCircle, Trash2 } from "lucide-react";
import type { AnalysisHistoryItem, AnalysisReport } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

type Props = {
  onOpen: (filename: string, report: AnalysisReport) => void;
};

export function RecentAnalyses({ onOpen }: Props) {
  const { settings, t } = useCopy();
  const [items, setItems] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/analyses", { cache: "no-store" });
      if (!response.ok) throw new Error("history_unavailable");
      const body = await response.json() as { analyses?: AnalysisHistoryItem[] };
      setItems(body.analyses ?? []);
    } catch {
      setError("Analysis history is unavailable.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function open(item: AnalysisHistoryItem) {
    setOpeningId(item.analysis_id);
    setError(null);
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("analysis_unavailable");
      onOpen(item.filename, await response.json() as AnalysisReport);
    } catch {
      setError("This analysis is no longer available.");
      void refresh();
    } finally {
      setOpeningId(null);
    }
  }

  async function remove(item: AnalysisHistoryItem) {
    if (!window.confirm(`Delete ${item.candidate_name ?? item.filename}?`)) return;
    const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}`, { method: "DELETE" });
    if (response.ok) setItems((current) => current.filter(({ analysis_id }) => analysis_id !== item.analysis_id));
    else setError("The analysis could not be deleted.");
  }

  return <section className="rounded-xl border bg-card">
    <div className="flex items-center gap-2 border-b px-5 py-4"><History className="size-4" /><h2 className="font-medium">{t("recentAnalyses")}</h2></div>
    {loading ? <div className="flex items-center justify-center py-8"><LoaderCircle className="size-5 animate-spin text-muted-foreground" /></div> : null}
    {!loading && !items.length ? <p className="px-5 py-6 text-sm text-muted-foreground">{t("noHistory")}</p> : null}
    {items.length ? <ul className="divide-y">{items.map((item) => {
      return <li key={item.analysis_id} className="flex min-w-0 items-center gap-2 px-3 py-2">
        <button type="button" onClick={() => void open(item)} className="min-w-0 flex-1 rounded-md px-2 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">
          <span className="flex items-baseline justify-between gap-3"><span className="truncate text-sm font-medium">{item.candidate_name ?? item.filename}</span><time className="shrink-0 text-xs text-muted-foreground">{new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</time></span>
          {item.candidate_name ? <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.filename}</span> : null}
        </button>
        <Button variant="ghost" size="icon" className="size-8 shrink-0" disabled={openingId === item.analysis_id} onClick={() => void remove(item)} aria-label={t("deleteAnalysis")}><Trash2 className="size-4" /></Button>
      </li>;
    })}</ul> : null}
    {error ? <p className="border-t px-5 py-3 text-sm text-destructive">{error}</p> : null}
  </section>;
}
