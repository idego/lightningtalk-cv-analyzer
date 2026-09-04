"use client";

import { useCallback, useEffect, useState } from "react";
import { Collapsible } from "@base-ui/react/collapsible";
import { ChevronDown, ChevronUp, History, LoaderCircle, Trash2 } from "lucide-react";
import type { AnalysisHistoryItem, AnalysisReport } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

type Props = {
  onOpen: (item: AnalysisHistoryItem, report: AnalysisReport) => void;
  /** Change this value to reload the list, e.g. after a batch file finishes. */
  refreshKey?: number;
  /** Analysis ids finished in this session, marked as new in the list. */
  highlightIds?: ReadonlySet<string>;
};

export function RecentAnalyses({ onOpen, refreshKey = 0, highlightIds }: Props) {
  const { settings, t } = useCopy();
  const [items, setItems] = useState<AnalysisHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const primaryItems = items.slice(0, 5);
  const additionalItems = items.slice(5, 15);
  const canExpand = items.length > 5;

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
    setOpeningId(item.analysis_id);
    setError(null);
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("analysis_unavailable");
      onOpen(item, await response.json() as AnalysisReport);
    } catch {
      setError(t("analysisUnavailable"));
      void refresh();
    } finally {
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

  return <section className="rounded-xl border bg-card">
    <div className="flex items-center gap-2 border-b px-5 py-4"><History className="size-4" /><h2 className="font-medium">{t("recentAnalyses")}</h2></div>
    {loading && !items.length ? <div className="flex items-center justify-center py-8"><LoaderCircle className="size-5 animate-spin text-muted-foreground" /></div> : null}
    {!loading && !items.length ? <p className="px-5 py-6 text-sm text-muted-foreground">{t("noHistory")}</p> : null}
    {items.length ? <div className={expanded ? "max-h-[32rem] overflow-y-auto" : undefined}><ul className="divide-y">{primaryItems.map((item) => {
      return <AnalysisHistoryRow key={item.analysis_id} item={item} isNew={highlightIds?.has(item.analysis_id) ?? false} openingId={openingId} onOpen={open} onRemove={remove} />;
    })}</ul>
    <Collapsible.Root open={expanded}>
      <Collapsible.Panel className="h-[var(--collapsible-panel-height)] overflow-hidden opacity-100 transition-[height,opacity] duration-[180ms] ease-[var(--motion-ease-out)] data-ending-style:h-0 data-ending-style:opacity-0 data-starting-style:h-0 data-starting-style:opacity-0 motion-reduce:transition-none">
        <ul className="divide-y border-t">{additionalItems.map((item) => (
          <AnalysisHistoryRow key={item.analysis_id} item={item} isNew={highlightIds?.has(item.analysis_id) ?? false} openingId={openingId} onOpen={open} onRemove={remove} />
        ))}</ul>
      </Collapsible.Panel>
    </Collapsible.Root></div> : null}
    {canExpand ? <div className="flex justify-center border-t px-5 py-3">
      <Button
        variant="ghost"
        size="sm"
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        {expanded ? t("showFewerAnalyses") : t("showMoreAnalyses", { count: Math.min(items.length, 15) - 5 })}
        {expanded ? <ChevronUp data-icon="inline-end" /> : <ChevronDown data-icon="inline-end" />}
      </Button>
    </div> : null}
    {error ? <p className="border-t px-5 py-3 text-sm text-destructive">{error}</p> : null}
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
    <button type="button" onClick={() => void onOpen(item)} className="min-w-0 flex-1 rounded-md px-2 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">
      <span className="flex items-baseline justify-between gap-3"><span className="flex min-w-0 items-center gap-2"><span className="truncate text-sm font-medium">{item.candidate_name ?? item.filename}</span>{isNew ? <span className="shrink-0 rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium uppercase text-primary">{t("newAnalysis")}</span> : null}</span><time className="shrink-0 text-xs text-muted-foreground">{new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.created_at))}</time></span>
      {item.candidate_name ? <span className="mt-0.5 block truncate text-xs text-muted-foreground">{item.filename}</span> : null}
    </button>
    <div className="relative">
      <Button
        variant={confirmRemove ? "destructive" : "ghost"}
        size="icon"
        className={`size-8 shrink-0 ${confirmRemove ? "" : "text-destructive hover:bg-destructive/10 hover:text-destructive"}`}
        disabled={openingId === item.analysis_id || removing}
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
