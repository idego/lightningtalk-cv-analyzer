"use client";

import { useState } from "react";
import type { AnalysisReport, EducationResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function EducationResearchPanel({ report }: { report: AnalysisReport }) {
  const [research, setResearch] = useState<EducationResearch | undefined>(report.education_research);
  const [state, setState] = useState<"idle" | "pending" | "error" | "timeout" | "completed">(report.education_research ? "completed" : "idle");
  const [error, setError] = useState<string | null>(null);
  const enabled = report.ai_analysis.status === "succeeded" && report.ai_analysis.research_candidates.some((candidate) => candidate.category === "education_or_certification");

  async function startResearch() {
    setState("pending"); setError(null);
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/education`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail ?? payload.error ?? "education_research_failed";
        if (response.status === 504 || detail === "education_research_timeout") {
          setState("timeout"); setError("Research przekroczył limit czasu. Możesz bezpiecznie spróbować ponownie."); return;
        }
        throw new Error(detail);
      }
      setResearch(payload.education_research); setState("completed");
    } catch (cause) {
      setState("error"); setError(cause instanceof Error ? cause.message : "education_research_failed");
    }
  }

  return <section className="space-y-3 rounded-md border border-emerald-500/30 p-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="font-medium">Education &amp; Certification Research</h3><p className="text-xs text-muted-foreground">Osobny public-web review; nie zmienia score ani bandu.</p></div>
      <Button type="button" variant="outline" onClick={startResearch} disabled={!enabled || state === "pending" || state === "completed"}>
        {state === "pending" ? "Researching…" : state === "completed" ? "Completed" : "Start education research"}
      </Button>
    </div>
    {!enabled ? <p className="text-sm text-muted-foreground">Research niedostępny: analiza nie zwróciła bezpiecznych kandydatów edukacyjnych.</p> : null}
    {error ? <p className="text-sm text-destructive">{error}</p> : null}
    {research ? <div className="space-y-3">{research.credentials.map((credential) => <article key={`${credential.institution}:${credential.program ?? ""}`} className="rounded-md bg-muted/20 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><strong>{credential.institution}</strong><Badge variant="outline">institution: {credential.institution_exists}</Badge><Badge variant="outline">accreditation: {credential.accreditation_status}</Badge><Badge variant="outline">confidence: {credential.confidence}</Badge></div>
      <p className="mt-2 text-muted-foreground">{[credential.program, credential.degree, credential.certificate, credential.dates, credential.city, credential.country].filter(Boolean).join(" · ") || "Brak wystarczających danych publicznych."}</p>
      {credential.location_difference_for_review ? <p className="mt-2 rounded border border-amber-500/30 p-2 text-xs">Do review: {credential.location_difference_for_review} To nie jest weryfikacja lokalizacji kandydata.</p> : null}
      <p className="mt-2 text-xs text-muted-foreground">{credential.uncertainty}</p>
      {credential.findings.map((finding, index) => <div key={`${finding.kind}-${index}`} className="mt-2 border-l-2 pl-2"><p>{finding.summary}</p><div className="mt-1 flex flex-wrap gap-2 text-xs">{finding.source_urls.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer" className="underline">Source</a>)}</div></div>)}
    </article>)}<details className="text-xs text-muted-foreground"><summary className="cursor-pointer">Searches and limitations</summary><ul className="mt-2 space-y-1">{research.searches_performed.map((search) => <li key={search}>Search: {search}</li>)}{research.search_limitations.map((limit) => <li key={limit}>Limit: {limit}</li>)}</ul></details></div> : null}
  </section>;
}
