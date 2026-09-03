"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { BriefcaseBusiness, CircleAlert, Globe2, GraduationCap, Map as MapIcon, MapPin, Phone, UserRound } from "lucide-react";
import type { AnalysisReport, AnalyzeItemResult } from "@/lib/analyze-types";
import type { ReportFinding, ReportOverview } from "@/lib/report-interface-adapter";
import { adaptReportInterface } from "@/lib/report-interface-adapter";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CompanyResearchPanel } from "@/components/analyze/company-research";
import { EducationResearchPanel } from "@/components/analyze/education-research";
import { LinkedInResearchPanel } from "@/components/analyze/linkedin-research";
import { useCopy } from "@/lib/app-settings";
import { GoogleSearchAction } from "@/components/analyze/google-search-action";
import { companyGoogleSearchUrl, educationGoogleSearchUrl } from "@/lib/google-search";
import { FeedbackControl } from "@/components/analyze/feedback-control";
import { feedbackTarget, type FeedbackManifest } from "@/lib/feedback-types";

function FlagList({ flags }: { flags: ReportFinding[] }) {
  const { t } = useCopy();
  return (
    <div className="space-y-2">
      {flags.map((flag) => (
        <HoverDisclosure
          key={flag.id}
          className="rounded-md border bg-muted/15 p-3 text-sm"
          allowHover
          feedbackSnapshotLabel={flag.whatWeFound}
          title={<span className="block font-medium leading-snug">{flag.whatWeFound}</span>}
          contentClassName="pt-3"
        >
          <dl className="space-y-3 border-t pt-3">
            <div><dt className="text-[0.65rem] font-semibold uppercase tracking-[0.09em] text-muted-foreground">{t("whyItMatters")}</dt><dd className="mt-1 leading-relaxed">{flag.whyItMatters}</dd></div>
            <div><dt className="text-[0.65rem] font-semibold uppercase tracking-[0.09em] text-muted-foreground">{t("whatToCheck")}</dt><dd className="mt-1 leading-relaxed">{flag.whatToCheck}</dd></div>
          </dl>
          {flag.evidence.length ? (
            <div className="mt-3 space-y-1 border-l-2 pl-2 text-xs text-muted-foreground">
              {flag.evidence.map((evidence, index) => (
                <p key={`${evidence.source_id}:${evidence.excerpt}`}>
                  {index === 0 ? `${t("evidence")}: ` : ""}„{evidence.excerpt}”
                </p>
              ))}
            </div>
          ) : null}
        </HoverDisclosure>
      ))}
    </div>
  );
}

