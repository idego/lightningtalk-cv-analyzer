"use client";

import { useEffect, useRef } from "react";
import type { AnalysisReport, EducationResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { getAutoResearchOrchestrator } from "@/lib/auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { ResearchConfidenceBadge, sortByResearchConfidence } from "@/components/analyze/research-confidence-badge";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy, type CopyKey } from "@/lib/app-settings";
import { researchEligibility } from "@/lib/auto-research";

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

export function EducationResearchPanel({
  report,
  onResearchChange,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: EducationResearch) => void;
}) {
  const { settings, t } = useCopy();
  const automatic = useAutoResearchState(report.analysis_id, "education");
  const notifiedAutomatic = useRef<EducationResearch | null>(null);
  const onResearchChangeRef = useRef(onResearchChange);
  const enabled = settings.aiEnabled && researchEligibility(report).education;
  const visibleResearch = report.education_research ?? automatic?.result as EducationResearch | undefined;
  const busy = automatic?.status === "pending" || automatic?.status === "running";
  const completed = Boolean(report.education_research) || automatic?.status === "succeeded";
  const hasContent = Boolean(visibleResearch || automatic?.message);
  const automaticMessage = automatic?.status === "manual-action"
    ? t("automaticResearchAlreadyAttempted")
    : automatic?.status === "failed"
      ? t(automatic.httpStatus === 504 ? "researchTimedOut" : "automaticResearchFailed")
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
    await getAutoResearchOrchestrator()?.runManual(report, settings, "education");
  }

  return <HoverDisclosure
    className="rounded-md border p-3"
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
    {automaticMessage ? <p className="text-sm text-destructive">{automaticMessage}</p> : null}
    {visibleResearch?.cache?.status === "hit" ? (
      <p className="text-xs text-muted-foreground">
        {settings.uiLanguage === "pl" ? "Użyto wyniku z cache." : "Reused a cached research result."}
      </p>
    ) : null}
    {visibleResearch ? <div className="space-y-2">{sortByResearchConfidence(visibleResearch.credentials).map((credential) => <HoverDisclosure
      key={`${credential.institution}:${credential.program ?? ""}`}
      className="rounded-md border bg-muted/20 p-3 text-sm"
      allowHover
      title={<div className="flex min-w-0 flex-wrap items-center gap-2"><strong>{credential.institution}</strong><Badge variant="outline">{t(institutionStatusKey(credential.institution_exists))}</Badge><Badge variant="outline">{t(accreditationStatusKey(credential.accreditation_status))}</Badge></div>}
      action={<ResearchConfidenceBadge confidence={credential.confidence} />}
      contentClassName="space-y-2 pt-3"
    >
      <p className="text-muted-foreground">{[credential.program, credential.degree, credential.certificate, credential.dates, credential.city, credential.country].filter(Boolean).join(" · ") || t("notEnoughPublicInformation")}</p>
      {credential.location_difference_for_review ? <p className="rounded border border-amber-500/30 p-2 text-xs">{t("forReview")} {credential.location_difference_for_review} {t("doesNotVerifyCandidateLocation")}</p> : null}
      <p className="text-xs text-muted-foreground">{credential.uncertainty}</p>
      {credential.findings.map((finding, index) => <p key={`${finding.kind}-${index}`}>{finding.summary}</p>)}
      <ResearchSources urls={credential.findings.flatMap((finding) => finding.source_urls)} />
    </HoverDisclosure>)}{visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? <HoverDisclosure className="pt-2 text-xs text-muted-foreground" triggerClassName="w-fit flex-none font-medium text-foreground" title={t("searchesAndLimitations")} contentClassName="pt-2"><ul className="space-y-1">{visibleResearch.searches_performed.map((search) => <li key={search}>{t("search")}: {search}</li>)}{visibleResearch.search_limitations.map((limit) => <li key={limit}>{t("limit")}: {limit}</li>)}</ul></HoverDisclosure> : null}</div> : null}
  </HoverDisclosure>;
}
