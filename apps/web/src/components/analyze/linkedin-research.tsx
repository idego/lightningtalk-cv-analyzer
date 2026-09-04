"use client";

import { useEffect, useRef } from "react";
import type { AnalysisReport, LinkedInDiscovery } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { getAutoResearchOrchestrator } from "@/lib/auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { ResearchConfidenceBadge, sortByResearchConfidence } from "@/components/analyze/research-confidence-badge";
import { SectionTitle } from "@/components/analyze/section-title";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy } from "@/lib/app-settings";
import { researchEligibility } from "@/lib/auto-research";
import { FeedbackControl } from "@/components/analyze/feedback-control";
import { feedbackTarget, type FeedbackManifest } from "@/lib/feedback-types";
import { linkedinPeopleKeyword, linkedinPeopleSearchUrl } from "@/lib/google-search";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { LinkedInIcon, ProviderActionIcon } from "@/components/analyze/search-provider-icon";

type LinkedInProfile = LinkedInDiscovery["possible_profiles"][number];

function profileNote(uncertainty: string) {
  return uncertainty
    .split(/(?<=[.!?])\s+/)
    .filter((sentence) => !/compar/i.test(sentence))
    .join(" ")
    .trim();
}

function LinkedInProfileCard({
  profile,
  profileIndex,
}: {
  profile: LinkedInProfile;
  profileIndex: number;
}) {
  const { t } = useCopy();
  const note = profileNote(profile.uncertainty);
  return (
    <article>
      <HoverDisclosure
        className="rounded-md border bg-muted/20 p-3 text-sm"
        allowHover
        feedbackSnapshotLabel={t("profile", { index: profileIndex + 1 })}
        title={<span className="font-medium">{t("profile", { index: profileIndex + 1 })}</span>}
        action={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ResearchConfidenceBadge confidence={profile.confidence} />
            <Tooltip>
              <TooltipTrigger
                render={
                  <Button
                    variant="outline"
                    size="icon-sm"
                    className="active:scale-[0.92]"
                    nativeButton={false}
                    render={
                      <a
                        href={profile.profile_url}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={t("openProfile")}
                      >
                        <ProviderActionIcon provider="linkedin" defaultIcon="external-link" />
                      </a>
                    }
                  />
                }
              />
              <TooltipContent>{t("openProfile")}</TooltipContent>
            </Tooltip>
          </div>
        }
        contentClassName="space-y-2 pt-3"
      >
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
        <ResearchSources
          urls={[
            profile.profile_url,
            ...profile.source_urls,
          ]}
        />
      </HoverDisclosure>
    </article>
  );
}

