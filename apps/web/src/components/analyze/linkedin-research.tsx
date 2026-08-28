"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink } from "lucide-react";
import type { AnalysisReport, LinkedInDiscovery } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { ResearchConfidenceBadge, sortByResearchConfidence } from "@/components/analyze/research-confidence-badge";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy } from "@/lib/app-settings";

type State = "idle" | "pending" | "error" | "timeout" | "completed";

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
        title={<span className="font-medium">{t("profile", { index: profileIndex + 1 })}</span>}
        action={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ResearchConfidenceBadge confidence={profile.confidence} />
          </div>
        }
        contentClassName="space-y-2 pt-3"
      >
        <div className="pb-1">
          <Button
            variant="outline"
            size="sm"
            render={
              <a href={profile.profile_url} target="_blank" rel="noreferrer">
                {t("openProfile")}
                <ExternalLink data-icon="inline-end" />
              </a>
            }
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {profile.photo_visible === "true" ? <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200">{t("photoVisible")}</Badge> : null}
          {profile.photo_visible === "false" ? <Badge variant="outline" className="border-rose-500/40 bg-rose-500/10 text-rose-800 dark:text-rose-200">{t("noPublicPhoto")}</Badge> : null}
          {profile.photo_visible === "unknown" ? <Badge variant="outline" className="border-muted-foreground/30 bg-muted text-muted-foreground">{t("photoUnknown")}</Badge> : null}
          {profile.connection_completeness_flag
            ? <Badge variant="outline" className="border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-200">{t("lowConnectionCount")}{profile.connection_count.display ? `: ${profile.connection_count.display}` : ""}</Badge>
            : profile.connection_count.display
              ? <Badge variant="outline" className="border-emerald-500/40 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200">{t("connections", { count: profile.connection_count.display })}</Badge>
              : <Badge variant="outline" className="border-muted-foreground/30 bg-muted text-muted-foreground">{t("connectionsUnknown")}</Badge>}
        </div>
        {note ? <p className="text-xs text-muted-foreground">{note}</p> : null}
        <ResearchSources
          urls={[
            profile.profile_url,
            ...profile.source_urls,
            profile.photo_source_url,
            profile.connection_count.source_url,
          ]}
        />
      </HoverDisclosure>
    </article>
  );
}

export function LinkedInResearchPanel({
  report,
  onDiscoveryChange,
}: {
  report: AnalysisReport;
  onDiscoveryChange?: (discovery: LinkedInDiscovery) => void;
}) {
  const { settings, t } = useCopy();
  const [discovery, setDiscovery] = useState<LinkedInDiscovery | undefined>(report.linkedin_discovery);
  const [discoveryState, setDiscoveryState] = useState<State>(discovery ? "completed" : "idle");
  const [error, setError] = useState<string | null>(null);
  const automatic = useAutoResearchState(report.analysis_id, "linkedin");
  const notifiedAutomatic = useRef<LinkedInDiscovery | null>(null);
  const onDiscoveryChangeRef = useRef(onDiscoveryChange);
  const enabled = report.ai_analysis.status === "succeeded" && report.ai_analysis.research_candidates.some((item) => item.category === "linkedin");
  const visibleDiscovery = discovery ?? automatic?.result as LinkedInDiscovery | undefined;
  const discoveryBusy = discoveryState === "pending" || automatic?.status === "pending" || automatic?.status === "running";
  const discoveryCompleted = discoveryState === "completed" || automatic?.status === "succeeded";
  const hasContent = Boolean(visibleDiscovery || error || automatic?.message);

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
  async function postDiscovery() {
    const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/research/linkedin/discovery`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token, aiEnabled: settings.aiEnabled }) });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw Object.assign(new Error(payload.detail ?? payload.error ?? "linkedin_research_failed"), { timeout: response.status === 504 });
    return payload;
  }

  async function discover() { setDiscoveryState("pending"); setError(null); try { const payload=await postDiscovery(); setDiscovery(payload.linkedin_discovery); onDiscoveryChange?.(payload.linkedin_discovery); setDiscoveryState("completed"); } catch (cause) { const timed=(cause as {timeout?:boolean}).timeout; setDiscoveryState(timed ? "timeout" : "error"); setError(timed ? t("researchTimedOut") : t("researchFailed")); } }

  return <HoverDisclosure
    className="rounded-md border p-3"
    title={<span className="font-medium">{t("linkedinProfiles")}</span>}
    collapsible={hasContent}
    contentClassName="space-y-3 pt-3"
    action={discoveryCompleted ? undefined : <ResearchAction
      busy={discoveryBusy}
      disabled={!enabled || discoveryBusy}
      onClick={discover}
      label={t("startDiscovery")}
      busyLabel={t("discovering")}
      busyAriaLabel={t("linkedinDiscoveryInProgress")}
      disabledReason={!enabled ? t("noCandidateDetails") : undefined}
    />}
  >
    {error ? <p className="text-sm text-destructive">{error}</p> : null}{automatic?.message ? <p className="text-sm text-destructive">{automatic.status === "manual-action" ? t("automaticResearchAlreadyAttempted") : t("automaticResearchFailed")}</p> : null}
    {visibleDiscovery?.linkedin_not_found ? <div className="rounded border border-amber-500/30 p-2 text-sm"><Badge variant="outline">{t("noProfileFound")}</Badge><p className="mt-2">{visibleDiscovery.not_found_caveat}</p></div> : null}
    {visibleDiscovery?.outcome === "ambiguous" ? <Badge variant="outline">{t("severalPossibleMatches")}</Badge> : null}
    <div className="space-y-2">
      {sortByResearchConfidence(visibleDiscovery?.possible_profiles ?? []).map((profile, profileIndex) => (
        <LinkedInProfileCard
          key={profile.profile_url}
          profile={profile}
          profileIndex={profileIndex}
        />
      ))}
    </div>
    {visibleDiscovery && (visibleDiscovery.searches_performed.length || visibleDiscovery.search_limitations.length) ? <HoverDisclosure className="text-xs text-muted-foreground" triggerClassName="w-fit flex-none" title={t("searchesAndLimitations")} contentClassName="space-y-1 pt-2">{visibleDiscovery.searches_performed.map(x=><p key={x}>{t("search")}: {x}</p>)}{visibleDiscovery.search_limitations.map(x=><p key={x}>{t("limit")}: {x}</p>)}</HoverDisclosure> : null}
  </HoverDisclosure>;
}
