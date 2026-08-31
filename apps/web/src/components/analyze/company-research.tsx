"use client";

import { useEffect, useRef } from "react";
import type { AnalysisReport, CompanyResearch } from "@/lib/analyze-types";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { getAutoResearchOrchestrator } from "@/lib/auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { ResearchConfidenceBadge, sortByResearchConfidence } from "@/components/analyze/research-confidence-badge";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy } from "@/lib/app-settings";
import { researchEligibility } from "@/lib/understanding-selectors";
import { isSelfEmploymentLabel } from "@/lib/relationship-labels";
import { GoogleSearchAction } from "@/components/analyze/google-search-action";
import { companyGoogleSearchUrl } from "@/lib/google-search";

function isResearchableCompany(value: string) {
  const normalized = value.toLocaleLowerCase().replace(/[^a-z]+/g, " ").trim();
  return !isSelfEmploymentLabel(normalized);
}

export function CompanyResearchPanel({
  report,
  onResearchChange,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: CompanyResearch) => void;
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
      title={t("companyResearch")}
      collapsible={hasContent}
      contentClassName="space-y-3 pt-3"
      action={completed ? undefined : (
        <ResearchAction
          busy={busy}
          disabled={!enabled || busy}
          onClick={startResearch}
          label={t("start")}
          busyLabel={t("researching")}
          busyAriaLabel={t("companyResearchInProgress")}
          disabledReason={!enabled ? t("noCompaniesAvailable") : undefined}
        />
      )}
    >
      {automaticMessage ? <p className="text-sm text-destructive">{automaticMessage}</p> : null}

      {visibleResearch ? (
        <div className="space-y-2">
          {sortByResearchConfidence(visibleResearch.organizations.filter((organization) => isResearchableCompany(organization.query_subject))).map((organization) => (
            <CompanyResult key={organization.query_subject} organization={organization} />
          ))}
          {visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? (
            <HoverDisclosure
              className="pt-2 text-xs text-muted-foreground"
              triggerClassName="w-fit flex-none font-medium text-foreground"
              title={t("searchDetails")}
              contentClassName="pt-2"
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
  const searchHref = companyGoogleSearchUrl({ organization: organization.query_subject, location: organization.location });
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
          {searchHref ? <GoogleSearchAction href={searchHref} subject={organization.query_subject} variant="labeled" /> : null}
        </div>
      }
      contentClassName="pt-3"
    >
      <div className="space-y-3">
        <dl className="divide-y rounded-md border">
          <FactRow
            label={t("reportedOfficeOrLocation")}
            value={organization.location ?? t("notConfirmed")}
          />
          <FactRow
            label={t("officialWebsite")}
            value={organization.official_website ? t("found") : t("notConfirmed")}
          />
          {organization.activity ? <FactRow label={t("activity")} value={organization.activity} /> : null}
          {organization.operating_dates ? <FactRow label={t("operatingDates")} value={organization.operating_dates} /> : null}
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

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid gap-1 px-3 py-2 sm:grid-cols-[12rem_1fr]">
      <dt className="text-muted-foreground">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
