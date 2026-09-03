"use client";

import { useEffect, useRef } from "react";
import { GraduationCap } from "lucide-react";
import type { AnalysisReport, EducationResearch } from "@/lib/analyze-types";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { getAutoResearchOrchestrator } from "@/lib/auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { ResearchCacheProvenanceView } from "@/components/analyze/research-cache-provenance";
import { ResearchConfidenceBadge, sortByResearchConfidence } from "@/components/analyze/research-confidence-badge";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy } from "@/lib/app-settings";
import { researchEligibility } from "@/lib/auto-research";
import { GoogleSearchAction } from "@/components/analyze/google-search-action";
import { educationGoogleSearchUrl } from "@/lib/google-search";
import { FeedbackControl } from "@/components/analyze/feedback-control";
import { feedbackTarget, type FeedbackManifest } from "@/lib/feedback-types";

type Credential = EducationResearch["credentials"][number];

function EducationResult({ credential }: { credential: Credential }) {
  const { t } = useCopy();
  const searchHref = educationGoogleSearchUrl({
    institution: credential.institution,
    program: credential.program,
  });
  const details = [credential.degree, credential.dates, credential.city, credential.country].filter(Boolean).join(" · ");

  return <HoverDisclosure
    className="rounded-md border bg-muted/20 p-3 text-sm"
    allowHover
    feedbackSnapshotLabel={credential.institution ?? t("educationResearch")}
    headerClassName="flex-wrap sm:flex-nowrap"
    actionClassName="w-full sm:w-auto"
    title={<div className="flex min-w-0 items-baseline gap-2"><strong className="min-w-0 truncate">{credential.institution}</strong>{credential.program ? <span className="min-w-0 truncate text-xs font-normal text-muted-foreground">{credential.program}</span> : null}</div>}
    action={<div className="flex flex-wrap items-center gap-2 sm:justify-end"><ResearchConfidenceBadge confidence={credential.confidence} />{searchHref ? <GoogleSearchAction href={searchHref} /> : null}</div>}
    contentClassName="space-y-2 pt-3"
  >
    {details ? <p className="text-muted-foreground">{details}</p> : null}
    {credential.location_difference_for_review ? <p className="rounded border border-amber-500/30 p-2 text-xs">{t("forReview")} {credential.location_difference_for_review} {t("doesNotVerifyCandidateLocation")}</p> : null}
    <p className="text-xs text-muted-foreground">{credential.uncertainty}</p>
    {credential.findings.map((finding, index) => <p key={`${finding.kind}-${index}`}>{finding.summary}</p>)}
    <ResearchSources urls={credential.findings.flatMap((finding) => finding.source_urls)} />
  </HoverDisclosure>;
}

export function EducationResearchPanel({
  report,
  onResearchChange,
  feedbackManifest,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: EducationResearch) => void;
  feedbackManifest?: FeedbackManifest;
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
    title={<span className="flex items-center gap-2 font-medium"><GraduationCap className="size-4 text-muted-foreground" aria-hidden />{t("educationResearch")}</span>}
    collapsible={hasContent}
    contentClassName="space-y-3 pt-3"
    feedbackSnapshotLabel={t("educationResearch")}
    action={<div className="flex items-center gap-2">
      {!completed ? <ResearchAction
        busy={busy}
        disabled={!enabled || busy}
        onClick={startResearch}
        label={t("start")}
        busyLabel={t("researching")}
        busyAriaLabel={t("educationResearchInProgress")}
        disabledReason={!enabled ? t("noEducationEntries") : undefined}
      /> : null}
      {hasContent && feedbackTarget(feedbackManifest, "education_research_result", "education_research", "section") ? <FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(feedbackManifest, "education_research_result", "education_research", "section")!} /> : null}
    </div>}
  >
    {automaticMessage ? <p className="text-sm text-destructive">{automaticMessage}</p> : null}
    <ResearchCacheProvenanceView cache={visibleResearch?.cache} locale={settings.uiLanguage} />
    {visibleResearch ? <div className="space-y-2">{sortByResearchConfidence(visibleResearch.credentials).map((credential) => <EducationResult key={`${credential.institution}:${credential.program ?? ""}`} credential={credential} />)}{visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? <HoverDisclosure className="ml-2 pt-2 text-xs text-muted-foreground" triggerClassName="w-fit flex-none font-medium text-foreground" title={t("searchesAndLimitations")} contentClassName="pl-3 pt-2"><ul className="space-y-1">{visibleResearch.searches_performed.map((search) => <li key={search}>{t("search")}: {search}</li>)}{visibleResearch.search_limitations.map((limit) => <li key={limit}>{t("limit")}: {limit}</li>)}</ul></HoverDisclosure> : null}</div> : null}
  </HoverDisclosure>;
}
