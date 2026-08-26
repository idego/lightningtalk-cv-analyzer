"use client";

import { useEffect, useRef, useState } from "react";
import { ThinkingOrb } from "thinking-orbs";
import type {
  AIAnalysis,
  AnalyzeItemResult,
  ChecklistId,
  ReviewFlag,
} from "@/lib/analyze-types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { aiStatusMessage, aiValidationState, partitionReviewFlags, presentReviewFlag, structuredFactLines } from "@/lib/review-findings";
import { CompanyResearchPanel } from "@/components/analyze/company-research";
import { EducationResearchPanel } from "@/components/analyze/education-research";
import { LinkedInResearchPanel } from "@/components/analyze/linkedin-research";
import { useCopy } from "@/lib/app-settings";

function aiFactCount(analysis: AIAnalysis) {
  return analysis.facts.contact.length
    + analysis.facts.education.length
    + analysis.facts.employment.length;
}

function FlagList({ flags, emptyText, reportLanguage }: { flags: ReviewFlag[]; emptyText: string; reportLanguage: "en" | "pl" }) {
  if (!flags.length) {
    return <p className="text-sm text-muted-foreground">{emptyText}</p>;
  }

  return (
    <div className="space-y-2">
      {flags.map((flag) => {
        const copy = presentReviewFlag(flag, reportLanguage);
        return (
        <div key={flag.id} className="rounded-md border bg-muted/15 p-3 text-sm">
          <dl className="space-y-2">
            <div><dt className="text-xs font-medium text-muted-foreground">What we found</dt><dd className="mt-0.5 font-medium">{copy.whatWeFound}</dd></div>
            <div><dt className="text-xs font-medium text-muted-foreground">Why it matters</dt><dd className="mt-0.5">{copy.whyItMatters}</dd></div>
            <div><dt className="text-xs font-medium text-muted-foreground">What to check</dt><dd className="mt-0.5">{copy.whatToCheck}</dd></div>
          </dl>
          {flag.evidence.length ? (
            <p className="mt-2 border-l-2 pl-2 text-xs text-muted-foreground">
              Evidence: „{flag.evidence[0].excerpt}”
            </p>
          ) : null}
        </div>
      );})}
    </div>
  );
}

const CHECK_LABELS: Record<ChecklistId, { en: string; pl: string }> = {
  contact: { en: "Contact details", pl: "Dane kontaktowe" },
  education: { en: "Education", pl: "Edukacja" },
  employment: { en: "Employment", pl: "Zatrudnienie" },
  timeline: { en: "Timeline", pl: "Chronologia" },
  duration_claims: { en: "Stated durations", pl: "Deklarowane okresy" },
  relationships: { en: "Company / client / project relations", pl: "Relacje firma / klient / projekt" },
  document_quality: { en: "Document quality", pl: "Jakość dokumentu" },
  protected_boundaries: { en: "Safe inference boundaries", pl: "Granice bezpiecznych wniosków" },
};

