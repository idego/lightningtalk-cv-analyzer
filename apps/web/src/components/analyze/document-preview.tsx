"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, LoaderCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

export function DocumentPreview({ file, onHide }: { file: File; onHide: () => void }) {
  return <DocumentPreviewContent key={`${file.name}:${file.size}:${file.lastModified}`} file={file} onHide={onHide} />;
}

function DocumentPreviewContent({ file, onHide }: { file: File; onHide: () => void }) {
  const { t } = useCopy();
  const containerRef = useRef<HTMLDivElement>(null);
  const [url] = useState(() => URL.createObjectURL(file));
  const isPdf = file.name.toLowerCase().endsWith(".pdf");
  const [loading, setLoading] = useState(!isPdf);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isPdf && containerRef.current) {
      containerRef.current.replaceChildren();
      void import("docx-preview")
        .then(({ renderAsync }) => renderAsync(file, containerRef.current!, undefined, {
          breakPages: true,
          ignoreWidth: false,
          // Keep the in-app preview continuous. docx-preview otherwise turns
          // continuous Word sections into separate, mostly empty pages.
          ignoreHeight: true,
          renderHeaders: true,
          renderFooters: true,
          ignoreLastRenderedPageBreak: false,
        }))
        .then(() => setLoading(false))
        .catch(() => {
          setLoading(false);
          setError(t("docxPreviewFailed"));
        });
    }
    return () => URL.revokeObjectURL(url);
  }, [file, isPdf, t, url]);

  return <aside className="sticky top-20 flex h-[calc(100svh-6.5rem)] min-w-0 flex-col overflow-hidden rounded-xl border bg-muted/35"><div className="flex min-w-0 items-center gap-2 border-b bg-background px-3 py-2"><FileText className="size-4 shrink-0" /><span className="min-w-0 flex-1 truncate text-sm font-medium">{file.name}</span><Button variant="ghost" size="icon" className="size-8" render={<a href={url} target="_blank" rel="noreferrer" aria-label={t("openOriginalFile")}><ExternalLink className="size-4" /></a>} /><Button variant="ghost" size="icon" className="size-8" onClick={onHide} aria-label={t("hideCvPreview")}><X className="size-4" /></Button></div><div className="relative min-h-0 flex-1 overflow-auto">{loading ? <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80"><LoaderCircle className="size-6 animate-spin" /></div> : null}{error ? <div className="m-4 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm">{error}</div> : null}{isPdf && url ? <iframe title={`${t("fileDetails")}: ${file.name}`} src={url} className="h-full min-h-[720px] w-full border-0 bg-white" /> : <div ref={containerRef} className="docx-preview-host min-h-full overflow-auto p-4" />}</div></aside>;
}
