"use client";

import type { AnalyzeItemResult } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

function bandBadgeClass(band: string) {
  switch (band) {
    case "green":
      return "bg-emerald-500/20 text-emerald-700 dark:text-emerald-300";
    case "amber":
      return "bg-amber-500/20 text-amber-700 dark:text-amber-300";
    case "red":
      return "bg-rose-500/20 text-rose-700 dark:text-rose-300";
    case "gray":
      return "bg-slate-500/20 text-slate-700 dark:text-slate-300";
    default:
      return "";
  }
}

export function ResultsList({ items }: { items: AnalyzeItemResult[] }) {
  if (!items.length) {
    return null;
  }

  return (
    <div className="space-y-4">
      {items.map((item) => {
        if (item.status === "error") {
          return (
            <Card key={item.filename} className="border-destructive/40">
              <CardHeader>
                <CardTitle className="text-base">{item.filename}</CardTitle>
                <CardDescription className="text-destructive">{item.error}</CardDescription>
              </CardHeader>
            </Card>
          );
        }

        const report = item.report;
        const claimed = report.claimed_location.raw ?? report.claimed_location.country_code ?? "Unknown";

        return (
          <Card key={item.filename}>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{item.filename}</CardTitle>
                  <CardDescription>{report.summary}</CardDescription>
                </div>
                <Badge className={bandBadgeClass(report.band)}>{report.band.toUpperCase()}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid gap-2 text-sm sm:grid-cols-3">
                <div>
                  <span className="text-muted-foreground">Score:</span>{" "}
                  {report.band === "gray"
                    ? "Nie oceniono — za mało niezależnych danych"
                    : report.score}
                </div>
                <div>
                  <span className="text-muted-foreground">Claimed:</span> {claimed}
                </div>
                <div>
                  <span className="text-muted-foreground">Signals:</span> {report.signal_count}
                </div>
              </div>

              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">Show findings ({report.findings.length})</summary>
                <div className="mt-3 overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Signal</TableHead>
                        <TableHead>Observed</TableHead>
                        <TableHead>Claimed</TableHead>
                        <TableHead>Direction</TableHead>
                        <TableHead>Weight</TableHead>
                        <TableHead>Rationale</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {report.findings.map((f, idx) => (
                        <TableRow key={`${f.signal}-${idx}`}>
                          <TableCell>{f.signal}</TableCell>
                          <TableCell>{f.observed}</TableCell>
                          <TableCell>{f.claimed ?? "-"}</TableCell>
                          <TableCell>{f.direction}</TableCell>
                          <TableCell>{f.weight}</TableCell>
                          <TableCell>{f.rationale}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </details>

              <p className="text-xs text-muted-foreground">{report.disclaimer}</p>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
