"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronDown, ChevronRight, FolderInput, FolderKanban, FolderPlus, LoaderCircle, Search, Trash2, X } from "lucide-react";
import type { AnalysisGroup, AnalysisHistoryItem } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { useConfirmation } from "@/components/ui/use-confirmation";
import { AnalysisHistoryRow } from "@/components/analyze/recent-analyses";
import { countAnalyses, searchAnalysisGroups, withMovedAnalysis, withoutAnalysis, withoutGroup } from "@/lib/analysis-history-search";
import { useCopy } from "@/lib/app-settings";

/** Analyses page: every saved analysis grouped by job offer, with search and per-row / per-group deletion. */
export function AnalysisGroupsPanel() {
  const { t } = useCopy();
  const router = useRouter();
  const { confirm, confirmationDialog } = useConfirmation();
  const [groups, setGroups] = useState<AnalysisGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [newGroupName, setNewGroupName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const searching = Boolean(query.trim());
  const visibleGroups = searchAnalysisGroups(groups, query);
  const total = countAnalyses(groups);
  const matchCount = countAnalyses(visibleGroups);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/analysis-groups", { cache: "no-store" });
      if (!response.ok) throw new Error("groups_unavailable");
      const body = await response.json() as { groups?: AnalysisGroup[] };
      setGroups(body.groups ?? []);
    } catch {
      setError(t("groupsUnavailable"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  function toggle(groupId: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(groupId)) next.delete(groupId); else next.add(groupId);
      return next;
    });
  }

  function clearSearch() { setQuery(""); searchRef.current?.focus(); }

  function open(item: AnalysisHistoryItem) {
    setOpeningId(item.analysis_id);
    router.push(`/analyze?analysis=${encodeURIComponent(item.analysis_id)}`);
  }

  function openCreate() { setCreateError(null); setNewGroupName(""); setCreateOpen(true); }

  async function createGroup() {
    const name = newGroupName.trim();
    if (!name || creating) return;
    setCreating(true);
    setCreateError(null);
    try {
      const response = await fetch("/api/analysis-groups", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) });
      if (!response.ok) throw new Error("group_create_failed");
      const created = await response.json() as { group_id: string; name: string; created_at: string };
      setGroups((current) => {
        const rest = current.filter((group) => group.is_unassigned);
        const named = current.filter((group) => !group.is_unassigned);
        return [...named, { ...created, is_unassigned: false, analyses: [] }, ...rest];
      });
      setNewGroupName("");
      setCreateOpen(false);
    } catch {
      setCreateError(t("groupCouldNotCreate"));
    } finally {
      setCreating(false);
    }
  }

  async function removeAnalysis(item: AnalysisHistoryItem) {
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}`, { method: "DELETE" });
      if (response.ok) setGroups((current) => withoutAnalysis(current, item.analysis_id));
      else setError(t("analysisCouldNotDelete"));
    } catch {
      setError(t("analysisCouldNotDelete"));
    }
  }

  async function moveAnalysis(item: AnalysisHistoryItem, target: AnalysisGroup) {
    const groupId = target.is_unassigned ? null : target.group_id;
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(item.analysis_id)}/group`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ group_id: groupId }) });
      if (response.ok) setGroups((current) => withMovedAnalysis(current, item.analysis_id, target.group_id));
      else setError(t("analysisCouldNotMove"));
    } catch {
      setError(t("analysisCouldNotMove"));
    }
  }

  async function removeGroup(group: AnalysisGroup) {
    const count = group.analyses.length;
    const description = group.is_unassigned
      ? t("clearUnassignedGroupDescription", { count })
      : t("deleteGroupDescription", { name: group.name, count });
    if (!(await confirm(description, { title: t("deleteGroupTitle"), action: t("deleteGroup") }))) return;
    try {
      const response = await fetch(`/api/analysis-groups/${encodeURIComponent(group.group_id)}`, { method: "DELETE" });
      if (response.ok) setGroups((current) => withoutGroup(current, group.group_id));
      else setError(t("groupCouldNotDelete"));
    } catch {
      setError(t("groupCouldNotDelete"));
    }
  }

  return <div className="mx-auto max-w-5xl space-y-6">
    {confirmationDialog}
    <Dialog open={createOpen} onOpenChange={(open) => { if (!creating) setCreateOpen(open); }}>
      <DialogContent className="sm:max-w-md">
        <form className="contents" onSubmit={(event) => { event.preventDefault(); void createGroup(); }}>
          <DialogHeader>
            <DialogTitle>{t("createGroup")}</DialogTitle>
            <DialogDescription>{t("createGroupDescription")}</DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="new-group-name">{t("groupName")}</Label>
            <Input id="new-group-name" autoFocus value={newGroupName} maxLength={120} placeholder={t("newGroupName")} onChange={(event) => setNewGroupName(event.target.value)} disabled={creating} />
            {createError ? <p role="alert" className="text-sm text-destructive">{createError}</p> : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCreateOpen(false)} disabled={creating}>{t("cancel")}</Button>
            <Button type="submit" disabled={creating || !newGroupName.trim()}>
              {creating ? <LoaderCircle className="size-4 animate-spin" data-icon="inline-start" /> : null}
              {creating ? t("creatingGroup") : t("createGroup")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2"><FolderKanban className="size-5" aria-hidden />{t("analysesTitle")}</CardTitle>
        <CardDescription>{t("analysesDescription")}</CardDescription>
        <CardAction><Button onClick={openCreate}><FolderPlus className="size-4" data-icon="inline-start" />{t("createGroup")}</Button></CardAction>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground" aria-hidden />
          <input ref={searchRef} type="search" value={query} aria-label={t("searchAnalyses")} placeholder={t("searchAnalyses")} autoComplete="off" maxLength={200} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") { event.preventDefault(); clearSearch(); } }} className="h-9 w-full rounded-md border bg-background pl-9 pr-9 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-search-cancel-button]:appearance-none" />
          {query ? <button type="button" aria-label={t("clearSearch")} className="absolute right-0 top-0 flex size-9 items-center justify-center rounded-md text-muted-foreground outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring" onClick={clearSearch}><X className="size-4" aria-hidden /></button> : null}
        </div>
        {searching && !loading && !error ? <p role="status" className="text-xs text-muted-foreground">{t("analysisMatchCount", { count: matchCount, total })}</p> : null}
        {error ? <div role="alert" className="flex items-center justify-between gap-3 rounded-md border border-destructive/40 px-3 py-2 text-sm text-destructive"><span>{error}</span><Button variant="outline" size="sm" disabled={loading} onClick={() => void refresh()}>{t("retry")}</Button></div> : null}
      </CardContent>
    </Card>

    {loading && !groups.length ? <div role="status" className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />{t("loadingGroups")}</div> : null}
    {searching && !matchCount && !loading && !error ? <p className="py-6 text-center text-sm text-muted-foreground">{t("noAnalysisMatches")}</p> : null}
    {visibleGroups.map((group) => (
      <GroupSection key={group.group_id} group={group} allGroups={groups} expanded={!collapsed.has(group.group_id) || searching} openingId={openingId} onToggle={() => toggle(group.group_id)} onOpen={open} onRemoveAnalysis={removeAnalysis} onRemoveGroup={removeGroup} onMoveAnalysis={moveAnalysis} />
    ))}
  </div>;
}

