"use client";

import type {
  AIAnalysis,
  AnalyzeItemResult,
  ChecklistId,
  ReviewFlag,
} from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { aiStatusMessage, partitionReviewFlags } from "@/lib/review-findings";
import { CompanyResearchPanel } from "@/components/analyze/company-research";

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

function FlagList({ flags, emptyText }: { flags: ReviewFlag[]; emptyText: string }) {
  if (!flags.length) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  }

  return (
    <div className="space-y-2">
      {flags.map((flag) => (
        <div key={flag.id} className="rounded-md border bg-muted/15 p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{flag.observation}</span>
            <Badge variant="outline">{flag.authority === "ai" ? "AI" : "Kod"}</Badge>
            <Badge variant="outline">{flag.confidence}</Badge>
          </div>
          <p className="mt-1 text-muted-foreground">{flag.reason}</p>
          {flag.evidence.length ? (
            <p className="mt-2 border-l-2 pl-2 text-xs text-muted-foreground">
              {flag.evidence[0].page_id}: „{flag.evidence[0].excerpt}”
            </p>
          ) : null}
          {flag.limitation ? (
            <p className="mt-2 text-xs text-muted-foreground">Ograniczenie: {flag.limitation}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

const CHECK_LABELS: Record<ChecklistId, string> = {
  contact: "Dane kontaktowe",
  education: "Edukacja",
  employment: "Zatrudnienie",
  timeline: "Chronologia",
  duration_claims: "Deklarowane okresy",
  relationships: "Relacje firma / klient / projekt",
  document_quality: "Jakość dokumentu",
  protected_boundaries: "Granice bezpiecznych wniosków",
};

function StructuredFacts({ analysis }: { analysis: AIAnalysis }) {
  const facts = [
    ...analysis.facts.contact.map((fact) => `${fact.kind}: ${fact.value}`),
    ...analysis.facts.education.map((fact) =>
      [fact.institution, fact.program, fact.study_dates].filter(Boolean).join(" — "),
    ),
    ...analysis.facts.employment.map((fact) =>
      [fact.organization, fact.role, fact.employment_dates].filter(Boolean).join(" — "),
    ),
  ];

  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        Dane odczytane z CV ({facts.length})
      </summary>
      {facts.length ? (
        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          {facts.map((fact, index) => <li key={`${fact}-${index}`}>• {fact}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          Analiza AI nie dodała ustrukturyzowanych danych.
        </p>
      )}
    </details>
  );
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
        const grouped = partitionReviewFlags(report.checklist.flags);
        const statusMessage = aiStatusMessage(
          report.ai_analysis.status,
          report.ai_analysis.failure_reason,
        );
        const checkedCount = Object.values(report.checklist.checks).filter(
          (check) => check.checked,
        ).length;

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
              {statusMessage ? (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
                  {statusMessage}
                </div>
              ) : null}

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

              <section className="space-y-2 rounded-md border border-rose-500/30 p-3">
                <h3 className="font-medium">Wymaga uwagi ({grouped.attention.length})</h3>
                <FlagList flags={grouped.attention} emptyText="Brak sygnałów wymagających uwagi." />
              </section>

              <section className="space-y-2 rounded-md border border-sky-500/30 p-3">
                <h3 className="font-medium">Warto wiedzieć ({grouped.worthKnowing.length})</h3>
                <FlagList flags={grouped.worthKnowing} emptyText="Brak dodatkowych informacji w tej grupie." />
              </section>

              <StructuredFacts analysis={report.ai_analysis} />

              <CompanyResearchPanel report={report} />

              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  Pozostałe sygnały ({grouped.remaining.length})
                </summary>
                <div className="mt-3 space-y-3">
                  <FlagList flags={grouped.remaining} emptyText="Brak pozostałych sygnałów." />
                  <div className="border-t pt-3 text-xs text-muted-foreground">
                    <p className="mb-2 font-medium">
                      Checklista analizy AI: {checkedCount}/{Object.keys(report.checklist.checks).length} obszarów
                    </p>
                    <ul className="grid gap-1 sm:grid-cols-2">
                      {Object.entries(report.checklist.checks).map(([id, check]) => (
                        <li key={id}>
                          {check.checked ? "✓" : "—"} {CHECK_LABELS[id as ChecklistId]}
                          {check.issue_count ? ` (${check.issue_count})` : ""}
                        </li>
                      ))}
                    </ul>
                  </div>
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
