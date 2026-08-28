"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, LoaderCircle, Maximize2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCopy } from "@/lib/app-settings";

type ViewTransform = { x: number; y: number; scale: number };
type ContentBounds = { width: number; height: number };

const MIN_SCALE = 0.12;
const MAX_SCALE = 4;
const FIT_PADDING = 24;

export function DocumentPreview({ file, onHide }: { file: File; onHide: () => void }) {
  return <DocumentPreviewContent key={`${file.name}:${file.size}:${file.lastModified}`} file={file} onHide={onHide} />;
}

function DocumentPreviewContent({ file, onHide }: { file: File; onHide: () => void }) {
  const { t } = useCopy();
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const documentRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<ViewTransform>({ x: 0, y: 0, scale: 1 });
  const boundsRef = useRef<ContentBounds>({ width: 0, height: 0 });
  const userAdjustedRef = useRef(false);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; originX: number; originY: number } | null>(null);
  const transitionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [url] = useState(() => URL.createObjectURL(file));
  const isPdf = file.name.toLowerCase().endsWith(".pdf");
  const [loading, setLoading] = useState(!isPdf);
  const [error, setError] = useState<string | null>(null);

  const clamp = useCallback((next: ViewTransform): ViewTransform => {
    const viewport = viewportRef.current;
    const { width, height } = boundsRef.current;
    if (!viewport || !width || !height) return next;
    const scaledWidth = width * next.scale;
    const scaledHeight = height * next.scale;
    const x = scaledWidth <= viewport.clientWidth ? (viewport.clientWidth - scaledWidth) / 2 : Math.min(0, Math.max(viewport.clientWidth - scaledWidth, next.x));
    const y = scaledHeight <= viewport.clientHeight ? (viewport.clientHeight - scaledHeight) / 2 : Math.min(0, Math.max(viewport.clientHeight - scaledHeight, next.y));
    return { ...next, x, y };
  }, []);

  const applyTransform = useCallback((next: ViewTransform, programmatic = false) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bounded = clamp(next);
    transformRef.current = bounded;
    if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    canvas.dataset.programmatic = programmatic ? "true" : "false";
    canvas.style.transform = `translate3d(${bounded.x}px, ${bounded.y}px, 0) scale(${bounded.scale})`;
    if (programmatic) transitionTimerRef.current = setTimeout(() => { if (canvasRef.current) canvasRef.current.dataset.programmatic = "false"; }, 180);
  }, [clamp]);

  const measureDocument = useCallback(() => {
    const documentNode = documentRef.current;
    if (!documentNode) return false;
    const width = documentNode.scrollWidth;
    const height = documentNode.scrollHeight;
    if (!width || !height) return false;
    boundsRef.current = { width, height };
    if (canvasRef.current) {
      canvasRef.current.style.width = `${width}px`;
      canvasRef.current.style.height = `${height}px`;
    }
    return true;
  }, []);

  const fitToView = useCallback((programmatic = true) => {
    const viewport = viewportRef.current;
    if (!viewport || !measureDocument()) return;
    const { width, height } = boundsRef.current;
    const scale = Math.max(MIN_SCALE, Math.min(1, (viewport.clientWidth - FIT_PADDING * 2) / width, (viewport.clientHeight - FIT_PADDING * 2) / height));
    userAdjustedRef.current = false;
    applyTransform({ x: 0, y: 0, scale }, programmatic);
  }, [applyTransform, measureDocument]);

  useEffect(() => {
    if (!isPdf && documentRef.current) {
      documentRef.current.replaceChildren();
      void import("docx-preview")
        .then(({ renderAsync }) => renderAsync(file, documentRef.current!, undefined, {
          breakPages: true, ignoreWidth: false, ignoreHeight: true, renderHeaders: true, renderFooters: true, ignoreLastRenderedPageBreak: false,
        }))
        .then(() => { setLoading(false); requestAnimationFrame(() => fitToView(false)); })
        .catch(() => { setLoading(false); setError(t("docxPreviewFailed")); });
    }
    return () => {
      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
      URL.revokeObjectURL(url);
    };
  }, [file, fitToView, isPdf, t, url]);

  useEffect(() => {
    if (isPdf || !viewportRef.current) return;
    let previousWidth = 0;
    let previousHeight = 0;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (Math.abs(width - previousWidth) < 2 && Math.abs(height - previousHeight) < 2) return;
      previousWidth = width;
      previousHeight = height;
      requestAnimationFrame(() => userAdjustedRef.current
        ? (measureDocument() && applyTransform(transformRef.current))
        : fitToView(false));
    });
    observer.observe(viewportRef.current);
    return () => observer.disconnect();
  }, [applyTransform, fitToView, isPdf, measureDocument]);

  function handleWheel(event: React.WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    userAdjustedRef.current = true;
    const current = transformRef.current;
    if (event.ctrlKey || event.metaKey) {
      const viewport = viewportRef.current;
      if (!viewport) return;
      const rect = viewport.getBoundingClientRect();
      const pointerX = event.clientX - rect.left;
      const pointerY = event.clientY - rect.top;
      const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, current.scale * Math.exp(-event.deltaY * 0.008)));
      const ratio = scale / current.scale;
      applyTransform({ scale, x: pointerX - (pointerX - current.x) * ratio, y: pointerY - (pointerY - current.y) * ratio });
      return;
    }
    const deltaX = event.deltaX || (event.shiftKey ? event.deltaY : 0);
    const deltaY = event.shiftKey && !event.deltaX ? 0 : event.deltaY;
    applyTransform({ ...current, x: current.x - deltaX, y: current.y - deltaY });
  }

  function startPan(event: React.PointerEvent<HTMLDivElement>) {
    if (event.button !== 0) return;
    userAdjustedRef.current = true;
    event.currentTarget.setPointerCapture(event.pointerId);
    const current = transformRef.current;
    dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, originX: current.x, originY: current.y };
    event.currentTarget.dataset.panning = "true";
  }

  function movePan(event: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    applyTransform({ ...transformRef.current, x: drag.originX + event.clientX - drag.x, y: drag.originY + event.clientY - drag.y });
  }

  function stopPan(event: React.PointerEvent<HTMLDivElement>) {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    event.currentTarget.dataset.panning = "false";
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  return (
    <aside className="sticky top-20 flex h-[calc(100svh-6.5rem)] min-w-0 flex-col overflow-hidden rounded-xl border bg-muted/35">
      <div className="flex min-w-0 items-center gap-2 border-b bg-background px-3 py-2">
        <FileText className="size-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{file.name}</span>
        {!isPdf ? <Button variant="ghost" size="icon" className="size-8" onClick={() => fitToView()} aria-label={t("fitCvPreview")}><Maximize2 className="size-4" /></Button> : null}
        <Button variant="ghost" size="icon" className="size-8" render={<a href={url} target="_blank" rel="noreferrer" aria-label={t("openOriginalFile")}><ExternalLink className="size-4" /></a>} />
        <Button variant="ghost" size="icon" className="size-8" onClick={onHide} aria-label={t("hideCvPreview")}><X className="size-4" /></Button>
      </div>
      {isPdf && url ? (
        <div className="relative min-h-0 flex-1 overflow-hidden bg-muted/25"><iframe title={`${t("fileDetails")}: ${file.name}`} src={url} className="h-full w-full border-0 bg-white" /></div>
      ) : (
        <div ref={viewportRef} className="document-preview-viewport relative min-h-0 flex-1 overflow-hidden bg-muted/25" onWheel={handleWheel} onPointerDown={startPan} onPointerMove={movePan} onPointerUp={stopPan} onPointerCancel={stopPan}>
          {loading ? <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80"><LoaderCircle className="size-6 animate-spin" /></div> : null}
          {error ? <div className="absolute inset-x-4 top-4 z-10 rounded-lg border border-amber-500/30 bg-background p-3 text-sm">{error}</div> : null}
          <div ref={canvasRef} className="document-preview-canvas absolute left-0 top-0 origin-top-left will-change-transform" data-programmatic="false"><div ref={documentRef} className="docx-preview-host inline-block p-4" /></div>
        </div>
      )}
    </aside>
  );
}
