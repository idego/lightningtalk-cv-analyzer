"use client";

import { useMemo, useState } from "react";
import type { AnalyzeBatchResponse, AnalyzeItemResult } from "@/lib/analyze-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ResultsList } from "@/components/analyze/results-list";

const ACCEPT = ".pdf,.docx";

export function UploadPanel() {
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<AnalyzeItemResult[]>([]);
  const [error, setError] = useState<string | null>(null);

  const acceptedFiles = useMemo(
    () => files.filter((f) => f.name.toLowerCase().endsWith(".pdf") || f.name.toLowerCase().endsWith(".docx")),
    [files]
  );

  function onFilesSelected(list: FileList | null) {
    if (!list) return;
    const incoming = Array.from(list);
    setFiles((prev) => [...prev, ...incoming]);
  }

  async function submit() {
    setError(null);
    if (!acceptedFiles.length) {
      setError("Add at least one .pdf or .docx file.");
      return;
    }

    setLoading(true);
    try {
      const form = new FormData();
      acceptedFiles.forEach((f) => form.append("files", f, f.name));

      const res = await fetch("/api/analyze", {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const payload = await res.json().catch(() => ({}));
        throw new Error(payload.error ?? `Analysis failed (${res.status})`);
      }

      const payload = (await res.json()) as AnalyzeBatchResponse;
      setItems(payload.results ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected analysis error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Upload CV files</CardTitle>
          <CardDescription>
            Upload one or more `.pdf`/`.docx` files for consistency analysis.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <label
            className="flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-muted-foreground/30 bg-muted/20 p-6 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              onFilesSelected(e.dataTransfer.files);
            }}
          >
            <input
              type="file"
              className="hidden"
              multiple
              accept={ACCEPT}
              onChange={(e) => onFilesSelected(e.target.files)}
            />
            <p className="text-sm font-medium">Drag and drop files here, or click to select</p>
            <p className="mt-1 text-xs text-muted-foreground">Accepted: .pdf, .docx</p>
          </label>

          {files.length ? (
            <div className="rounded-md border p-3 text-sm">
              <p className="mb-2 font-medium">Queued files ({acceptedFiles.length} valid)</p>
              <ul className="space-y-1 text-muted-foreground">
                {files.map((f, idx) => (
                  <li key={`${f.name}-${idx}`}>• {f.name}</li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="flex items-center gap-3">
            <Button onClick={submit} disabled={loading || !acceptedFiles.length}>
              {loading ? "Processing..." : "Analyze files"}
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                setFiles([]);
                setItems([]);
                setError(null);
              }}
              disabled={loading}
            >
              Reset
            </Button>
          </div>

          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <p className="text-xs text-muted-foreground">
            Decision-support only. This workflow analyzes consistency and does not verify physical location.
          </p>
        </CardContent>
      </Card>

      <ResultsList items={items} />
    </div>
  );
}
