"use client";

import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, FileText, LoaderCircle, Minus, Plus } from "lucide-react";
import type { PDFDocumentProxy, PDFDocumentLoadingTask, RenderTask } from "pdfjs-dist";
import { Button } from "@/components/ui/button";

/** Render the actual exported page even when the browser has no embedded PDF viewer. */
export function ProfilePdfPage({ url }: { url: string }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [document, setDocument] = useState<PDFDocumentProxy | null>(null);
  const [page, setPage] = useState(1);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const { width, height } = size;
  const [zoom, setZoom] = useState(1);
  const [rendered, setRendered] = useState("");
  const [failed, setFailed] = useState(false);
  const [pageText, setPageText] = useState("");
  const renderKey = `${page}:${width}:${height}:${zoom}`;

  useEffect(() => {
    let disposed = false;
    let task: PDFDocumentLoadingTask | undefined;
    void import("pdfjs-dist").then((pdfjs) => {
      if (disposed) return;
      pdfjs.GlobalWorkerOptions.workerSrc = "/pdfjs/pdf.worker.min.mjs";
      task = pdfjs.getDocument({ url, wasmUrl: "/pdfjs/wasm/" });
      return task.promise;
    }).then((pdf) => { if (!disposed && pdf) setDocument(pdf); })
      .catch(() => { if (!disposed) setFailed(true); });
    return () => { disposed = true; void task?.destroy(); };
  }, [url]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver(([entry]) => setSize({
      width: Math.max(0, Math.floor(entry.contentRect.width - 2)),
      height: Math.max(0, Math.floor(entry.contentRect.height - 2)),
    }));
    observer.observe(host);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!document || width <= 0 || height <= 0 || !canvasRef.current) return;
    let disposed = false;
    let task: RenderTask | undefined;
    const canvas = canvasRef.current;
    void document.getPage(page).then(async (pdfPage) => {
      if (disposed) return;
      const base = pdfPage.getViewport({ scale: 1 });
      const cssScale = Math.min(width / base.width, height / base.height) * zoom;
      const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      const viewport = pdfPage.getViewport({ scale: cssScale * pixelRatio });
      canvas.width = Math.ceil(viewport.width);
      canvas.height = Math.ceil(viewport.height);
      canvas.style.width = `${viewport.width / pixelRatio}px`;
      canvas.style.height = `${viewport.height / pixelRatio}px`;
      task = pdfPage.render({ canvas, viewport });
      await task.promise;
      if (disposed) return;
      setRendered(renderKey);
      const text = await pdfPage.getTextContent();
      if (!disposed) setPageText(text.items.map((item) => "str" in item ? item.str : "").join(" "));
    }).catch((cause) => { if (!disposed && cause?.name !== "RenderingCancelledException") setFailed(true); });
    return () => { disposed = true; task?.cancel(); };
  }, [document, page, width, height, zoom, renderKey]);

  return <div className="flex h-full min-h-0 flex-col">
    <header className="flex min-h-11 shrink-0 flex-wrap items-center gap-1 border-b bg-background px-2 py-1.5">
      <h2 className="mr-auto flex items-center gap-2 px-1 text-sm font-medium"><FileText className="size-4 text-muted-foreground" aria-hidden />Document preview</h2>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon-sm" disabled={!document || page <= 1} aria-label="Previous PDF page" onClick={() => setPage((value) => value - 1)}><ChevronLeft /></Button>
        <span role="status" className="text-xs tabular-nums">{page} / {document?.numPages ?? "…"}</span>
        <Button variant="ghost" size="icon-sm" disabled={!document || page >= document.numPages} aria-label="Next PDF page" onClick={() => setPage((value) => value + 1)}><ChevronRight /></Button>
      </div>
      <div className="flex items-center gap-1">
        <Button variant="ghost" size="icon-sm" disabled={zoom <= 0.75} aria-label="Zoom out PDF" onClick={() => setZoom((value) => Math.max(.75, value - .25))}><Minus /></Button>
        <Button variant="ghost" size="sm" onClick={() => setZoom(1)}>Fit page</Button>
        <Button variant="ghost" size="icon-sm" disabled={zoom >= 2} aria-label="Zoom in PDF" onClick={() => setZoom((value) => Math.min(2, value + .25))}><Plus /></Button>
      </div>
    </header>
    <div ref={hostRef} className="relative min-h-0 flex-1 overflow-auto p-3 [scrollbar-gutter:stable]">
      {failed ? <p role="alert" className="p-3 text-sm">The PDF could not be displayed. Use Download → PDF to open it.</p> : <>
        {rendered !== renderKey ? <div role="status" className="absolute inset-0 z-10 flex items-center justify-center gap-2 bg-background/80 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Rendering page…</div> : null}
        <canvas ref={canvasRef} role="img" aria-label={`Profile document page ${page}`} className={`mx-auto block bg-white shadow-sm ${rendered === renderKey ? "" : "invisible"}`} />
        {rendered === renderKey ? <p className="sr-only">{pageText}</p> : null}
      </>}
    </div>
  </div>;
}
