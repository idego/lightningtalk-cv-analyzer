"use client";

import { useRef, useState } from "react";
import { PanelRightOpen } from "lucide-react";
import type { AnalyzeItemResult } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { ResultsList } from "@/components/analyze/results-list";
import { DocumentPreview } from "@/components/analyze/document-preview";
import { useCopy } from "@/lib/app-settings";
import { useIsMobile } from "@/hooks/use-mobile";

export type AnalyzedFile = { file: File | null; result: AnalyzeItemResult };

export function AnalysisWorkspace({ entries, compact = false }: { entries: AnalyzedFile[]; compact?: boolean }) {
  const { t } = useCopy();
  const isMobile = useIsMobile();
  const hostRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [previewVisible, setPreviewVisible] = useState(!compact);
  const [previewShare, setPreviewShare] = useState(55);
  const active = entries[Math.min(activeIndex, entries.length - 1)];
  const hasOriginalFiles = entries.some(({ file }) => file !== null);
  function startResize(event: React.PointerEvent<HTMLDivElement>) { event.currentTarget.setPointerCapture(event.pointerId); const move = (moveEvent: PointerEvent) => { const rect = hostRef.current?.getBoundingClientRect(); if (!rect) return; const next = ((rect.right - moveEvent.clientX) / rect.width) * 100; setPreviewShare(Math.min(70, Math.max(32, next))); }; const stop = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); }; window.addEventListener("pointermove", move); window.addEventListener("pointerup", stop); }
  const columns = !previewVisible || !hasOriginalFiles || isMobile
    ? "minmax(0, 1fr)"
    : `minmax(0, ${100 - previewShare}fr) 10px minmax(340px, ${previewShare}fr)`;

  return <div className="mx-auto w-full max-w-[1800px]">
    {hasOriginalFiles ? (!previewVisible ? <div className="mb-2 flex justify-end"><Button variant="ghost" size="sm" onClick={() => setPreviewVisible(true)}><PanelRightOpen />{t("showCv")}</Button></div> : null) : <p className="mb-3 text-sm text-muted-foreground">{t("originalNotRetained")}</p>}
    <div ref={hostRef} className="grid min-w-0 items-start gap-y-3" style={{ gridTemplateColumns: columns }}>
      <ResultsList items={entries.map(entry => entry.result)} onActiveIndex={setActiveIndex} />
      {previewVisible && active.file ? <>
        {!isMobile ? <div role="separator" aria-orientation="vertical" aria-label={t("resizeCvPreview")} onPointerDown={startResize} className="sticky top-20 h-[calc(100svh-6.5rem)] cursor-col-resize touch-none rounded-full bg-border transition-colors hover:bg-primary/60" /> : null}
        <DocumentPreview file={active.file} onHide={() => setPreviewVisible(false)} />
      </> : null}
    </div>
  </div>;
}