function OverviewIcon({ label, tone, children }: { label: string; tone: string; children: ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            aria-label={label}
            className={`flex size-8 shrink-0 items-center justify-center rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-ring ${tone}`}
          >
            {children}
          </span>
        }
      />
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

function OverviewRow({
  icon,
  label,
  value,
  detail,
  tone,
  action,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail?: ReactNode;
  tone: string;
  action?: ReactNode;
}) {
  return (
    <div className={`flex min-w-0 gap-3 py-1.5 ${detail ? "items-start" : "items-center"}`}>
      <OverviewIcon label={label} tone={tone}>{icon}</OverviewIcon>
      <div className={`min-w-0 flex-1 ${detail ? "pt-0.5" : ""}`}>
        <p className="break-words text-sm font-medium leading-snug text-foreground">{value}</p>
        {detail ? <p className="mt-0.5 break-words text-xs leading-relaxed text-muted-foreground">{detail}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

function displayCountry(countryCode: string, language: "en" | "pl") {
  const code = countryCode.toUpperCase();
  const name = new Intl.DisplayNames([language], { type: "region" }).of(code);
  return name && name !== code ? `${name} (${code})` : code;
}

function joinDisplay(...values: Array<string | null | undefined>) {
  return values.filter(Boolean).join(" · ") || null;
}

function StructuredFacts({ overview, analysisId, feedbackManifest }: { overview: ReportOverview; analysisId: string; feedbackManifest?: FeedbackManifest }) {
  const { settings, t } = useCopy();
  const hasContact = Boolean(overview.candidateName || overview.phone);
  const hasLocation = Boolean(overview.statedLocation || overview.resolvedLocation || overview.postalCode || overview.postalCountry || overview.postalConsistency || overview.euStatus);
  const hasFacts = hasContact || hasLocation || overview.education.length > 0 || overview.employment.length > 0 || overview.attentionRecords.length > 0 || Boolean(overview.educationStatus || overview.employmentStatus);
  const reviewLabel = settings.uiLanguage === "pl" ? "Wymaga sprawdzenia" : "Needs review";
  const emptySection = (sectionStatus: string | undefined) => {
    if (sectionStatus === "not_present") return settings.uiLanguage === "pl" ? "Nie znaleziono wpisów w CV." : "No entries were found in the CV.";
    if (sectionStatus === "failed") return settings.uiLanguage === "pl" ? "Nie udało się przeanalizować tej sekcji." : "This section could not be analyzed.";
    return settings.uiLanguage === "pl" ? "Nie udało się jednoznacznie ustalić zawartości tej sekcji." : "This section could not be resolved confidently.";
  };
  const contactTone = "bg-sky-500/10 text-sky-700 dark:text-sky-300";
  const locationTone = "bg-violet-500/10 text-violet-700 dark:text-violet-300";
  const educationTone = "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  const employmentTone = "bg-amber-500/10 text-amber-800 dark:text-amber-200";

  return (
    <HoverDisclosure className="rounded-md border p-3" triggerClassName="text-sm font-medium" title={t("extracted")} feedbackSnapshotLabel={t("extracted")} action={feedbackTarget(feedbackManifest, "report_overall", "report", "overall") ? <FeedbackControl analysisId={analysisId} target={feedbackTarget(feedbackManifest, "report_overall", "report", "overall")!} /> : null} contentClassName="pt-4">
      {hasFacts ? (
        <div className="space-y-5">
          {overview.attentionRecords.length ? <section aria-labelledby="overview-attention" className="rounded border border-rose-500/30 bg-rose-500/5 p-3">
            <h4 id="overview-attention" className="mb-2 text-xs font-semibold text-foreground">{settings.uiLanguage === "pl" ? "Dane wymagające uwagi" : "Data needing attention"}</h4>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {overview.attentionRecords.map((item) => <OverviewRow key={item.id} icon={<CircleAlert className="size-4" />} label={reviewLabel} value={item.value} detail={item.detail} tone="bg-rose-500/10 text-rose-700 dark:text-rose-300" />)}
            </div>
          </section> : null}
          {hasContact || hasLocation ? <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
            {hasContact ? <section aria-labelledby="overview-contact">
              <h4 id="overview-contact" className="mb-2 text-xs font-semibold text-foreground">{t("contact")}</h4>
              <div className="space-y-1">
                {overview.candidateName ? <OverviewRow icon={<UserRound className="size-4" />} label={t("candidateName")} value={overview.candidateName} tone={contactTone} /> : null}
                {overview.phone ? <OverviewRow icon={<Phone className="size-4" />} label={t("phoneNumber")} value={overview.phone} detail={overview.phoneCountry ? displayCountry(overview.phoneCountry, settings.uiLanguage) : null} tone={contactTone} /> : null}
              </div>
            </section> : null}

            {hasLocation ? <section aria-labelledby="overview-location">
              <h4 id="overview-location" className="mb-2 text-xs font-semibold text-foreground">{t("location")}</h4>
              <div className="space-y-1">
                {overview.statedLocation ? <OverviewRow icon={<MapPin className="size-4" />} label={t("statedLocation")} value={overview.statedLocation} tone={locationTone} /> : null}
                {overview.resolvedLocation ? <OverviewRow icon={<MapIcon className="size-4" />} label={t("resolvedLocation")} value={overview.resolvedLocation} tone={locationTone} /> : null}
                {overview.postalCode ? <OverviewRow icon={<MapPin className="size-4" />} label={t("postalCode")} value={overview.postalCode} tone={locationTone} /> : null}
                {overview.postalCountry ? <OverviewRow icon={<Globe2 className="size-4" />} label={t("postalCountry")} value={displayCountry(overview.postalCountry, settings.uiLanguage)} tone={locationTone} /> : null}
                {overview.postalConsistency ? <OverviewRow icon={<MapPin className="size-4" />} label={t("postalConsistency")} value={t(overview.postalConsistency === "consistent" ? "postalConsistent" : "postalMismatch")} tone={locationTone} /> : null}
                {overview.euStatus ? <OverviewRow icon={<Globe2 className="size-4" />} label={t("euStatus")} value={t(overview.euStatus === "outside" ? "outsideEu" : "insideEu")} detail={t("euStatusDisclaimer")} tone={locationTone} /> : null}
              </div>
            </section> : null}
          </div> : null}

          {overview.education.length || overview.educationStatus ? <section aria-labelledby="overview-education" className="border-t pt-4">
            <h4 id="overview-education" className="mb-2 text-xs font-semibold text-foreground">{t("education")}</h4>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {overview.education.map((item) => {
                const href = educationGoogleSearchUrl({ institution: item.searchSubject, program: item.searchContext });
                return <OverviewRow
                  key={item.id}
                  icon={<GraduationCap className="size-4" />}
                  label={t("educationEntry")}
                  value={item.value}
                  detail={joinDisplay(item.detail, item.needsReview ? reviewLabel : null)}
                  tone={educationTone}
                  action={href ? <GoogleSearchAction href={href} /> : null}
                />;
              })}
            </div>
            {!overview.education.length ? <p className="text-xs text-muted-foreground">{emptySection(overview.educationStatus)}</p> : null}
          </section> : null}

          {overview.employment.length || overview.employmentStatus ? <section aria-labelledby="overview-employment" className="border-t pt-4">
            <h4 id="overview-employment" className="mb-2 text-xs font-semibold text-foreground">{t("experience")}</h4>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {overview.employment.map((item) => {
                const href = companyGoogleSearchUrl({ organization: item.searchSubject, location: item.searchContext });
                return <OverviewRow
                  key={item.id}
                  icon={<BriefcaseBusiness className="size-4" />}
                  label={t("employmentEntry")}
                  value={item.value}
                  detail={joinDisplay(item.detail, item.needsReview ? reviewLabel : null)}
                  tone={employmentTone}
                  action={href ? <GoogleSearchAction href={href} /> : null}
                />;
              })}
            </div>
            {!overview.employment.length ? <p className="text-xs text-muted-foreground">{emptySection(overview.employmentStatus)}</p> : null}
          </section> : null}
        </div>
      ) : <p className="text-sm text-muted-foreground">{t("noCvDetails")}</p>}
    </HoverDisclosure>
  );
}

export function ResultsList({ items, onActiveIndex }: { items: AnalyzeItemResult[]; onActiveIndex?: (index: number) => void }) {
  const { settings, t } = useCopy();
  const reportRefs = useRef<Array<HTMLElement | null>>([]);
  const [reportOverrides, setReportOverrides] = useState<Record<string, AnalysisReport>>({});
  const [feedback, setFeedback] = useState<Record<string, FeedbackManifest>>({});
  const feedbackLoads = useRef(new Set<string>());
  const reportIds = items
    .filter((item): item is Exclude<AnalyzeItemResult, { status: "error" }> => item.status !== "error")
    .map((item) => item.report.analysis_id)
    .join(",");

  useEffect(() => {
    let cancelled = false;
    for (const analysisId of reportIds.split(",").filter(Boolean)) {
      if (feedbackLoads.current.has(analysisId)) continue;
      feedbackLoads.current.add(analysisId);
      fetch(`/api/analyses/${encodeURIComponent(analysisId)}/feedback`, { cache: "no-store" })
        .then(async (response) => response.ok ? response.json() : null)
        .then((manifest) => { if (!cancelled && manifest) setFeedback((previous) => ({ ...previous, [analysisId]: manifest })); })
        .catch(() => feedbackLoads.current.delete(analysisId));
    }
    return () => { cancelled = true; };
  }, [reportIds]);

  function updateCompletedResearch(
    report: AnalysisReport,
    patch: Partial<Pick<AnalysisReport, "company_research" | "education_research" | "linkedin_discovery">>,
  ) {
    setReportOverrides((previous) => {
      const current = previous[report.analysis_id] ?? report;
      return { ...previous, [report.analysis_id]: { ...current, ...patch } };
    });
  }

  useEffect(() => {
    if (!onActiveIndex) return;
    const ratios = new Map<Element, number>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
      let bestIndex = 0;
      let bestRatio = -1;
      reportRefs.current.forEach((element, index) => {
        const ratio = element ? ratios.get(element) ?? 0 : 0;
        if (ratio > bestRatio) {
          bestRatio = ratio;
          bestIndex = index;
        }
      });
      if (bestRatio > 0) onActiveIndex(bestIndex);
    }, { threshold: [0, 0.2, 0.4, 0.6, 0.8, 1] });
    reportRefs.current.forEach((element) => { if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [items, onActiveIndex]);

  if (!items.length) return null;

  return (
    <div className="space-y-4">
      {items.map((item, itemIndex) => {
        if (item.status === "error") {
          return (
            <Card key={`${item.filename}-${itemIndex}`} ref={(node) => { reportRefs.current[itemIndex] = node; }} className="report-enter scroll-mt-20 border-destructive/40">
              <CardHeader>
                <CardTitle className="text-base">{item.filename}</CardTitle>
                <CardDescription className="text-destructive">{item.error}</CardDescription>
              </CardHeader>
            </Card>
          );
        }

        const report = reportOverrides[item.report.analysis_id] ?? item.report;
        const presentation = adaptReportInterface(report, settings.uiLanguage);
        return (
          <Card key={`${item.filename}-${itemIndex}`} ref={(node) => { reportRefs.current[itemIndex] = node; }} className="report-enter scroll-mt-20 overflow-visible">
            <CardHeader className="pb-0">
              <CardTitle className="text-base">{item.filename}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {presentation.attention.length ? <HoverDisclosure className="rounded-md border border-rose-500/30 p-3" triggerClassName="text-sm font-medium" title={`${t("needsAttention")} (${presentation.attention.length})`} contentClassName="pt-3">
                <FlagList flags={presentation.attention} />
              </HoverDisclosure> : null}

              {presentation.worthKnowing.length ? <HoverDisclosure className="rounded-md border border-sky-500/30 p-3" triggerClassName="text-sm font-medium" title={`${t("worthKnowing")} (${presentation.worthKnowing.length})`} contentClassName="pt-3">
                <FlagList flags={presentation.worthKnowing} />
              </HoverDisclosure> : null}

              <StructuredFacts overview={presentation.overview} analysisId={report.analysis_id} feedbackManifest={feedback[report.analysis_id]} />

              {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.company_research !== false ? <CompanyResearchPanel report={report} feedbackManifest={feedback[report.analysis_id]} onResearchChange={(companyResearch) => updateCompletedResearch(report, { company_research: companyResearch })} /> : null}
              {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.education_research !== false ? <EducationResearchPanel report={report} feedbackManifest={feedback[report.analysis_id]} onResearchChange={(educationResearch) => updateCompletedResearch(report, { education_research: educationResearch })} /> : null}
              {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.linkedin_research !== false ? <LinkedInResearchPanel report={report} feedbackManifest={feedback[report.analysis_id]} onDiscoveryChange={(linkedinDiscovery) => updateCompletedResearch(report, { linkedin_discovery: linkedinDiscovery })} /> : null}

              {presentation.remaining.length ? <HoverDisclosure className="rounded-md border p-3" triggerClassName="text-sm font-medium" title={`${t("remaining")} (${presentation.remaining.length})`} feedbackSnapshotLabel={t("remaining")} action={feedbackTarget(feedback[report.analysis_id], "report_overall", "remaining", "section") ? <FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(feedback[report.analysis_id], "report_overall", "remaining", "section")!} /> : null} contentClassName="pt-3">
                <FlagList flags={presentation.remaining} />
              </HoverDisclosure> : null}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
