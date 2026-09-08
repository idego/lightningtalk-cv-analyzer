"use client";

import { useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, ChevronUp, History, LoaderCircle, Search, X } from "lucide-react";
import type { RecentProfileItem } from "@/components/profile-builder/profile-builder-model";
import { DeleteButton } from "@/components/ui/delete-button";
import { Button } from "@/components/ui/button";
import { useAppSettings } from "@/lib/app-settings";

const COLLAPSED_COUNT = 5;

type Props = {
  items: RecentProfileItem[];
  loading: boolean;
  error: string | null;
  openingId: string | null;
  highlightIds?: ReadonlySet<string>;
  onOpen: (item: RecentProfileItem) => Promise<void>;
  onRemove: (item: RecentProfileItem) => Promise<void>;
  onRetry: () => void;
};

function normalize(value: string): string {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").replace(/[łŁ]/g, "l").toLowerCase();
}

/** Match every word across candidate name, filename, and template, keeping list order. */
export function searchRecentProfiles(items: readonly RecentProfileItem[], query: string): RecentProfileItem[] {
  const words = normalize(query).trim().split(/\s+/).filter(Boolean);
  return items.filter((item) => {
    const text = normalize(`${item.candidate_name ?? ""} ${item.source_filename} ${item.template_name}`);
    return words.every((word) => text.includes(word));
  });
}

/** Same layout and behaviour as Recent analyses: search, five rows with "Show more", "New" badges, inline delete. */
export function RecentProfiles({ items, loading, error, openingId, highlightIds, onOpen, onRemove, onRetry }: Props) {
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);
  const matches = searchRecentProfiles(items, query);
  const searching = Boolean(query.trim());
  const visibleItems = searching || expanded ? matches : matches.slice(0, COLLAPSED_COUNT);
  function changeQuery(value: string) { setQuery(value); setExpanded(false); }
  function clearSearch() { changeQuery(""); searchRef.current?.focus(); }

  return <section className="rounded-xl border bg-card" aria-labelledby="recent-profiles-heading">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
      <h2 id="recent-profiles-heading" className="flex items-center gap-2 font-medium"><History className="size-4" aria-hidden />Recent profiles</h2>
      <div className="flex w-full items-center gap-2 sm:w-auto">
        <div className="relative min-w-0 flex-1 sm:w-64">
          <Search className="pointer-events-none absolute left-2.5 top-2 size-4 text-muted-foreground" aria-hidden />
          <input ref={searchRef} type="search" value={query} aria-label="Search profiles" placeholder="Search profiles" autoComplete="off" maxLength={200} onChange={(event) => changeQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); clearSearch(); } }} className="h-8 w-full rounded-md border bg-background pl-8 pr-8 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-search-cancel-button]:appearance-none" />
          {query ? <button type="button" aria-label="Clear search" className="absolute right-0 top-0 flex size-8 items-center justify-center rounded-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring" onClick={clearSearch}><X className="size-4" aria-hidden /></button> : null}
        </div>
        <Button variant="outline" className="shrink-0 border-foreground/25" size="sm" nativeButton={false} render={<Link href="/profiles" />}>View all</Button>
      </div>
    </div>
    {loading && !items.length ? <div role="status" className="flex items-center justify-center gap-2 px-5 py-6 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading recent profiles…</div> : null}
    {!loading && !error && !items.length && !searching ? <div className="px-5 py-6"><p className="text-sm font-medium">No profiles yet.</p><p className="mt-1 text-xs text-muted-foreground">Converted CVs will appear here.</p></div> : null}
    {searching && !loading && !error ? <p role="status" className="px-5 pt-3 text-xs text-muted-foreground">{matches.length} of {items.length} profiles match</p> : null}
    {searching && !matches.length && !loading && !error ? <p className="px-5 py-6 text-sm text-muted-foreground">No profiles match your search.</p> : null}
    {visibleItems.length ? <ul className={`divide-y ${expanded || searching ? "max-h-[32rem] overflow-y-auto" : ""}`}>{visibleItems.map((item) => (
      <RecentProfileRow key={item.profile_id} item={item} isNew={highlightIds?.has(item.profile_id) ?? false} openingId={openingId} onOpen={onOpen} onRemove={onRemove} />
    ))}</ul> : null}
    {!searching && items.length > COLLAPSED_COUNT ? <div className="flex justify-center border-t px-5 py-3"><Button variant="ghost" size="sm" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>
      {expanded ? "Show fewer" : `Show more (${items.length - COLLAPSED_COUNT})`}
      {expanded ? <ChevronUp data-icon="inline-end" /> : <ChevronDown data-icon="inline-end" />}
    </Button></div> : null}
    {error ? <div role="alert" className="flex items-center justify-between gap-3 border-t px-5 py-3 text-sm text-destructive"><span>{error}</span><Button variant="outline" size="sm" disabled={loading} onClick={onRetry}>Retry</Button></div> : null}
  </section>;
}

function RecentProfileRow({ item, isNew, openingId, onOpen, onRemove }: {
  item: RecentProfileItem;
  isNew: boolean;
  openingId: string | null;
  onOpen: (item: RecentProfileItem) => Promise<void>;
  onRemove: (item: RecentProfileItem) => Promise<void>;
}) {
  const settings = useAppSettings();
  const [removing, setRemoving] = useState(false);
  async function requestRemove() {
    setRemoving(true);
    try {
      await onRemove(item);
    } finally {
      setRemoving(false);
    }
  }
  return <li className="flex min-w-0 items-center gap-2 px-3 py-2">
    <button type="button" disabled={openingId !== null || removing} onClick={() => void onOpen(item)} className="min-w-0 flex-1 rounded-md px-2 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-wait disabled:opacity-70">
      <span className="flex flex-col gap-0.5 sm:flex-row sm:items-baseline sm:justify-between sm:gap-3"><span className="flex min-w-0 items-center gap-2"><span className="truncate text-sm font-medium">{item.candidate_name ?? item.source_filename}</span>{isNew ? <span className="shrink-0 rounded-full bg-primary/15 px-1.5 py-0.5 text-[10px] font-medium uppercase text-primary">New</span> : null}{openingId === item.profile_id ? <LoaderCircle className="size-3.5 shrink-0 animate-spin text-muted-foreground" aria-hidden /> : null}</span><time className="shrink-0 text-xs text-muted-foreground">{new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.updated_at))}</time></span>
      <span className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">{item.candidate_name ? <span className="truncate">{item.source_filename}</span> : null}<span className="shrink-0 rounded-full bg-muted px-1.5 py-0.5">{item.template_name}</span></span>
    </button>
    <DeleteButton label={`Delete ${item.candidate_name ?? item.source_filename}`} disabled={openingId !== null || removing} onDelete={requestRemove} />
  </li>;
}
