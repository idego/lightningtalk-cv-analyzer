"use client";

import { type ReactNode, useEffect, useRef } from "react";
import { BriefcaseBusiness, Building2, CalendarDays, ExternalLink, Globe2, MapPin } from "lucide-react";
import type { AnalysisReport, CompanyResearch } from "@/lib/analyze-types";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { getAutoResearchOrchestrator } from "@/lib/auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { ResearchCacheProvenanceView } from "@/components/analyze/research-cache-provenance";
import { ResearchConfidenceBadge, sortByResearchConfidence } from "@/components/analyze/research-confidence-badge";
import { SectionTitle } from "@/components/analyze/section-title";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy } from "@/lib/app-settings";
import { researchEligibility } from "@/lib/auto-research";
import { isSelfEmploymentLabel } from "@/lib/relationship-labels";
import { GoogleSearchAction } from "@/components/analyze/google-search-action";
import { companyGoogleSearchUrl } from "@/lib/google-search";
import { FeedbackControl } from "@/components/analyze/feedback-control";
import { feedbackTarget, type FeedbackManifest } from "@/lib/feedback-types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function isResearchableCompany(value: string) {
  const normalized = value.toLocaleLowerCase().replace(/[^a-z]+/g, " ").trim();
  return !isSelfEmploymentLabel(normalized);
}

export function CompanyResearchPanel({
  report,
  onResearchChange,
  feedbackManifest,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: CompanyResearch) => void;
  feedbackManifest?: FeedbackManifest;
}) {
  const { settings, t } = useCopy();
  const automatic = useAutoResearchState(report.analysis_id, "company");
  const notifiedAutomatic = useRef<CompanyResearch | null>(null);
  const onResearchChangeRef = useRef(onResearchChange);
  const enabled = settings.aiEnabled && researchEligibility(report).company;
  const visibleResearch = report.company_research ?? automatic?.result as CompanyResearch | undefined;
  const busy = automatic?.status === "pending" || automatic?.status === "running";
  const completed = Boolean(report.company_research) || automatic?.status === "succeeded";
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
      ? automatic.result as CompanyResearch | undefined
      : undefined;
    if (!result || notifiedAutomatic.current === result) return;
    notifiedAutomatic.current = result;
    onResearchChangeRef.current?.(result);
  }, [automatic?.result, automatic?.status]);

  async function startResearch() {
    await getAutoResearchOrchestrator()?.runManual(report, settings, "company");
  }

  return (
    <HoverDisclosure
      className="rounded-md border p-3"
      triggerClassName="font-medium"
      title={<SectionTitle className="font-medium" icon={<Building2 className="size-4" />}>{t("companyResearch")}</SectionTitle>}
      collapsible={hasContent}
      contentClassName="space-y-3 pt-3"
      feedbackSnapshotLabel={t("companyResearch")}
      action={<div className="flex items-center gap-2">
        {!completed ? <ResearchAction
            busy={busy}
            disabled={!enabled || busy}
            onClick={startResearch}
            label={t("start")}
            busyLabel={t("researching")}
            busyAriaLabel={t("companyResearchInProgress")}
            disabledReason={!enabled ? t("noCompaniesAvailable") : undefined}
          /> : null}
        {hasContent && feedbackTarget(feedbackManifest, "company_research_result", "company_research", "section") ? <FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(feedbackManifest, "company_research_result", "company_research", "section")!} /> : null}
      </div>}
    >
      {automaticMessage ? <p className="text-sm text-destructive">{automaticMessage}</p> : null}
      <ResearchCacheProvenanceView cache={visibleResearch?.cache} locale={settings.uiLanguage} />

      {visibleResearch ? (
        <div className="space-y-2">
          {sortByResearchConfidence(visibleResearch.organizations.filter((organization) => isResearchableCompany(organization.query_subject))).map((organization) => <CompanyResult key={organization.query_subject} organization={organization} />)}
          {visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? (
            <HoverDisclosure
              className="ml-2 pt-2 text-xs text-muted-foreground"
              triggerClassName="w-fit flex-none font-medium text-foreground"
              title={t("searchDetails")}
              contentClassName="pl-3 pt-2"
            >
              <ul className="space-y-1">
                {visibleResearch.searches_performed.map((search) => <li key={search}>{t("search")}: {search}</li>)}
                {visibleResearch.search_limitations.map((limit) => <li key={limit}>{t("limit")}: {limit}</li>)}
              </ul>
            </HoverDisclosure>
          ) : null}
        </div>
      ) : null}
    </HoverDisclosure>
  );
}

type Organization = CompanyResearch["organizations"][number];

