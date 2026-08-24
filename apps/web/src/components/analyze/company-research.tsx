"use client";

import { useState } from "react";
import type { AnalysisReport, CompanyResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function CompanyResearchPanel({ report }: { report: AnalysisReport }) {
  const [research, setResearch] = useState<CompanyResearch | undefined>(report.company_research);
  const [state, setState] = useState<"idle" | "pending" | "error" | "timeout" | "completed">(
    report.company_research ? "completed" : "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const candidates = report.ai_analysis.research_candidates.filter(
    (candidate) => candidate.category === "company",
  );
  const enabled = report.ai_analysis.status === "succeeded" && candidates.length > 0;

  async function startResearch() {
    setState("pending");
    setError(null);
    try {
      const response = await fetch(
        `/api/analyses/${encodeURIComponent(report.analysis_id)}/research/company`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token }) },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail ?? payload.error ?? "company_research_failed";
        if (response.status === 504 || detail === "company_research_timeout") {
          setState("timeout");
          setError("Research przekroczył limit czasu. Możesz bezpiecznie spróbować ponownie.");
          return;
        }
        throw new Error(detail);
      }
      setResearch(payload.company_research);
      setState("completed");
    } catch (cause) {
      setState("error");
      setError(cause instanceof Error ? cause.message : "company_research_failed");
    }
  }

  return (
    <section className="space-y-3 rounded-md border border-violet-500/30 p-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="font-medium">Company research</h3>
          <p className="text-xs text-muted-foreground">
            Osobny public-web review; nie zmienia score ani bandu.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={startResearch}
          disabled={!enabled || state === "pending" || state === "completed"}
        >
          {state === "pending" ? "Researching…" : state === "completed" ? "Completed" : "Start company research"}
        </Button>
      </div>

      {!enabled ? (
        <p className="text-sm text-muted-foreground">
          Research niedostępny: analiza nie zwróciła bezpiecznych kandydatów firmowych.
        </p>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {research ? (
        <div className="space-y-3">
          {research.organizations.map((organization) => (
            <article key={organization.query_subject} className="rounded-md bg-muted/20 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <strong>{organization.query_subject}</strong>
                <Badge variant="outline">{organization.existence}</Badge>
                <Badge variant="outline">confidence: {organization.confidence}</Badge>
                {organization.limited_online_presence ? (
                  <Badge variant="outline">limited online presence</Badge>
                ) : null}
              </div>
              <p className="mt-2 text-muted-foreground">
                {[organization.activity, organization.operating_dates, organization.location, organization.relationship]
                  .filter(Boolean).join(" · ") || "Brak wystarczających danych publicznych."}
              </p>
              {organization.limited_online_presence_reason ? (
                <p className="mt-2 text-xs text-muted-foreground">{organization.limited_online_presence_reason}</p>
              ) : null}
              {organization.findings.map((finding, index) => (
                <div key={`${finding.kind}-${index}`} className="mt-2 border-l-2 pl-2">
                  <p>{finding.summary}</p>
                  <div className="mt-1 flex flex-wrap gap-2 text-xs">
                    {finding.source_urls.map((url) => (
                      <a key={url} href={url} target="_blank" rel="noreferrer" className="underline">
                        Source
                      </a>
                    ))}
                  </div>
                </div>
              ))}
            </article>
          ))}
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">Searches and limitations</summary>
            <ul className="mt-2 space-y-1">
              {research.searches_performed.map((search) => <li key={search}>Search: {search}</li>)}
              {research.search_limitations.map((limit) => <li key={limit}>Limit: {limit}</li>)}
            </ul>
          </details>
        </div>
      ) : null}
    </section>
  );
}
