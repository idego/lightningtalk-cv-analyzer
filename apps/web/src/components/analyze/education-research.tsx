"use client";

import { useEffect, useRef, useState } from "react";
import { ThinkingOrb } from "thinking-orbs";
import type { AnalysisReport, EducationResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

function institutionStatus(status: string) {
  return {
    supported: "Institution confirmed",
    mismatch: "Institution mismatch",
    evidence_unavailable: "Institution not confirmed",
  }[status] ?? "Institution not confirmed";
}

function accreditationStatus(status: string | null) {
  if (status === "established") return "Accreditation confirmed";
  if (status === "not_established") return "Accreditation not confirmed";
  return "Accreditation unknown";
}

function confidenceLabel(confidence: string) {
  return `Confidence: ${confidence.replaceAll("_", " ")}`;
}

export function EducationResearchPanel({
  report,
  onResearchChange,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: EducationResearch) => void;
}) {
  const [research, setResearch] = useState<EducationResearch | undefined>(report.education_research);
  const [state, setState] = useState<"idle" | "pending" | "error" | "timeout" | "completed">(report.education_research ? "completed" : "idle");
  const [error, setError] = useState<string | null>(null);
  const automatic = useAutoResearchState(report.analysis_id, "education");
  const notifiedAutomatic = useRef<EducationResearch | null>(null);
  const onResearchChangeRef = useRef(onResearchChange);
  const enabled = report.ai_analysis.status === "succeeded" && report.ai_analysis.research_candidates.some((candidate) => candidate.category === "education_or_certification");
  const visibleResearch = research ?? automatic?.result as EducationResearch | undefined;
  const busy = state === "pending" || automatic?.status === "pending" || automatic?.status === "running";
  const completed = state === "completed" || automatic?.status === "succeeded";
  const hasContent = Boolean(visibleResearch || error || automatic?.message || !enabled);

  useEffect(() => {
    onResearchChangeRef.current = onResearchChange;
  }, [onResearchChange]);

  useEffect(() => {
    const result = automatic?.status === "succeeded"
      ? automatic.result as EducationResearch | undefined
      : undefined;
    if (!result || notifiedAutomatic.current === result) return;
    notifiedAutomatic.current = result;
    onResearchChangeRef.current?.(result);
  }, [automatic?.result, automatic?.status]);

  async function startResearch() {
    setState("pending"); setError(null);
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/education`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail ?? payload.error ?? "education_research_failed";
        if (response.status === 504 || detail === "education_research_timeout") {
          setState("timeout"); setError("Research timed out. You can safely try again."); return;
        }
        throw new Error(detail);
      }
      setResearch(payload.education_research);
      onResearchChange?.(payload.education_research);
      setState("completed");
    } catch (cause) {
      setState("error"); setError(cause instanceof Error ? cause.message : "education_research_failed");
    }
  }

  return <HoverDisclosure
    className="rounded-md border border-emerald-500/30 p-3"
    triggerClassName="font-medium"
    title="Education & Certification Research"
    collapsible={hasContent}
    contentClassName="space-y-3 pt-3"
    action={completed ? undefined : <Button type="button" variant="outline" onClick={startResearch} disabled={!enabled || busy}>
        {busy ? <span className="flex items-center gap-2"><ThinkingOrb state="working" size={20} theme="auto" aria-label="Education research in progress" />Researching…</span> : "Start"}
      </Button>}
  >
    {!enabled ? <p className="text-sm text-muted-foreground">No education entries available to research.</p> : null}
    {error ? <p className="text-sm text-destructive">{error}</p> : null}
    {automatic?.message ? <p className="text-sm text-destructive">{automatic.message}</p> : null}
    {visibleResearch ? <div className="space-y-3">{visibleResearch.credentials.map((credential) => <article key={`${credential.institution}:${credential.program ?? ""}`} className="rounded-md bg-muted/20 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><strong>{credential.institution}</strong><Badge variant="outline">{institutionStatus(credential.institution_exists)}</Badge><Badge variant="outline">{accreditationStatus(credential.accreditation_status)}</Badge><Badge variant="outline">{confidenceLabel(credential.confidence)}</Badge></div>
      <p className="mt-2 text-muted-foreground">{[credential.program, credential.degree, credential.certificate, credential.dates, credential.city, credential.country].filter(Boolean).join(" · ") || "Not enough public information."}</p>
      {credential.location_difference_for_review ? <p className="mt-2 rounded border border-amber-500/30 p-2 text-xs">For review: {credential.location_difference_for_review} This does not verify the candidate&apos;s location.</p> : null}
      <p className="mt-2 text-xs text-muted-foreground">{credential.uncertainty}</p>
      {credential.findings.map((finding, index) => <div key={`${finding.kind}-${index}`} className="mt-2 border-l-2 pl-2"><p>{finding.summary}</p></div>)}
      <div className="mt-3"><ResearchSources urls={credential.findings.flatMap((finding) => finding.source_urls)} /></div>
    </article>)}{visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? <HoverDisclosure className="text-xs text-muted-foreground" triggerClassName="w-fit flex-none" title="Searches and limitations" contentClassName="pt-2"><ul className="space-y-1">{visibleResearch.searches_performed.map((search) => <li key={search}>Search: {search}</li>)}{visibleResearch.search_limitations.map((limit) => <li key={limit}>Limit: {limit}</li>)}</ul></HoverDisclosure> : null}</div> : null}
  </HoverDisclosure>;
}
