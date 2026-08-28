"use client";

import { useEffect, useRef, useState } from "react";
import type { AnalysisReport, CompanyResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { ResearchAction } from "@/components/analyze/research-action";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { useCopy } from "@/lib/app-settings";

export function CompanyResearchPanel({
  report,
  onResearchChange,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: CompanyResearch) => void;
}) {
  const { settings, t } = useCopy();
  const [research, setResearch] = useState<CompanyResearch | undefined>(report.company_research);
  const [state, setState] = useState<"idle" | "pending" | "error" | "timeout" | "completed">(
    report.company_research ? "completed" : "idle",
  );
  const [error, setError] = useState<string | null>(null);
  const automatic = useAutoResearchState(report.analysis_id, "company");
  const notifiedAutomatic = useRef<CompanyResearch | null>(null);
  const onResearchChangeRef = useRef(onResearchChange);
  const candidates = report.ai_analysis.research_candidates.filter(
    (candidate) => candidate.category === "company",
  );
  const enabled = report.ai_analysis.status === "succeeded" && candidates.length > 0;
  const visibleResearch = research ?? automatic?.result as CompanyResearch | undefined;
  const busy = state === "pending" || automatic?.status === "pending" || automatic?.status === "running";
  const completed = state === "completed" || automatic?.status === "succeeded";
  const hasContent = Boolean(visibleResearch || error || automatic?.message);
  const automaticMessage = automatic?.status === "manual-action"
    ? t("automaticResearchAlreadyAttempted")
    : automatic?.status === "failed"
      ? t("automaticResearchFailed")
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
    setState("pending");
    setError(null);
    try {
      const response = await fetch(
        `/api/analyses/${encodeURIComponent(report.analysis_id)}/research/company`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token, aiEnabled: settings.aiEnabled }) },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail ?? payload.error ?? "company_research_failed";
        if (response.status === 504 || detail === "company_research_timeout") {
          setState("timeout");
          setError(t("researchTimedOut"));
          return;
        }
        throw new Error(detail);
      }
      setResearch(payload.company_research);
      onResearchChange?.(payload.company_research);
      setState("completed");
    } catch {
      setState("error");
      setError(t("researchFailed"));
    }
  }

  return (
    <HoverDisclosure
      className="rounded-md border border-violet-500/30 p-3"
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
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {automaticMessage ? <p className="text-sm text-destructive">{automaticMessage}</p> : null}

      {visibleResearch ? (
        <div className="divide-y">
          {visibleResearch.organizations.map((organization) => (
            <CompanyResult key={organization.query_subject} organization={organization} />
          ))}
          {visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? (
            <HoverDisclosure
              className="py-3 text-xs text-muted-foreground"
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
      className="py-3 text-sm"
      title={
        <div className="min-w-0">
          <strong className="block truncate">{organization.query_subject}</strong>
          <span className="text-xs text-muted-foreground">{existence}</span>
        </div>
      }
      action={
        <div className="flex shrink-0 items-center gap-2">
          <Badge variant="outline">{t("confidenceWithValue", { value: t(`confidence${organization.confidence[0].toUpperCase()}${organization.confidence.slice(1)}` as "confidenceHigh" | "confidenceMedium" | "confidenceLow") })}</Badge>
        </div>
      }
      contentClassName="pt-3"
    >
      <div className="space-y-3 pl-0 sm:pl-2">
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
