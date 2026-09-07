"use client";

import { useEffect, useRef, useState } from "react";
import { FileText, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { exportProfileSnapshot } from "./profile-builder-client";
import { ProfilePdfPage } from "./profile-pdf-page";
import { ProfileDocumentPreview } from "./profile-document-preview";
import { derivedPresentation, type ProfileSnapshotPayload } from "./profile-builder-model";

/** Uses the export renderer, so the preview cannot disagree about redaction or pagination. */
export function ProfileExportPreview({ snapshot, pdfAvailable }: { snapshot: ProfileSnapshotPayload; pdfAvailable: boolean }) {
  const hostRef = useRef<HTMLElement>(null);
  const urlRef = useRef<string | null>(null);
  const [visible, setVisible] = useState(false);
  const serialized = JSON.stringify(snapshot);
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${attempt}:${serialized}`;
  const [result, setResult] = useState<{ key: string; url?: string; failed?: boolean } | null>(null);
  const current = result?.key === requestKey ? result : null;

  useEffect(() => {
    const node = hostRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => setVisible(entry.contentRect.width > 0));
    observer.observe(node);
    return () => observer.disconnect();
  }, [pdfAvailable]);
  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current); }, []);

  useEffect(() => {
    if (!pdfAvailable || !visible || result?.key === requestKey) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      const { profile, anonymization, template } = JSON.parse(serialized) as ProfileSnapshotPayload;
      void exportProfileSnapshot("pdf", { profile, anonymization, template, template_id: template.id }, controller.signal)
        .then((blob) => {
          if (controller.signal.aborted) return;
          if (urlRef.current) URL.revokeObjectURL(urlRef.current);
          urlRef.current = URL.createObjectURL(blob);
          setResult({ key: requestKey, url: urlRef.current });
        })
        .catch(() => { if (!controller.signal.aborted) setResult({ key: requestKey, failed: true }); });
    }, 800);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [serialized, requestKey, pdfAvailable, visible, result]);

  if (!pdfAvailable) return <div className="h-full min-h-0 overflow-auto overscroll-contain"><ProfileDocumentPreview profile={derivedPresentation(snapshot.profile, snapshot.anonymization)} template={snapshot.template} label="Layout preview · PDF preview unavailable" /></div>;

  return <section ref={hostRef} className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border bg-card" aria-label="Document preview">
    {!current?.url ? <header className="flex min-h-11 shrink-0 items-center gap-2 border-b px-3 py-2">
      <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden />
      <h2 className="text-sm font-medium">Document preview</h2>
    </header> : null}
    <div className="relative min-h-0 flex-1 bg-muted/25">
      {current?.url ? <ProfilePdfPage key={current.url} url={current.url} /> : current?.failed ? <div role="alert" className="flex h-full flex-col items-center justify-center gap-3 px-5 text-center text-sm">
        <p>Preview could not be generated. Your edits are still here; retry or download DOCX.</p>
        <Button variant="outline" onClick={() => setAttempt((value) => value + 1)}>Retry preview</Button>
      </div> : <div role="status" className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" aria-hidden />Updating document preview…</div>}
    </div>
  </section>;
}
