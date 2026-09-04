"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ExternalLink, FileText, LoaderCircle, Maximize2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { DocumentSource } from "@/lib/analyze-types";
import { useCopy } from "@/lib/app-settings";
import { consumePreviewWheel, fitWidthTransform, measureRenderedDocx, pdfPageWidthUrl, wheelTransform, type ViewTransform } from "@/lib/document-preview";

type ContentBounds = { width: number; height: number };

export function DocumentPreview({ source, onHide }: { source: DocumentSource; onHide: () => void }) {
  const key = source instanceof File ? `file:${source.name}:${source.size}:${source.lastModified}` : `stored:${source.url}:${source.name}`;
  return <DocumentPreviewContent key={key} source={source} onHide={onHide} />;
}

function DocumentPreviewContent({ source, onHide }: { source: DocumentSource; onHide: () => void }) {
  const { t } = useCopy();
  const viewportRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const documentRef = useRef<HTMLDivElement>(null);
  const transformRef = useRef<ViewTransform>({ x: 0, y: 0, scale: 1 });
  const boundsRef = useRef<ContentBounds>({ width: 0, height: 0 });
  const userAdjustedRef = useRef(false);
  const dragRef = useRef<{ pointerId: number; x: number; y: number; originX: number; originY: number } | null>(null);
  const transitionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const name = source.name;
  const isPdf = name.toLowerCase().endsWith(".pdf");
  const [blob, setBlob] = useState<Blob | null>(null);
  const [url, setUrl] = useState<string | null>(null);
  const [fetching, setFetching] = useState(!(source instanceof File));
  const [rendering, setRendering] = useState(!isPdf);
  const [error, setError] = useState<string | null>(null);
  const loading = fetching || (rendering && !error);

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
    const { width, height } = measureRenderedDocx(documentNode);
    if (!width || !height) return false;
    boundsRef.current = { width, height };
    if (canvasRef.current) {
      canvasRef.current.style.width = `${width}px`;
      canvasRef.current.style.height = `${height}px`;
    }
    return true;
  }, []);

  const fitToWidth = useCallback((programmatic = true) => {
    const viewport = viewportRef.current;
    if (!viewport || !measureDocument()) return;
    const { width } = boundsRef.current;
    userAdjustedRef.current = false;
    applyTransform(fitWidthTransform({ viewportWidth: viewport.clientWidth, contentWidth: width }), programmatic);
  }, [applyTransform, measureDocument]);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    const adopt = (resolved: Blob) => {
      if (cancelled) return;
      objectUrl = URL.createObjectURL(resolved);
      setBlob(resolved);
      setUrl(objectUrl);
      setFetching(false);
    };
    if (source instanceof File) {
      adopt(source);
    } else {
      queueMicrotask(() => { if (!cancelled) setFetching(true); });
      fetch(source.url, { cache: "no-store" })
        .then((response) => { if (!response.ok) throw new Error(String(response.status)); return response.blob(); })
        .then(adopt)
        .catch(() => { if (cancelled) return; setFetching(false); setRendering(false); setError(t("documentFetchFailed")); });
    }
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [source, t]);

  useEffect(() => {
    if (isPdf || !blob || !documentRef.current) return;
    let cancelled = false;
    documentRef.current.replaceChildren();
    void import("docx-preview")
      .then(({ renderAsync }) => renderAsync(blob, documentRef.current!, undefined, {
        breakPages: true, ignoreWidth: false, ignoreHeight: true, renderHeaders: true, renderFooters: true, ignoreLastRenderedPageBreak: false,
      }))
      .then(() => { if (cancelled) return; setRendering(false); requestAnimationFrame(() => fitToWidth(false)); })
      .catch(() => { if (cancelled) return; setRendering(false); setError(t("docxPreviewFailed")); });
    return () => {
      cancelled = true;
      if (transitionTimerRef.current) clearTimeout(transitionTimerRef.current);
    };
  }, [blob, fitToWidth, isPdf, t]);

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
        : fitToWidth(false));
    });
    observer.observe(viewportRef.current);
    return () => observer.disconnect();
  }, [applyTransform, fitToWidth, isPdf, measureDocument]);

  const handleWheel = useCallback((event: WheelEvent) => {
    consumePreviewWheel(event);
    userAdjustedRef.current = true;
    const current = transformRef.current;
    const viewport = viewportRef.current;
    if (!viewport) return;
    const rect = viewport.getBoundingClientRect();
    const deltaX = event.deltaX || (event.shiftKey ? event.deltaY : 0);
    const deltaY = event.shiftKey && !event.deltaX ? 0 : event.deltaY;
    applyTransform(wheelTransform(current, {
      deltaX,
      deltaY,
      zoom: event.ctrlKey || event.metaKey,
      pointerX: event.clientX - rect.left,
      pointerY: event.clientY - rect.top,
    }));
  }, [applyTransform]);

  useEffect(() => {
    const viewport = viewportRef.current;
    if (isPdf || !viewport) return;
    viewport.addEventListener("wheel", handleWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", handleWheel);
  }, [handleWheel, isPdf]);

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
    <aside className="sticky top-28 flex h-[calc(100svh-8rem)] min-w-0 flex-col overflow-hidden rounded-xl border bg-muted/35">
      <div className="flex min-w-0 items-center gap-2 border-b bg-background px-3 py-2">
        <FileText className="size-4 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium">{name}</span>
        {!isPdf ? <Button variant="ghost" size="icon" className="size-8" onClick={() => fitToWidth()} aria-label={t("fitCvPreview")}><Maximize2 className="size-4" /></Button> : null}
        {url ? <Button variant="ghost" size="icon" className="size-8" render={<a href={url} target="_blank" rel="noreferrer" aria-label={t("openOriginalFile")}><ExternalLink className="size-4" /></a>} /> : null}
        <Button variant="ghost" size="icon" className="size-8" onClick={onHide} aria-label={t("hideCvPreview")}><X className="size-4" /></Button>
      </div>
      {isPdf && url ? (
        <div className="relative min-h-0 flex-1 overflow-hidden bg-muted/25"><iframe title={name} src={pdfPageWidthUrl(url)} className="h-full w-full border-0 bg-white" /></div>
      ) : (
        <div ref={viewportRef} className="document-preview-viewport relative min-h-0 flex-1 overflow-hidden bg-muted/25" onPointerDown={startPan} onPointerMove={movePan} onPointerUp={stopPan} onPointerCancel={stopPan}>
          {loading ? <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80"><LoaderCircle className="size-6 animate-spin" /></div> : null}
          {error ? <div className="absolute inset-x-4 top-4 z-10 rounded-lg border border-amber-500/30 bg-background p-3 text-sm">{error}</div> : null}
          <div ref={canvasRef} className="document-preview-canvas absolute left-0 top-0 origin-top-left will-change-transform" data-programmatic="false"><div ref={documentRef} className="docx-preview-host inline-block" /></div>
        </div>
      )}
    </aside>
  );
}