function StructuredFacts({ report }: { report: Extract<AnalyzeItemResult, { status: "ok" }>["report"] }) {
  const { t } = useCopy();
  const facts = structuredFactLines(report);

  return (
    <details className="rounded-md border p-3">
      <summary className="cursor-pointer text-sm font-medium">
        {t("extracted")} ({facts.length})
      </summary>
      {facts.length ? (
        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          {facts.map((fact, index) => <li key={`${fact}-${index}`}>• {fact}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          No structured CV data was found yet.
        </p>
      )}
    </details>
  );
}

export function ResultsList({ items, onActiveIndex }: { items: AnalyzeItemResult[]; onActiveIndex?: (index: number) => void }) {
  const { settings, t } = useCopy();
  const reportRefs = useRef<Array<HTMLElement | null>>([]);
  const [reportOverrides, setReportOverrides] = useState<Record<string, Extract<AnalyzeItemResult, { status: "ok" }>["report"]>>({});
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<Record<string, string>>({});

  async function retryAi(report: Extract<AnalyzeItemResult, { status: "ok" }>["report"]) {
    setRetryingId(report.analysis_id);
    setRetryError(previous => ({ ...previous, [report.analysis_id]: "" }));
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/ai/retry`, { method: "POST" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error ?? payload.detail ?? "AI retry failed");
      setReportOverrides(previous => ({ ...previous, [report.analysis_id]: payload }));
    } catch (error) {
      setRetryError(previous => ({ ...previous, [report.analysis_id]: error instanceof Error ? error.message : "AI retry failed" }));
    } finally {
      setRetryingId(null);
    }
  }

  useEffect(() => {
    if (!onActiveIndex) return;
    const ratios = new Map<Element, number>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
      let bestIndex = 0; let bestRatio = -1;
      reportRefs.current.forEach((element, index) => { const ratio = element ? ratios.get(element) ?? 0 : 0; if (ratio > bestRatio) { bestRatio = ratio; bestIndex = index; } });
      if (bestRatio > 0) onActiveIndex(bestIndex);
    }, { threshold: [0, 0.2, 0.4, 0.6, 0.8, 1] });
    reportRefs.current.forEach(element => { if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [items, onActiveIndex]);
  if (!items.length) {
    return null;
  }

  return (
    <div className="space-y-4">
      {items.map((item, itemIndex) => {
        if (item.status === "error") {
          return (
            <Card key={`${item.filename}-${itemIndex}`} ref={(node) => { reportRefs.current[itemIndex] = node; }} className="scroll-mt-20 border-destructive/40">
              <CardHeader>
                <CardTitle className="text-base">{item.filename}</CardTitle>
                <CardDescription className="text-destructive">{item.error}</CardDescription>
              </CardHeader>
            </Card>
          );
        }

        const report = reportOverrides[item.report.analysis_id] ?? item.report;
        const claimed = report.claimed_location.raw ?? report.claimed_location.country_code ?? "Unknown";
        const grouped = partitionReviewFlags(report.checklist.flags);
        const statusMessage = aiStatusMessage(
          report.ai_analysis.status,
          report.ai_analysis.failure_reason,
          settings.uiLanguage,
        );
        const validationState = aiValidationState(report.ai_analysis);
        const checkedCount = Object.values(report.checklist.checks).filter(
          (check) => check.checked,
        ).length;
        const factCount = aiFactCount(report.ai_analysis);
        const findingCount = report.ai_analysis.findings.length;
        const reportDescription = report.ai_analysis.status === "succeeded"
          ? (settings.uiLanguage === "pl" ? `AI odczytało ${factCount} danych i dodało ${findingCount} uwag do przejrzenia.` : `AI extracted ${factCount} facts and added ${findingCount} review notes.`)
          : (settings.uiLanguage === "pl" ? "Analiza AI nie zwróciła pełnego wyniku." : "AI analysis did not return a complete result.");

        return (
          <Card key={`${item.filename}-${itemIndex}`} ref={(node) => { reportRefs.current[itemIndex] = node; }} className="scroll-mt-20">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{item.filename}</CardTitle>
                  <CardDescription>{reportDescription}</CardDescription>
                </div>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">{grouped.attention.length} {t("needsAttention").toLowerCase()} · {grouped.worthKnowing.length} {t("worthKnowing").toLowerCase()} · {checkedCount}/{Object.keys(report.checklist.checks).length} {settings.uiLanguage === "pl" ? "sprawdzono" : "checked"}</p>
            </CardHeader>
            <CardContent className="space-y-3">
              {statusMessage ? (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
                  <div className="flex flex-wrap items-center justify-between gap-3"><span className="flex items-center gap-2">{report.ai_analysis.status === "pending" ? <ThinkingOrb state="working" size={20} theme="auto" aria-label="AI analysis in progress" /> : null}{statusMessage}</span>{report.ai_analysis.status === "failed" && report.ai_analysis.manual_retry_available ? <Button variant="outline" size="sm" disabled={retryingId === report.analysis_id} onClick={() => retryAi(report)}>{retryingId === report.analysis_id ? (settings.uiLanguage === "pl" ? "Ponawianie…" : "Retrying…") : (settings.uiLanguage === "pl" ? "Ponów analizę AI" : "Retry AI analysis")}</Button> : null}</div>
                  {retryError[report.analysis_id] ? <p className="mt-2 text-xs text-destructive">{retryError[report.analysis_id]}</p> : null}
                </div>
              ) : null}
              {validationState.warning ? (
                <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
                  {validationState.warning}
                </div>
              ) : null}

              <section className="space-y-2 rounded-md border border-rose-500/30 p-3">
                <h3 className="font-medium">{t("needsAttention")} ({grouped.attention.length})</h3>
                <FlagList flags={grouped.attention} emptyText={t("noAttention")} reportLanguage={report.ai_analysis.report_language} />
              </section>

              <section className="space-y-2 rounded-md border border-sky-500/30 p-3">
                <h3 className="font-medium">{t("worthKnowing")} ({grouped.worthKnowing.length})</h3>
                <FlagList flags={grouped.worthKnowing} emptyText={t("noWorth")} reportLanguage={report.ai_analysis.report_language} />
              </section>

              <StructuredFacts report={report} />

              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {t("deterministic")}: {report.band === "gray" ? "insufficient evidence" : report.band.toUpperCase()}
                </summary>
                <div className="mt-3 space-y-3 text-sm">
                  <p className="text-muted-foreground">{report.summary}</p>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <div><span className="text-muted-foreground">Score:</span> {report.band === "gray" ? "Not assessed" : report.score}</div>
                    <div><span className="text-muted-foreground">Claimed:</span> {claimed}</div>
                    <div><span className="text-muted-foreground">Signals:</span> {report.signal_count}</div>
                  </div>
                </div>
              </details>

              <CompanyResearchPanel report={report} />

              <EducationResearchPanel report={report} />
              <LinkedInResearchPanel report={report} />

              <details className="rounded-md border p-3">
                <summary className="cursor-pointer text-sm font-medium">
                  {t("remaining")} ({grouped.remaining.length})
                </summary>
                <div className="mt-3 space-y-3">
                  <FlagList flags={grouped.remaining} emptyText={t("noRemaining")} reportLanguage={report.ai_analysis.report_language} />
                  <div className="border-t pt-3 text-xs text-muted-foreground">
                    <p className="mb-2 font-medium">
                      {settings.uiLanguage === "pl" ? "Checklista AI" : "AI checklist"}: {checkedCount}/{Object.keys(report.checklist.checks).length} {settings.uiLanguage === "pl" ? "obszarów" : "areas"}
                    </p>
                    <ul className="grid gap-1 sm:grid-cols-2">
                      {Object.entries(report.checklist.checks).map(([id, check]) => (
                        <li key={id}>
                          {check.checked ? "✓" : "—"} {CHECK_LABELS[id as ChecklistId][settings.uiLanguage]}
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
