"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, History, LoaderCircle, Search, Trash2, X } from "lucide-react";
import type { AnalysisHistoryItem, AnalysisReport } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { searchAnalysisHistory } from "@/lib/analysis-history-search";
import { useCopy } from "@/lib/app-settings";

type Props = {
  onOpen: (item: AnalysisHistoryItem, report: AnalysisReport) => void;
  query: string;
  onQueryChange: (query: string) => void;
  refreshKey?: number;
  highlightIds?: ReadonlySet<string>;
};

export function RecentAnalyses({ onOpen, query, onQueryChange, refreshKey = 0, highlightIds }: Props) {
  const { t } = useCopy();
  const [items, setItems] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const opening = useRef(false);
  const matches = searchAnalysisHistory(items, query);
  const searching = Boolean(query.trim());
  const visibleItems = searching || expanded ? matches : matches.slice(0, 5);
  function changeQuery(value: string) { onQueryChange(value); setExpanded(false); }
  function clearSearch() { changeQuery(""); searchRef.current?.focus(); }

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/analyses", { cache: "no-store" });
      if (!response.ok) throw new Error("history_unavailable");
      const body = await response.json() as { analyses?: AnalysisHistoryItem[] };
      setItems(body.analyses ?? []);
    } catch {
      setError(t("historyUnavailable"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh, refreshKey]);

  async function open(item: AnalysisHistoryItem) {
    if (opening.current) return;
    opening.current = true;
    setOpeningId(item.analysis_id);
    setError(null);
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("analysis_unavailable");
      onOpen(item, await response.json() as AnalysisReport);
    } catch {
      setError(t("analysisUnavailable"));
    } finally {
      opening.current = false;
      setOpeningId(null);
    }
  }

  async function remove(item: AnalysisHistoryItem) {
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}`, { method: "DELETE" });
      if (response.ok) setItems((current) => current.filter(({ analysis_id }) => analysis_id !== item.analysis_id));
      else setError(t("analysisCouldNotDelete"));
    } catch {
      setError(t("analysisCouldNotDelete"));
    }
  }

  return <section className="rounded-xl border bg-card" aria-labelledby="recent-analyses-heading">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
      <h2 id="recent-analyses-heading" className="flex items-center gap-2 font-medium"><History className="size-4" aria-hidden />{t("recentAnalyses")}</h2>
      <div className="relative w-full sm:w-72">
        <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden />
        <input ref={searchRef} type="search" value={query} aria-label={t("searchAnalyses")} placeholder={t("searchAnalyses")} autoComplete="off" maxLength={200} onChange={(event) => changeQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); clearSearch(); } }} className="h-8 w-full rounded-md border bg-background pl-8 pr-8 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-search-cancel-button]:appearance-none" />
        {query ? <button type="button" aria-label={t("clearSearch")} className="absolute right-0 top-0 flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring" onClick={clearSearch}><X className="size-4" aria-hidden /></button> : null}
      </div>
    </div>
    {loading && !items.length ? <div role="status" className="flex items-center justify-center gap-2 px-5 py-6 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />{t("loadingHistory")}</div> : null}
    {!loading && !error && !items.length && !searching ? <div className="px-5 py-6"><p className="text-sm font-medium">{t("noHistory")}</p><p className="mt-1 text-xs text-muted-foreground">{t("noHistoryDescription")}</p></div> : null}
    {searching && !loading && !error ? <p role="status" className="px-5 pt-3 text-xs text-muted-foreground">{t("analysisMatchCount", { count: matches.length, total: items.length })}</p> : null}
    {searching && !matches.length && !loading && !error ? <p className="px-5 py-6 text-sm text-muted-foreground">{t("noAnalysisMatches")}</p> : null}
    {visibleItems.length ? <ul className={`divide-y ${expanded || searching ? "max-h-[32rem] overflow-y-auto" : ""}`}>{visibleItems.map((item) => (
      <AnalysisHistoryRow key={item.analysis_id} item={item} isNew={highlightIds?.has(item.analysis_id) ?? false} openingId={openingId} onOpen={open} onRemove={remove} />
    ))}</ul> : null}
    {!searching && items.length > 5 ? <div className="flex justify-center border-t px-5 py-3"><Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>
      {expanded ? t("showFewerAnalyses") : t("showMoreAnalyses", { count: items.length - 5 })}
      {expanded ? <ChevronUp data-icon="inline-end" /> : <ChevronDown data-icon="inline-end" />}
    </Button></div> : null}
    {error ? <div role="alert" className="flex items-center justify-between gap-3 border-t px-5 py-3 text-sm text-destructive"><span>{error}</span><Button variant="outline" size="sm" disabled={loading} onClick={() => void refresh()}>{t("retry")}</Button></div> : null}
  </section>;
}

function AnalysisHistoryRow({
  item,
  isNew,
  openingId,
  onOpen,
  onRemove,
}: {
  item: AnalysisHistoryItem;
  isNew: boolean;
  openingId: string | null;
  onOpen: (item: AnalysisHistoryItem) => Promise<void>;
  onRemove: (item: AnalysisHistoryItem) => Promise<void>;
}) {
  const { settings, t } = useCopy();
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing, setRemoving] = useState(false);
  async function requestRemove() {
    if (!confirmRemove) {
      setConfirmRemove(true);
      return;
    }
    setConfirmRemove(false);
    setRemoving(true);
    try {
      await onRemove(item);
    } finally {
      setRemoving(false);
    }
  }
  return <li className="flex min-w-0 items-center gap-2 px-3 py-2">
    <button type="button" disabled={openingId !== null || removing} onClick={() => void onOpen(item)} className="min-w-0 flex-1 rounded-md px-2 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-wait disabled:opacity-70">
      <span className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3"><span className="flex min-w-0 items-center gap-2"><span className="truncate text-sm font-medium">{item.candidate_name ?? item.filename}</span>{isNew ? <span className="shrink-0 rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium uppercase text-primary">{t("newAnalysis")}</span> : null}{openingId === item.analysis_id ? <LoaderCircle className="size-3.5 shrink-0 animate-spin text-muted-foreground" aria-hidden /> : null}</span><time className="shrink-0 text-xs text-muted-foreground">{new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</time></span>
      <span className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">{item.candidate_name ? <span className="truncate">{item.filename}</span> : null}{item.status === "partial" ? <span className="shrink-0 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-amber-800 dark:text-amber-200">{t("partialAnalysis")}</span> : null}</span>
    </button>
    <div className="relative">
      <Button
        variant={confirmRemove ? "destructive" : "ghost"}
        size="icon"
        className={`size-8 shrink-0 ${confirmRemove ? "" : "text-destructive hover:bg-destructive/10 hover:text-destructive"}`}
        disabled={openingId !== null || removing}
        onBlur={() => { if (!removing) setConfirmRemove(false); }}
        onKeyDown={(event) => { if (event.key === "Escape") setConfirmRemove(false); }}
        onClick={() => void requestRemove()}
        aria-label={t(confirmRemove ? "clickAgainToConfirm" : "deleteAnalysis")}
      >
        {removing ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
      </Button>
      {confirmRemove ? <span role="status" className="absolute right-0 top-full z-20 mt-2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md">{t("clickAgainToConfirm")}</span> : null}
    </div>
  </li>;
}
