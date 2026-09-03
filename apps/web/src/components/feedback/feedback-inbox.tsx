"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, FileText, LoaderCircle, MessageSquareText, SlidersHorizontal, ThumbsDown, ThumbsUp, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { feedbackContext } from "@/lib/feedback-context";
import { type CopyKey, useCopy } from "@/lib/app-settings";

type InboxItem = {
  target_id: string; actor_hash: string; triage_status: string;
  triage_note?: string | null; comment?: string | null; context_text?: string | null;
  context_label?: string | null; updated_at?: string | null; failure?: unknown;
  actor_email?: string | null; rating?: string | null; kind?: unknown; source_category?: unknown; source_key?: unknown;
};
type InboxData = { items: InboxItem[]; counts: Record<string, number> };
const statuses = ["new", "reviewing", "planned", "resolved", "wont_fix"] as const;
const statusLabelKeys: Record<string, CopyKey> = { new: "statusNew", reviewing: "statusReviewing", planned: "statusPlanned", resolved: "statusResolved", wont_fix: "statusWontFix" };

export function FeedbackInbox({ owner }: { owner: boolean }) {
  const { settings, t } = useCopy();
  const [data, setData] = useState<InboxData | null>(null);
  const [status, setStatus] = useState("");
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const hasUnsavedNotes = Boolean(data?.items.some((item) => (notes[itemKey(item)] ?? "").trim() !== (item.triage_note ?? "")));

  function acceptData(next: InboxData) {
    setData(next);
    setNotes((current) => {
      const merged = { ...current };
      for (const item of next.items) if (!(itemKey(item) in merged)) merged[itemKey(item)] = item.triage_note ?? "";
      return merged;
    });
  }

  async function load() {
    const response = await fetch(`/api/feedback/inbox${status ? `?status=${status}` : ""}`, { cache: "no-store" });
    acceptData(response.ok ? await response.json() : { items: [], counts: {} });
  }

  useEffect(() => {
    let active = true;
    fetch(`/api/feedback/inbox${status ? `?status=${status}` : ""}`, { cache: "no-store" })
      .then(async (response) => response.ok ? response.json() : { items: [], counts: {} })
      .then((value: InboxData) => { if (active) acceptData(value); });
    return () => { active = false; };
  }, [status]);

  useEffect(() => {
    if (!hasUnsavedNotes) return;
    const message = t("unsavedFeedbackNote");
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = true;
    };
    const linkClick = (event: MouseEvent) => {
      const link = (event.target as HTMLElement).closest("a[href]");
      if (!link || link.getAttribute("target") === "_blank") return;
      if (!window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", linkClick, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", linkClick, true);
    };
  }, [hasUnsavedNotes, t]);

  async function updateTriage(item: InboxItem, nextStatus: string, note: string) {
    const key = itemKey(item);
    setBusy(key);
    setErrors((current) => ({ ...current, [key]: "" }));
    const response = await fetch(`/api/feedback/inbox/${encodeURIComponent(item.target_id)}/${encodeURIComponent(item.actor_hash)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus, note: note.trim() || null }),
    });
    if (response.ok) await load();
    else setErrors((current) => ({ ...current, [key]: t("feedbackUpdateFailed") }));
    setBusy(null);
  }

  async function remove(item: InboxItem) {
    const key = itemKey(item);
    if (confirmDelete !== key) { setConfirmDelete(key); return; }
    setBusy(key);
    const response = await fetch(`/api/feedback/inbox/${encodeURIComponent(item.target_id)}/${encodeURIComponent(item.actor_hash)}`, { method: "DELETE" });
    if (response.ok) { setConfirmDelete(null); await load(); }
    else setErrors((current) => ({ ...current, [key]: t("feedbackDeleteFailed") }));
    setBusy(null);
  }

  return (
    <section className="mx-auto max-w-6xl space-y-5">
      <div className="flex items-start justify-between gap-4">
        <details className="group relative w-fit rounded-lg border bg-card">
          <summary className="flex min-w-40 cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm font-medium transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset">
            <span className="flex min-w-0 items-center gap-2"><SlidersHorizontal className="size-4 text-muted-foreground" /><span>{t("feedbackFilters")}</span>{status ? <span className="truncate text-xs font-normal text-muted-foreground">· {t(statusLabelKeys[status])}</span> : null}</span>
            <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
          </summary>
          <div className="absolute left-0 top-full z-30 mt-2 flex w-[min(32rem,calc(100vw-2rem))] flex-wrap gap-2 rounded-xl border bg-popover p-3 text-popover-foreground shadow-md" aria-label={t("feedbackStatusFilters")}>
            {["", ...statuses].map((value) => (
              <Button key={value} variant={status === value ? "secondary" : "outline"} size="sm" className="rounded-full" onClick={() => setStatus(value)} aria-pressed={status === value}>
                {value ? t(statusLabelKeys[value]) : t("all")}<span className="tabular-nums text-muted-foreground">{value ? data?.counts[value] ?? 0 : Object.values(data?.counts ?? {}).reduce((sum, count) => sum + count, 0)}</span>
              </Button>
            ))}
          </div>
        </details>
        {owner ? <Button variant="outline" nativeButton={false} render={<Link href="/feedback/access">{t("manageAccess")}</Link>} /> : null}
      </div>

      <div className="space-y-3">
        {!data ? <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />{t("loadingFeedback")}</div> : null}
        {data?.items.map((item) => {
          const context = feedbackContext(item);
          const key = itemKey(item);
          const awaitingConfirmation = confirmDelete === key;
          const isBusy = busy === key;
          const date = item.updated_at ? new Date(item.updated_at).toLocaleString(settings.uiLanguage === "pl" ? "pl-PL" : "en-GB", { dateStyle: "medium", timeStyle: "short" }) : null;
          return (
            <article key={key} className="rounded-xl border bg-card transition-[border-color,box-shadow] duration-150 hover:border-foreground/20 hover:shadow-sm">
              <header className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-5">
                <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
                  <h2 className="text-sm font-semibold">{context.section}</h2>
                  {item.rating ? <span className="inline-flex items-center gap-1 rounded-md bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{item.rating === "helpful" ? <ThumbsUp className="size-3" /> : <ThumbsDown className="size-3" />}{t(item.rating === "helpful" ? "helpful" : "needsImprovement")}</span> : null}
                  {date ? <span className="text-xs text-muted-foreground">{date}</span> : null}
                </div>
                <div className="flex items-center gap-1.5">
                  <DropdownMenu>
                    <DropdownMenuTrigger disabled={isBusy} render={<Button variant="outline" className="min-w-32 justify-between" />}>
                      <span className="flex items-center gap-2"><span className={`size-2 rounded-full ${statusDot(item.triage_status)}`} aria-hidden="true" />{t(statusLabelKeys[item.triage_status])}</span><ChevronDown className="size-4 text-muted-foreground" />
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" side="bottom" sideOffset={6} className="min-w-40">
                      {statuses.map((value) => (
                        <DropdownMenuItem key={value} className="py-2" onClick={() => void updateTriage(item, value, notes[key] ?? "")}>
                          <span className={`size-2 rounded-full ${statusDot(value)}`} aria-hidden="true" /><span className="flex-1">{t(statusLabelKeys[value])}</span>{item.triage_status === value ? <span className="text-xs text-muted-foreground">{t("current")}</span> : null}
                        </DropdownMenuItem>
                      ))}
                    </DropdownMenuContent>
                  </DropdownMenu>
                  <div className="relative">
                    <Button
                      variant={awaitingConfirmation ? "destructive" : "outline"}
                      size="icon-sm"
                      className={awaitingConfirmation ? "" : "text-destructive hover:bg-destructive/10 hover:text-destructive"}
                      disabled={isBusy}
                      aria-label={t(awaitingConfirmation ? "confirmDeleteFeedback" : "deleteFeedback")}
                      onBlur={() => { if (!isBusy) setConfirmDelete(null); }}
                      onKeyDown={(event) => { if (event.key === "Escape") setConfirmDelete(null); }}
                      onClick={() => void remove(item)}
                    >
                      {isBusy ? <LoaderCircle className="animate-spin" /> : <Trash2 />}
                    </Button>
                    {awaitingConfirmation ? <span role="status" className="absolute right-0 top-full z-20 mt-2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-xs text-background shadow-md">{t("clickAgainToConfirm")}</span> : null}
                  </div>
                </div>
              </header>

              <div className="border-t px-4 py-4 sm:px-5">
                <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,0.7fr)]">
                  <div className="min-w-0 space-y-3">
                    {item.comment ? <div><p className="text-xs font-medium text-muted-foreground">{t("commentFrom", { author: item.actor_email || t("unknownAuthor") })}</p><p className="mt-1.5 text-sm leading-relaxed">{item.comment}</p></div> : null}
                    {item.context_text ? (
                      <details className="group border-t pt-3">
                        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-lg py-1 text-sm font-medium outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring">
                          <span className="flex items-center gap-2"><FileText className="size-4 text-muted-foreground" />{t("showCvExcerpt")}</span><ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
                        </summary>
                        <div className="mt-3 max-h-80 overflow-auto rounded-lg bg-muted/45 p-3">
                          {!sameLabel(item.context_label, context.section) && !sameLabel(item.context_label, context.subject) ? <p className="mb-2 text-xs font-semibold text-muted-foreground">{item.context_label}</p> : null}
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">{item.context_text}</p>
                        </div>
                      </details>
                    ) : null}
                    {item.failure ? <details className="border-t pt-3"><summary className="cursor-pointer text-sm font-medium">{t("errorDetails")}</summary><pre className="mt-3 max-h-64 overflow-auto rounded-lg bg-muted p-3 text-xs">{JSON.stringify(item.failure, null, 2)}</pre></details> : null}
                  </div>

                  <div className="border-t pt-4 lg:border-l lg:border-t-0 lg:pl-4 lg:pt-0">
                    <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground" htmlFor={`note-${key}`}><MessageSquareText className="size-4" />{t("teamNote")}</label>
                    <textarea id={`note-${key}`} className={`mt-2 w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm leading-relaxed outline-none transition-colors placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 ${item.comment || item.context_text || item.failure ? "min-h-24" : "min-h-16"}`} maxLength={500} placeholder={t("teamNotePlaceholder")} value={notes[key] ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [key]: event.target.value }))} />
                    <div className="mt-2 flex min-h-8 flex-wrap items-center justify-between gap-2"><span className="text-xs text-destructive" role="alert">{errors[key]}</span><Button size="sm" disabled={isBusy || (notes[key] ?? "").trim() === (item.triage_note ?? "")} onClick={() => void updateTriage(item, item.triage_status, notes[key] ?? "")}>{isBusy ? <LoaderCircle className="animate-spin" /> : null}{t("saveNote")}</Button></div>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
        {data && !data.items.length ? <p className="py-16 text-center text-sm text-muted-foreground">{t("noFeedbackForFilter")}</p> : null}
      </div>
    </section>
  );
}

function itemKey(item: InboxItem) { return `${item.target_id}:${item.actor_hash}`; }
function sameLabel(left: unknown, right: unknown) { return Boolean(left && right && String(left).trim().toLocaleLowerCase() === String(right).trim().toLocaleLowerCase()); }
function statusDot(status: string) { return { new: "bg-sky-500", reviewing: "bg-amber-500", planned: "bg-violet-500", resolved: "bg-emerald-500", wont_fix: "bg-zinc-400" }[status] ?? "bg-zinc-400"; }
