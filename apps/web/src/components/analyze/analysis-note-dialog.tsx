"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, NotebookPen, StickyNote } from "lucide-react";
import type { AnalysisHistoryItem } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useCopy } from "@/lib/app-settings";

/** Fallback until the API reports its own limit. Mirrors ANALYSIS_NOTE_MAX_CHARS in the API. */
export const NOTE_MAX_CHARS = 2000;

type NotePayload = { note: { content: string; updated_at: string } | null; max_chars?: number };

/**
 * Per-analysis note: a row button that opens a modal editor. The button is filled when a note exists.
 * `onChange` reports the new has-note state so the parent list can update its indicator.
 */
export function AnalysisNoteButton({ item, disabled = false, onChange }: {
  item: AnalysisHistoryItem;
  disabled?: boolean;
  onChange?: (analysisId: string, hasNote: boolean) => void;
}) {
  const { t } = useCopy();
  const [open, setOpen] = useState(false);
  const hasNote = Boolean(item.has_note);
  const Icon = hasNote ? NotebookPen : StickyNote;
  return <>
    <Button variant="ghost" size="icon" className={`size-8 shrink-0 ${hasNote ? "text-primary" : ""}`} disabled={disabled} aria-label={hasNote ? t("editNote") : t("addNote")} title={hasNote ? t("editNote") : t("addNote")} onClick={() => setOpen(true)}>
      <Icon className="size-4" />
    </Button>
    {open ? <AnalysisNoteDialog item={item} onClose={() => setOpen(false)} onChange={onChange} /> : null}
  </>;
}

function AnalysisNoteDialog({ item, onClose, onChange }: {
  item: AnalysisHistoryItem;
  onClose: () => void;
  onChange?: (analysisId: string, hasNote: boolean) => void;
}) {
  const { settings, t } = useCopy();
  const [content, setContent] = useState("");
  const [saved, setSaved] = useState<{ content: string; updated_at: string } | null>(null);
  const [maxChars, setMaxChars] = useState(NOTE_MAX_CHARS);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const path = `/api/analyses/${encodeURIComponent(item.analysis_id)}/note`;
  const trimmed = content.trim();
  const dirty = trimmed !== (saved?.content ?? "");
  const tooLong = trimmed.length > maxChars;

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const response = await fetch(path, { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error("note_unavailable");
        const body = await response.json() as NotePayload;
        setSaved(body.note);
        setContent(body.note?.content ?? "");
        if (body.max_chars) setMaxChars(body.max_chars);
      } catch (cause) {
        if (cause instanceof DOMException && cause.name === "AbortError") return;
        setError(t("noteUnavailable"));
      } finally {
        setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [path, t]);

  async function save() {
    if (!trimmed || tooLong || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: trimmed }) });
      if (!response.ok) throw new Error("note_save_failed");
      const body = await response.json() as NotePayload;
      setSaved(body.note);
      onChange?.(item.analysis_id, true);
      onClose();
    } catch {
      setError(t("noteCouldNotSave"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(path, { method: "DELETE" });
      if (!response.ok) throw new Error("note_delete_failed");
      setSaved(null);
      setContent("");
      onChange?.(item.analysis_id, false);
      onClose();
    } catch {
      setError(t("noteCouldNotDelete"));
    } finally {
      setBusy(false);
    }
  }

  return <Dialog open onOpenChange={(next) => { if (!next && !busy) onClose(); }}>
    <DialogContent className="sm:max-w-lg">
      <form className="contents" onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <DialogHeader>
          <DialogTitle>{t("noteTitle", { name: item.candidate_name ?? item.filename })}</DialogTitle>
          <DialogDescription>{t("noteDescription")}</DialogDescription>
        </DialogHeader>
        {loading ? <div role="status" className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />{t("loadingNote")}</div> : <div className="grid gap-1.5">
          <textarea autoFocus value={content} rows={8} maxLength={maxChars + 200} placeholder={t("notePlaceholder")} aria-label={t("noteTitle", { name: item.candidate_name ?? item.filename })} disabled={busy} onChange={(event) => setContent(event.target.value)} className="min-h-40 w-full resize-y rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{saved ? t("noteUpdated", { time: new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(saved.updated_at)) }) : ""}</span>
            <span className={tooLong ? "text-destructive" : ""} aria-live="polite">{trimmed.length} / {maxChars}</span>
          </div>
          {tooLong ? <p role="alert" className="text-sm text-destructive">{t("noteTooLong", { max: maxChars })}</p> : null}
          {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
        </div>}
        <DialogFooter className="sm:justify-between">
          <div>{saved ? <Button type="button" variant="ghost" className="text-destructive hover:text-destructive" disabled={busy || loading} onClick={() => void remove()}>{t("deleteNote")}</Button> : null}</div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" disabled={busy} onClick={onClose}>{t("cancel")}</Button>
            <Button type="submit" disabled={busy || loading || !trimmed || !dirty || tooLong}>
              {busy ? <LoaderCircle className="size-4 animate-spin" data-icon="inline-start" /> : null}
              {t("saveNote")}
            </Button>
          </div>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>;
}