export function LinkedInResearchPanel({
  report,
  onDiscoveryChange,
  feedbackManifest,
  readOnly = false,
}: {
  report: AnalysisReport;
  onDiscoveryChange?: (discovery: LinkedInDiscovery) => void;
  feedbackManifest?: FeedbackManifest;
  readOnly?: boolean;
}) {
  const { settings, t } = useCopy();
  const automatic = useAutoResearchState(report.analysis_id, "linkedin");
  const notifiedAutomatic = useRef<LinkedInDiscovery | null>(null);
  const onDiscoveryChangeRef = useRef(onDiscoveryChange);
  const enabled = settings.aiEnabled && researchEligibility(report).linkedin;
  const visibleDiscovery = report.linkedin_discovery ?? automatic?.result as LinkedInDiscovery | undefined;
  const discoveryBusy = automatic?.status === "pending" || automatic?.status === "running";
  const discoveryCompleted = Boolean(report.linkedin_discovery) || automatic?.status === "succeeded";
  const hasContent = Boolean(visibleDiscovery || automatic?.message);
  const searchKeyword = linkedinSearchKeyword(report);
  const searchHref = linkedinPeopleSearchUrl(searchKeyword);

  useEffect(() => {
    onDiscoveryChangeRef.current = onDiscoveryChange;
  }, [onDiscoveryChange]);

  useEffect(() => {
    const result = automatic?.status === "succeeded"
      ? automatic.result as LinkedInDiscovery | undefined
      : undefined;
    if (!result || notifiedAutomatic.current === result) return;
    notifiedAutomatic.current = result;
    onDiscoveryChangeRef.current?.(result);
  }, [automatic?.result, automatic?.status]);
  async function discover() {
    await getAutoResearchOrchestrator()?.runManual(report, settings, "linkedin");
  }

  return <HoverDisclosure
    className="rounded-md border p-3"
    title={<SectionTitle className="font-medium" icon={<LinkedInIcon className="size-4" />}>{t("linkedinProfiles")}</SectionTitle>}
    collapsible={hasContent}
    defaultOpen={readOnly}
    feedbackSnapshotLabel={t("linkedinProfiles")}
    contentClassName="space-y-3 pt-3"
    action={<div className="flex items-center gap-2">
      {searchHref ? <Tooltip><TooltipTrigger render={<Button variant="outline" size="icon-sm" className="active:scale-[0.92]" nativeButton={false} render={<a href={searchHref} target="_blank" rel="noreferrer" aria-label={t("searchLinkedIn")}><ProviderActionIcon provider="linkedin" /></a>} />} /><TooltipContent>{t("searchLinkedIn")}</TooltipContent></Tooltip> : null}
      {!readOnly && !discoveryCompleted ? <ResearchAction
        busy={discoveryBusy}
        disabled={!enabled || discoveryBusy}
        onClick={discover}
        label={t("start")}
        busyLabel={t("discovering")}
        busyAriaLabel={t("linkedinDiscoveryInProgress")}
        disabledReason={!enabled ? t("noCandidateDetails") : undefined}
      /> : null}
      {!readOnly && hasContent && feedbackTarget(feedbackManifest, "linkedin_research_result", "linkedin_discovery", "section") ? <FeedbackControl analysisId={report.analysis_id} report={report} target={feedbackTarget(feedbackManifest, "linkedin_research_result", "linkedin_discovery", "section")!} /> : null}
    </div>}
  >
    {automatic?.message ? <p className="text-sm text-destructive">{automatic.status === "manual-action" ? t("automaticResearchAlreadyAttempted") : t(automatic.httpStatus === 504 ? "researchTimedOut" : "automaticResearchFailed")}</p> : null}
    {visibleDiscovery?.linkedin_not_found ? <div className="rounded border border-amber-500/30 p-2 text-sm"><Badge variant="outline">{t("noProfileFound")}</Badge><p className="mt-2">{visibleDiscovery.not_found_caveat}</p></div> : null}
    <div className="space-y-2">
      {sortByResearchConfidence(visibleDiscovery?.possible_profiles ?? []).map((profile, profileIndex) => (
        <LinkedInProfileCard
          key={profile.profile_url}
          profile={profile}
          profileIndex={profileIndex}
        />
      ))}
    </div>
    {visibleDiscovery && (visibleDiscovery.searches_performed.length || visibleDiscovery.search_limitations.length) ? <HoverDisclosure className="ml-2 text-xs text-muted-foreground" triggerClassName="w-fit flex-none" title={t("searchesAndLimitations")} contentClassName="space-y-1 pl-3 pt-2">{visibleDiscovery.searches_performed.map(x=><p key={x}>{t("search")}: {x}</p>)}{visibleDiscovery.search_limitations.map(x=><p key={x}>{t("limit")}: {x}</p>)}</HoverDisclosure> : null}
  </HoverDisclosure>;
}

function fieldValue(field: { value?: string } | null | undefined): string | null {
  return typeof field?.value === "string" && field.value.trim() ? field.value.trim() : null;
}

export function linkedinSearchKeyword(report: AnalysisReport): string | null {
  const name = fieldValue(report.base_analysis.profile.candidate_name);
  const employment = report.base_analysis.employment.find((record) => record.status === "accepted");
  return linkedinPeopleKeyword({ candidateName: name, organization: fieldValue(employment?.organization) });
}
