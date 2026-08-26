"use client";

import { useEffect, useRef, useState } from "react";
import { ThinkingOrb } from "thinking-orbs";
import type { AnalysisReport, CompanyResearch } from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAutoResearchState } from "@/lib/use-auto-research";
import { ResearchSources } from "@/components/analyze/research-sources";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

export function CompanyResearchPanel({
  report,
  onResearchChange,
}: {
  report: AnalysisReport;
  onResearchChange?: (research: CompanyResearch) => void;
}) {
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
  const hasContent = Boolean(visibleResearch || error || automatic?.message || !enabled);

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
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accessToken: report.analysis_access_token }) },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        const detail = payload.detail ?? payload.error ?? "company_research_failed";
        if (response.status === 504 || detail === "company_research_timeout") {
          setState("timeout");
          setError("Research timed out. You can safely try again.");
          return;
        }
        throw new Error(detail);
      }
      setResearch(payload.company_research);
      onResearchChange?.(payload.company_research);
      setState("completed");
    } catch (cause) {
      setState("error");
      setError(cause instanceof Error ? cause.message : "company_research_failed");
    }
  }

  return (
    <HoverDisclosure
      className="rounded-md border border-violet-500/30 p-3"
      triggerClassName="font-medium"
      title="Company research"
      collapsible={hasContent}
      contentClassName="space-y-3 pt-3"
      action={completed ? undefined : (
        <Button
            type="button"
            variant="outline"
            onClick={startResearch}
            disabled={!enabled || busy}
          >
            {busy ? (
            <span className="flex items-center gap-2">
              <ThinkingOrb state="working" size={20} theme="auto" aria-label="Company research in progress" />
              Researching…
            </span>
            ) : "Start"}
          </Button>
      )}
    >

      {!enabled ? (
        <p className="text-sm text-muted-foreground">
          No companies available to research.
        </p>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      {automatic?.message ? <p className="text-sm text-destructive">{automatic.message}</p> : null}

      {visibleResearch ? (
        <div className="divide-y">
          {visibleResearch.organizations.map((organization) => (
            <CompanyResult key={organization.query_subject} organization={organization} />
          ))}
          {visibleResearch.searches_performed.length || visibleResearch.search_limitations.length ? (
            <HoverDisclosure
              className="py-3 text-xs text-muted-foreground"
              triggerClassName="w-fit flex-none font-medium text-foreground"
              title="Search details"
              contentClassName="pt-2"
            >
              <ul className="space-y-1">
                {visibleResearch.searches_performed.map((search) => <li key={search}>Search: {search}</li>)}
                {visibleResearch.search_limitations.map((limit) => <li key={limit}>Limit: {limit}</li>)}
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
  const sources = Array.from(new Set([
    ...(organization.official_website ? [organization.official_website] : []),
    ...organization.company_pages,
    ...organization.registries,
    ...organization.findings.flatMap((finding) => finding.source_urls),
  ]));
  const existence = {
    supported: "Company found",
    conflicting: "Conflicting company information",
    insufficient_evidence: "Company not confirmed",
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
          <Badge variant="outline">{organization.confidence} confidence</Badge>
        </div>
      }
      contentClassName="pt-3"
    >
      <div className="space-y-3 pl-0 sm:pl-2">
        <dl className="divide-y rounded-md border">
          <FactRow
            label="Reported office or location"
            value={organization.location ?? "Not confirmed"}
          />
          <FactRow
            label="Official website"
            value={organization.official_website ? "Found" : "Not confirmed"}
          />
          {organization.activity ? <FactRow label="Activity" value={organization.activity} /> : null}
          {organization.operating_dates ? <FactRow label="Operating dates" value={organization.operating_dates} /> : null}
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
