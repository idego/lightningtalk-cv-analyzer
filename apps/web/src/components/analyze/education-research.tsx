"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalysisReport, EducationResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy, type CopyKey } from "@/lib/app-settings";

function institutionStatusKey(status: string): CopyKey {
  return ({
    supported: "institutionConfirmed",
    mismatch: "institutionMismatch",
    evidence_unavailable: "institutionNotConfirmed",
  }[status] ?? "institutionNotConfirmed") as CopyKey;
}

function accreditationStatusKey(status: string | null): CopyKey {
  if (status === "established") return "accreditationConfirmed";
  if (status === "not_established") return "accreditationNotConfirmed";
  return "accreditationUnknown";
}

function confidenceKey(confidence: string): CopyKey {
  if (confidence === "high") return "confidenceHigh";
  if (confidence === "medium") return "confidenceMedium";
  return "confidenceLow";
}

export function EducationResearchPanel({
  report,
  onResearchChange,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: EducationResearch) => void;
}) {
  const { settings, t } = useCopy();
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
  const hasContent = Boolean(visibleResearch || error || automatic?.message);
  const automaticMessage = automatic?.status === "manual-action"
    ? t("automaticResearchAlreadyAttempted")
    : automatic?.message
      ? t("automaticResearchFailed")
      : null;

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
      const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/education`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token, aiEnabled: settings.aiEnabled }) });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail ?? payload.error ?? "education_research_failed";
        if (response.status === 504 || detail === "education_research_timeout") {
          setState("timeout"); setError(t("researchTimedOut")); return;
        }
        throw new Error(detail);
      }
      setResearch(payload.education_research);
      onResearchChange?.(payload.education_research);
      setState("completed");
    } catch {
      setState("error"); setError(t("researchFailed"));
    }
  }

  return <HoverDisclosure
    className="rounded-md border border-emerald-500/30 p-3"
    triggerClassName="font-medium"
    title={t("educationResearch")}
    collapsible={hasContent}
    contentClassName="space-y-3 pt-3"
    action={completed ? undefined : <ResearchAction
      busy={busy}
      disabled={!enabled || busy}
      onClick={startResearch}
      label={t("start")}
      busyLabel={t("researching")}
      busyAriaLabel={t("educationResearchInProgress")}
      disabledReason={!enabled ? t("noEducationEntries") : undefined}
    />}
  >
    {error ? <p className="text-sm text-destructive">{error}</p> : null}
    {automaticMessage ? <p className="text-sm text-destructive">{automaticMessage}</p> : null}
    {visibleResearch ? <div className="space-y-3">{visibleResearch.credentials.map((credential) => <article key={`${credential.institution}:${credential.program ?? ""}`} className="rounded-md bg-muted/20 p-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><strong>{credential.institution}</strong><Badge variant="outline">{t(institutionStatusKey(credential.institution_exists))}</Badge><Badge variant="outline">{t(accreditationStatusKey(credential.accreditation_status))}</Badge><Badge variant="outline">{t("confidenceWithValue", { value: t(confidenceKey(credential.confidence)) })}</Badge></div>
      <p className="mt-2 text-muted-foreground">{[credential.program, credential.degree, credential.certificate, credential.dates, credential.city, credential.country].filter(Boolean).join(" · ") || t("notEnoughPublicInformation")}</p>
      {credential.location_difference_for_review ? <p className="mt-2 rounded border border-amber-500/30 p-2 text-xs">{t("forReview")} {credential.location_difference_for_review} {t("doesNotVerifyCandidateLocation")}</p> : null}
      <p className="mt-2 text-xs text-muted-foreground">{credential.uncertainty}</p>
      {credential.findings.map((finding, index) => <div key={`${finding.kind}-${index}`} className="mt-2 border-l-2 pl-2"><p>{finding.summary}</p></div>)}
      <div className="mt-3"><ResearchSources urls={credential.findings.flatMap((finding) => finding.source_urls)} /></div>
    </article>)}{visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? <HoverDisclosure className="text-xs text-muted-foreground" triggerClassName="w-fit flex-none" title={t("searchesAndLimitations")} contentClassName="pt-2"><ul className="space-y-1">{visibleResearch.searches_performed.map((search) => <li key={search}>{t("search")}: {search}</li>)}{visibleResearch.search_limitations.map((limit) => <li key={limit}>{t("limit")}: {limit}</li>)}</ul></HoverDisclosure> : null}</div> : null}
  </HoverDisclosure>;
}