function CompanyResult({ organization }: { organization: Organization }) {
  const { t } = useCopy();
  const offices = organization.offices ?? [];
  const operatingPeriods = organization.operating_periods ?? [];
  const searchHref = companyGoogleSearchUrl({ organization: organization.query_subject, location: offices[0]?.address });
  const sources = Array.from(new Set([
    ...(organization.official_website ? [organization.official_website] : []),
    ...organization.company_pages,
    ...organization.registries,
    ...organization.findings.flatMap((finding) => finding.source_urls),
  ]));
  const existence = {
    supported: t("companyFound"),
    conflicting: t("conflictingCompanyInformation"),
    insufficient_evidence: t("companyNotConfirmed"),
  }[organization.existence];

  return (
    <HoverDisclosure
      className="rounded-md border bg-muted/20 p-3 text-sm"
      allowHover
      feedbackSnapshotLabel={organization.query_subject}
      headerClassName="flex-wrap sm:flex-nowrap"
      actionClassName="w-full sm:w-auto"
      title={
        <div className="min-w-0">
          <strong className="block truncate">{organization.query_subject}</strong>
          <span className="text-xs text-muted-foreground">{existence}</span>
        </div>
      }
      action={
        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          <ResearchConfidenceBadge confidence={organization.confidence} />
          {searchHref ? <GoogleSearchAction href={searchHref} /> : null}
        </div>
      }
      contentClassName="pt-3"
    >
      <div className="space-y-3">
        <dl className="divide-y rounded-md border">
          <FactRow
            label={t("reportedOfficeOrLocation")}
            icon={<MapPin className="size-4" />}
            align={offices.length ? "start" : "center"}
            value={offices.length ? (
              <ul className="list-disc space-y-2 pl-4">
                {offices.map((office, index) => (
                  <li key={`${office.address}-${index}`}>
                    <ExternalFactLink href={`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(office.address)}`} value={office.address} />
                    {office.comment ? <p className="mt-0.5 text-xs text-muted-foreground">{office.comment}</p> : null}
                  </li>
                ))}
              </ul>
            ) : t("notConfirmed")}
          />
          <FactRow
            label={t("officialWebsite")}
            icon={<Globe2 className="size-4" />}
            align="center"
            value={organization.official_website ? <ExternalFactLink href={organization.official_website} value={organization.official_website} compact /> : t("notConfirmed")}
          />
          {organization.activity ? <FactRow label={t("activity")} icon={<BriefcaseBusiness className="size-4" />} value={organization.activity} /> : null}
          {operatingPeriods.length ? (
            <FactRow
              label={t("operatingDates")}
              icon={<CalendarDays className="size-4" />}
              value={
                <ul className="list-disc space-y-2 pl-4">
                  {operatingPeriods.map((period, index) => (
                    <li key={`${period.from}-${period.to}-${index}`}>
                      <span>{formatOperatingPeriod(period, t("present"), t("until"))}</span>
                      {period.comment ? <p className="mt-0.5 text-xs text-muted-foreground">{period.comment}</p> : null}
                    </li>
                  ))}
                </ul>
              }
            />
          ) : null}
        </dl>

        {organization.findings.length ? (
          <div className="space-y-2">
            {organization.findings.map((finding, index) => (
              <p key={`${finding.kind}-${index}`}>{finding.summary}</p>
            ))}
          </div>
        ) : null}

        {organization.limited_online_presence_reason ? (
          <p className="text-xs text-muted-foreground">{organization.limited_online_presence_reason}</p>
        ) : null}

        <ResearchSources urls={sources} />
      </div>
    </HoverDisclosure>
  );
}

function formatOperatingPeriod(period: Organization["operating_periods"][number], present: string, until: string) {
  if (period.from && period.ongoing) return `${period.from} – ${present}`;
  if (period.from && period.to) return `${period.from} – ${period.to}`;
  if (period.from) return period.from;
  return `${until} ${period.to}`;
}

function ExternalFactLink({ href, value, compact = false }: { href: string; value: string; compact?: boolean }) {
  return <a className={`inline-flex max-w-full items-center gap-1 break-words underline decoration-muted-foreground/50 underline-offset-2 [text-decoration-skip-ink:none] hover:text-foreground ${compact ? "leading-none" : ""}`} href={href} target="_blank" rel="noreferrer">{value}<ExternalLink className="size-3 shrink-0" aria-hidden /></a>;
}

function FactRow({ label, icon, value, align = "start" }: { label: string; icon: ReactNode; value: ReactNode; align?: "start" | "center" }) {
  return (
    <div className={`grid gap-1 px-3 py-2 sm:grid-cols-[2.25rem_1fr] ${align === "center" ? "items-center" : "items-start"}`}>
      <dt>
        <Tooltip>
          <TooltipTrigger
            render={
              <span
                tabIndex={0}
                aria-label={label}
                className="flex size-7 items-center justify-center rounded-md text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {icon}
              </span>
            }
          />
          <TooltipContent side="right">{label}</TooltipContent>
        </Tooltip>
      </dt>
      <dd>{value}</dd>
    </div>
  );
}
