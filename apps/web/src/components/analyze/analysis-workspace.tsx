"use client";

import { useRef, useState } from "react";
import { ArrowLeft, PanelRightClose, PanelRightOpen } from "lucide-react";
import type { AnalyzeItemResult } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { ResultsList } from "@/components/analyze/results-list";
import { DocumentPreview } from "@/components/analyze/document-preview";
import { useCopy } from "@/lib/app-settings";
import { useIsMobile } from "@/hooks/use-mobile";

export type AnalyzedFile = { file: File | null; result: AnalyzeItemResult };

export function AnalysisWorkspace({
  entries,
  compact = false,
  onBack,
  analyzedCount,
}: {
  entries: AnalyzedFile[];
  compact?: boolean;
  onBack?: () => void;
  analyzedCount?: string;
}) {
  const { t } = useCopy();
  const isMobile = useIsMobile();
  const hostRef = useRef<HTMLDivElement>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const [previewVisible, setPreviewVisible] = useState(!compact);
  const [previewShare, setPreviewShare] = useState(55);
  const active = entries[Math.min(activeIndex, entries.length - 1)];
  const hasOriginalFiles = entries.some(({ file }) => file !== null);
  function resizePreview(next: number) { setPreviewShare(Math.min(70, Math.max(32, next))); }
  function startResize(event: React.PointerEvent<HTMLDivElement>) { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); const move = (moveEvent: PointerEvent) => { const rect = hostRef.current?.getBoundingClientRect(); if (!rect) return; resizePreview(((rect.right - moveEvent.clientX) / rect.width) * 100); }; const stop = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", stop); }; window.addEventListener("pointermove", move); window.addEventListener("pointerup", stop); }
  function resizeWithKeyboard(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    resizePreview(previewShare + (event.key === "ArrowLeft" ? 2 : -2));
  }
  const columns = !previewVisible || !hasOriginalFiles || isMobile
    ? isMobile ? "minmax(0, 1fr)" : "minmax(0, 1fr) 0px minmax(0, 0fr)"
    : `minmax(0, ${100 - previewShare}fr) 16px minmax(340px, ${previewShare}fr)`;

  return <div className="mx-auto w-full max-w-[1800px]">
    <div className="mb-3 flex min-h-10 items-start justify-between gap-4">
      <div className="flex items-center gap-4">
        {onBack ? <Button variant="outline" onClick={onBack}><ArrowLeft data-icon="inline-start" />{t("back")}</Button> : null}
        {analyzedCount ? <p className="text-sm text-muted-foreground">{analyzedCount}</p> : null}
      </div>
      {!hasOriginalFiles ? <div className="flex flex-col items-end gap-1.5">
        <p className="text-sm text-foreground/75">{t("originalNotRetained")}</p>
        <Button variant="ghost" size="sm" disabled><PanelRightOpen />{t("showCv")}</Button>
      </div> : <Button variant="ghost" size="sm" onClick={() => setPreviewVisible((visible) => !visible)}>
        {previewVisible ? <PanelRightClose /> : <PanelRightOpen />}
        {t(previewVisible ? "hideCv" : "showCv")}
      </Button>}
    </div>
    <div ref={hostRef} className="grid min-w-0 items-start gap-y-3 transition-[grid-template-columns] duration-[180ms] ease-[var(--motion-ease-out)] motion-reduce:transition-none" style={{ gridTemplateColumns: columns }}>
      <ResultsList items={entries.map(entry => entry.result)} onActiveIndex={setActiveIndex} />
      {active.file ? <>
        {!isMobile ? <div role="separator" aria-orientation="vertical" aria-label={t("resizeCvPreview")} aria-valuemin={32} aria-valuemax={70} aria-valuenow={Math.round(previewShare)} tabIndex={previewVisible ? 0 : -1} onKeyDown={resizeWithKeyboard} onPointerDown={startResize} className={`group/separator sticky top-20 z-10 h-[calc(100svh-6.5rem)] w-full touch-none focus-visible:outline-none ${previewVisible ? "cursor-col-resize" : "pointer-events-none opacity-0"}`}><span aria-hidden="true" className="absolute inset-y-0 left-1/2 w-0.5 -translate-x-1/2 bg-border transition-colors group-hover/separator:bg-primary/70 group-focus-visible/separator:bg-primary group-active/separator:bg-primary" /></div> : null}
        <div
          aria-hidden={!previewVisible}
          inert={!previewVisible}
          className={`grid min-w-0 transition-[grid-template-rows,opacity] duration-[180ms] ease-[var(--motion-ease-out)] motion-reduce:transition-none ${previewVisible ? "opacity-100" : "pointer-events-none opacity-0"}`}
          style={{ gridTemplateRows: previewVisible ? "minmax(0, 1fr)" : "minmax(0, 0fr)" }}
        >
          <div className="min-h-0 min-w-0 overflow-hidden">
            <DocumentPreview file={active.file} onHide={() => setPreviewVisible(false)} />
          </div>
        </div>
      </> : null}
    </div>
  </div>;
}