function GroupSection({ group, allGroups, expanded, openingId, onToggle, onOpen, onRemoveAnalysis, onRemoveGroup, onMoveAnalysis }: {
  group: AnalysisGroup;
  allGroups: AnalysisGroup[];
  expanded: boolean;
  openingId: string | null;
  onToggle: () => void;
  onOpen: (item: AnalysisHistoryItem) => void;
  onRemoveAnalysis: (item: AnalysisHistoryItem) => Promise<void>;
  onRemoveGroup: (group: AnalysisGroup) => Promise<void>;
  onMoveAnalysis: (item: AnalysisHistoryItem, target: AnalysisGroup) => Promise<void>;
}) {
  const { t } = useCopy();
  const [removing, setRemoving] = useState(false);
  const name = group.is_unassigned ? t("unassignedGroup") : group.name;
  const headingId = `analysis-group-${group.group_id}`;
  const contentId = `analysis-group-${group.group_id}-content`;
  async function requestRemoveGroup() {
    setRemoving(true);
    try { await onRemoveGroup(group); } finally { setRemoving(false); }
  }
  return <section className="rounded-xl border bg-card" aria-labelledby={headingId}>
    <div className="flex items-center gap-2 border-b px-3 py-2">
      <button type="button" aria-expanded={expanded} aria-controls={contentId} aria-label={expanded ? t("collapseGroup", { name }) : t("expandGroup", { name })} onClick={onToggle} className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-1.5 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring">
        {expanded ? <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden /> : <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />}
        <h2 id={headingId} className="truncate font-medium">{name}</h2>
        <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">{t("analysesInGroup", { count: group.analyses.length })}</span>
        {group.is_unassigned ? <span className="hidden truncate text-xs text-muted-foreground sm:inline">{t("unassignedGroupDescription")}</span> : null}
      </button>
      <Button variant="ghost" size="sm" className="shrink-0 text-foreground hover:bg-destructive/10 hover:text-destructive" disabled={removing || (group.is_unassigned && !group.analyses.length)} aria-label={t("deleteGroup")} onClick={() => void requestRemoveGroup()}>
        {removing ? <LoaderCircle className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
        <span className="hidden sm:inline">{t("deleteGroup")}</span>
      </Button>
    </div>
    {expanded ? <div id={contentId}>
      {group.analyses.length ? <ul className="divide-y">{group.analyses.map((item) => (
        <AnalysisHistoryRow key={item.analysis_id} item={item} openingId={openingId} onOpen={onOpen} onRemove={onRemoveAnalysis} actions={<MoveToGroupMenu item={item} current={group} groups={allGroups} disabled={openingId !== null} onMove={onMoveAnalysis} />} />
      ))}</ul> : <p className="px-5 py-4 text-sm text-muted-foreground">{t("noAnalysesInGroup")}</p>}
    </div> : null}
  </section>;
}

/** Per-row "Move to group" menu listing every group, with the current one checked and disabled. */
function MoveToGroupMenu({ item, current, groups, disabled, onMove }: {
  item: AnalysisHistoryItem;
  current: AnalysisGroup;
  groups: AnalysisGroup[];
  disabled: boolean;
  onMove: (item: AnalysisHistoryItem, target: AnalysisGroup) => Promise<void>;
}) {
  const { t } = useCopy();
  const [moving, setMoving] = useState(false);
  async function move(target: AnalysisGroup) {
    if (target.group_id === current.group_id) return;
    setMoving(true);
    try { await onMove(item, target); } finally { setMoving(false); }
  }
  return <DropdownMenu>
    <DropdownMenuTrigger render={<Button variant="ghost" size="icon" className="size-8 shrink-0" disabled={disabled || moving} aria-label={moving ? t("movingToGroup") : t("moveToGroup")} />}>
      {moving ? <LoaderCircle className="size-4 animate-spin" /> : <FolderInput className="size-4" />}
    </DropdownMenuTrigger>
    <DropdownMenuContent align="end">
      {groups.map((group) => {
        const isCurrent = group.group_id === current.group_id;
        return <DropdownMenuItem key={group.group_id} disabled={isCurrent} onClick={() => void move(group)}>
          <span className="flex size-4 items-center justify-center">{isCurrent ? <Check className="size-4" aria-hidden /> : null}</span>
          <span className="truncate">{group.is_unassigned ? t("unassignedGroup") : group.name}</span>
        </DropdownMenuItem>;
      })}
    </DropdownMenuContent>
  </DropdownMenu>;
}
