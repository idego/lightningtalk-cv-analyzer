"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { BriefcaseBusiness, Globe2, GraduationCap, Map as MapIcon, MapPin, Phone, UserRound, Wrench } from "lucide-react";
import { ThinkingOrb } from "thinking-orbs";
import type {
  AnalysisReport,
  AnalyzeItemResult,
  ChecklistId,
  ReviewFlag,
} from "@/lib/analyze-types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  aiStatusMessage,
  mergeCompletedResearch,
  partitionReviewFlags,
  presentReviewFlag,
  recruiterReviewFlags,
} from "@/lib/review-findings";
import { CompanyResearchPanel } from "@/components/analyze/company-research";
import { EducationResearchPanel } from "@/components/analyze/education-research";
import { LinkedInResearchPanel } from "@/components/analyze/linkedin-research";
import { FileDetailsDisclosure, LinkInspectionPanel } from "@/components/analyze/file-inspection";
import { type CopyKey, useCopy } from "@/lib/app-settings";
import { summarizeDateRanges } from "@/lib/date-range-summary";
import { StructuralAuditPanel } from "@/components/analyze/structural-audit-panel";
import { selectStructuredRecords, type DisplayRecord } from "@/lib/understanding-selectors";
import { educationOverviewDetail, employmentOverviewDetail } from "@/lib/overview-record-details";
import { RecordAuthorityDetails, type RecordAuthorityDetailLabels } from "@/components/analyze/record-authority-details";
import { FeedbackControl } from "@/components/analyze/feedback-control";
import { feedbackTarget, type FeedbackManifest } from "@/lib/feedback-types";

function FlagList({ flags, reportLanguage, analysisId, manifest, report }: { flags: ReviewFlag[]; reportLanguage: "en" | "pl";analysisId:string;manifest?:FeedbackManifest;report:AnalysisReport }) {
  const { t } = useCopy();
  return (
    <div className="space-y-2">
      {flags.map((flag) => {
        const copy = presentReviewFlag(flag, reportLanguage);
        const observation = report.deterministic.observations.find((item) => item.kind === flag.category);
        const fact = report.deterministic.facts.find((item) => item.kind === flag.category);
        const target = feedbackTarget(manifest, "review_finding", "finding", flag.id)
          ?? (observation ? feedbackTarget(manifest, "structural_observation", "deterministic", observation.id) : null)
          ?? (fact ? feedbackTarget(manifest, "structured_fact", "facts", fact.id) : null);
        return (
        <div key={flag.id} className="relative"><HoverDisclosure
          className="rounded-md border bg-muted/15 p-3 text-sm"
          allowHover
          title={
            <span className="block font-medium leading-snug">{copy.whatWeFound}</span>
          }
          contentClassName="pt-3"
        >
          <dl className="space-y-3 border-t pt-3">
            <div><dt className="text-[0.65rem] font-semibold uppercase tracking-[0.09em] text-muted-foreground">{t("whyItMatters")}</dt><dd className="mt-1 leading-relaxed">{copy.whyItMatters}</dd></div>
            <div><dt className="text-[0.65rem] font-semibold uppercase tracking-[0.09em] text-muted-foreground">{t("whatToCheck")}</dt><dd className="mt-1 leading-relaxed">{copy.whatToCheck}</dd></div>
          </dl>
          {flag.evidence.length ? (
            <p className="mt-3 border-l-2 pl-2 text-xs text-muted-foreground">
              {t("evidence")}: „{flag.evidence[0].excerpt}”
            </p>
          ) : null}
        </HoverDisclosure>{target?<div className="absolute right-2 top-2"><FeedbackControl analysisId={analysisId} target={target}/></div>:null}</div>
      );})}
    </div>
  );
}

const CHECK_LABELS: Record<ChecklistId, { en: string; pl: string }> = {
  contact: { en: "Contact details", pl: "Dane kontaktowe" },
  education: { en: "Education", pl: "Edukacja" },
  employment: { en: "Employment", pl: "Zatrudnienie" },
  timeline: { en: "Timeline", pl: "Chronologia" },
  duration_claims: { en: "Stated durations", pl: "Deklarowane okresy" },
  relationships: { en: "Company / client / project relations", pl: "Relacje firma / klient / projekt" },
  document_quality: { en: "Document quality", pl: "Jakość dokumentu" },
  protected_boundaries: { en: "Safe inference boundaries", pl: "Granice bezpiecznych wniosków" },
};

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
  action?:ReactNode;
}) {
  return (
    <div className="flex min-w-0 items-start gap-3 py-1.5">
      <OverviewIcon label={label} tone={tone}>{icon}</OverviewIcon>
      <div className="min-w-0 flex-1 pt-0.5">
        <p className="break-words text-sm font-medium leading-snug text-foreground">{value}</p>
        {detail ? <p className="mt-0.5 break-words text-xs leading-relaxed text-muted-foreground">{detail}</p> : null}
      </div>
      {action}
    </div>
  );
}

function displayCountry(countryCode: string, language: "en" | "pl") {
  const code = countryCode.toUpperCase();
  const name = new Intl.DisplayNames([language], { type: "region" }).of(code);
  return name && name !== code ? `${name} (${code})` : code;
}

function recordDetailsLabels(
  record: Pick<DisplayRecord, "authority" | "confidence">,
  t: (key: CopyKey, values?: Record<string, string | number>) => string,
): RecordAuthorityDetailLabels {
  const confidenceKey: CopyKey = record.confidence === "high"
    ? "confidenceHigh"
    : record.confidence === "low"
      ? "confidenceLow"
      : "confidenceMedium";
  return {
    authority: t(record.authority === "code" ? "recordSourceCode" : "recordSourceAi"),
    confidence: t("confidenceWithValue", { value: t(confidenceKey) }),
    aiEnrichment: t("recordAiEnrichment"),
    conflict: t("recordConflict"),
    unknownFields: t("recordUnknownFields"),
    codeValue: t("recordCodeValue"),
    aiValue: t("recordAiValue"),
  };
}

function StructuredFacts({ report,manifest }: { report: Extract<AnalyzeItemResult, { status: "ok" }>["report"];manifest?:FeedbackManifest }) {
  const { settings, t } = useCopy();
  const aiContact = report.ai_analysis.facts.contact;
  const candidateName = aiContact.find((fact) => fact.kind === "candidate_name")?.value;
  const phoneCandidate = report.deterministic.candidates.find((candidate) => candidate.subject === "person" && candidate.kind === "phone");
  const phone = phoneCandidate?.value
    ?? aiContact.find((fact) => fact.kind === "phone")?.value;
  const statedLocationCandidate = report.deterministic.candidates.find((candidate) => candidate.subject === "person" && candidate.kind === "explicit_location");
  const statedLocation = statedLocationCandidate?.value
    ?? aiContact.find((fact) => fact.kind === "stated_location")?.value;
  const phoneCountry = report.deterministic.facts.find((fact) => fact.subject === "person" && fact.kind === "phone_country")?.value;
  const claimedLocation = report.deterministic.facts.find((fact) => fact.subject === "person" && fact.kind === "claimed_location");
  const resolvedLocation = claimedLocation
    ? `${claimedLocation.resolved_name ?? displayCountry(claimedLocation.value, settings.uiLanguage)}${claimedLocation.resolved_name && claimedLocation.value ? ` (${claimedLocation.value})` : ""}`
    : null;
  const postalCountryFact = report.deterministic.facts.find((fact) => fact.subject === "person" && fact.kind === "postal_country");
  const postalCandidateIds = new Set(postalCountryFact?.source_candidate_ids ?? []);
  const postalCandidate = report.deterministic.candidates.find((candidate) => candidate.kind === "postal" && postalCandidateIds.has(candidate.id));
  const postalCode = postalCandidate?.value;
  const euObservation = report.deterministic.observations.find((observation) => observation.kind === "combined_location_outside_eu" || observation.kind === "combined_location_inside_eu");
  const euStatus = euObservation?.kind === "combined_location_outside_eu"
      ? t("outsideEu")
    : euObservation?.kind === "combined_location_inside_eu"
      ? t("insideEu")
      : null;
  const selectedRecords = selectStructuredRecords(report);
  const education = selectedRecords.filter((record) => record.kind === "education");
  const employment = selectedRecords.filter((record) => record.kind === "employment");
  const skills = report.document_understanding?.skills ?? [];
  const timelineNow = new Date();
  const educationTimeline = summarizeDateRanges(education.map((fact) => fact.study_dates), timelineNow, settings.uiLanguage);
  const employmentTimeline = summarizeDateRanges(employment.map((fact) => fact.employment_dates), timelineNow, settings.uiLanguage);
  const hasContact = Boolean(candidateName || phone);
  const hasLocation = Boolean(statedLocation || resolvedLocation || postalCode || postalCountryFact || euStatus);
  const hasFacts = hasContact || hasLocation || education.length > 0 || employment.length > 0 || skills.length > 0;
  const contactTone = "bg-sky-500/10 text-sky-700 dark:text-sky-300";
  const locationTone = "bg-violet-500/10 text-violet-700 dark:text-violet-300";
  const educationTone = "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300";
  const employmentTone = "bg-amber-500/10 text-amber-800 dark:text-amber-200";
  const skillsTone = "bg-cyan-500/10 text-cyan-800 dark:text-cyan-200";

  return (
    <HoverDisclosure
      className="rounded-md border p-3"
      triggerClassName="text-sm font-medium"
      title={t("extracted")}
      contentClassName="pt-4"
    >
      {hasFacts ? (
        <div className="space-y-5">
          {hasContact || hasLocation ? <div className="grid gap-x-8 gap-y-5 md:grid-cols-2">
            {hasContact ? <section aria-labelledby="overview-contact">
              <h4 id="overview-contact" className="mb-2 text-xs font-semibold text-foreground">{t("contact")}</h4>
              <div className="space-y-1">
                {candidateName ? <OverviewRow icon={<UserRound className="size-4" />} label={t("candidateName")} value={candidateName} tone={contactTone} /> : null}
                {phone ? <OverviewRow
                  icon={<Phone className="size-4" />}
                  label={t("phoneNumber")}
                  value={phone}
                  detail={phoneCountry ? displayCountry(phoneCountry, settings.uiLanguage) : null}
                  tone={contactTone}
                  action={phoneCandidate && feedbackTarget(manifest,"structured_fact","candidates",phoneCandidate.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","candidates",phoneCandidate.id)!}/>:undefined}
                /> : null}
              </div>
            </section> : null}

            {hasLocation ? <section aria-labelledby="overview-location">
              <h4 id="overview-location" className="mb-2 text-xs font-semibold text-foreground">{t("location")}</h4>
              <div className="space-y-1">
                {statedLocation ? <OverviewRow icon={<MapPin className="size-4" />} label={t("statedLocation")} value={statedLocation} tone={locationTone} action={statedLocationCandidate&&feedbackTarget(manifest,"structured_fact","candidates",statedLocationCandidate.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","candidates",statedLocationCandidate.id)!}/>:undefined} /> : null}
                {resolvedLocation ? <OverviewRow icon={<MapIcon className="size-4" />} label={t("resolvedLocation")} value={resolvedLocation} tone={locationTone} action={claimedLocation&&feedbackTarget(manifest,"structured_fact","facts",claimedLocation.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","facts",claimedLocation.id)!}/>:undefined} /> : null}
                {postalCode ? <OverviewRow icon={<MapPin className="size-4" />} label={t("postalCode")} value={postalCode} tone={locationTone} action={postalCandidate&&feedbackTarget(manifest,"structured_fact","candidates",postalCandidate.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","candidates",postalCandidate.id)!}/>:undefined} /> : null}
                {postalCountryFact ? <OverviewRow icon={<Globe2 className="size-4" />} label={t("postalCountry")} value={displayCountry(postalCountryFact.value, settings.uiLanguage)} tone={locationTone} /> : null}
                {euStatus ? <OverviewRow icon={<Globe2 className="size-4" />} label={t("euStatus")} value={euStatus} tone={locationTone} /> : null}
              </div>
            </section> : null}
          </div> : null}

          {education.length ? <section aria-labelledby="overview-education" className="border-t pt-4">
            <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <h4 id="overview-education" className="text-xs font-semibold text-foreground">{t("education")}</h4>
              {educationTimeline ? <span className="text-xs font-normal text-muted-foreground">{educationTimeline}</span> : null}
            </div>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {education.map((fact) => <OverviewRow
                key={fact.id}
                icon={<GraduationCap className="size-4" />}
                label={t("educationEntry")}
                value={fact.institution ?? t("educationEntry")}
                detail={<RecordAuthorityDetails
                  record={fact}
                  labels={recordDetailsLabels(fact, t)}
                  leading={[educationOverviewDetail(fact)]}
                />}
                tone={educationTone}
                action={feedbackTarget(manifest,"structured_fact","records",fact.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","records",fact.id)!}/>:undefined}
              />)}
            </div>
          </section> : null}

          {employment.length ? <section aria-labelledby="overview-employment" className="border-t pt-4">
            <div className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <h4 id="overview-employment" className="text-xs font-semibold text-foreground">{t("experience")}</h4>
              {employmentTimeline ? <span className="text-xs font-normal text-muted-foreground">{employmentTimeline}</span> : null}
            </div>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {employment.map((fact) => <OverviewRow
                key={fact.id}
                icon={<BriefcaseBusiness className="size-4" />}
                label={t("employmentEntry")}
                value={fact.role ?? fact.relationship_type ?? t("employmentEntry")}
                detail={<RecordAuthorityDetails
                  record={fact}
                  labels={recordDetailsLabels(fact, t)}
                  leading={[employmentOverviewDetail(fact)]}
                />}
                tone={employmentTone}
                action={feedbackTarget(manifest,"structured_fact","records",fact.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","records",fact.id)!}/>:undefined}
              />)}
            </div>
          </section> : null}

          {skills.length ? <section aria-labelledby="overview-skills" className="border-t pt-4">
            <h4 id="overview-skills" className="mb-2 text-xs font-semibold text-foreground">{t("skills")}</h4>
            <div className="grid gap-x-8 gap-y-1 md:grid-cols-2">
              {skills.map((skill) => <OverviewRow
                key={skill.id}
                icon={<Wrench className="size-4" />}
                label={t("explicitSkill")}
                value={skill.display_label}
                tone={skillsTone}
                action={feedbackTarget(manifest,"structured_fact","skills",skill.id)?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(manifest,"structured_fact","skills",skill.id)!}/>:undefined}
              />)}
            </div>
          </section> : null}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("noCvDetails")}
        </p>
      )}
    </HoverDisclosure>
  );
}

export function ResultsList({ items, onActiveIndex }: { items: AnalyzeItemResult[]; onActiveIndex?: (index: number) => void }) {
  const { settings, t } = useCopy();
  const reportRefs = useRef<Array<HTMLElement | null>>([]);
  const [reportOverrides, setReportOverrides] = useState<Record<string, Extract<AnalyzeItemResult, { status: "ok" }>["report"]>>({});
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState<Record<string, FeedbackManifest>>({});
  const feedbackLoads=useRef(new Set<string>());
  const reportIds = items.filter((item): item is Extract<AnalyzeItemResult,{status:"ok"}>=>item.status==="ok").map(item=>item.report.analysis_id).join(",");

  useEffect(()=>{let cancelled=false;for(const analysisId of reportIds.split(",").filter(Boolean)){if(feedbackLoads.current.has(analysisId))continue;feedbackLoads.current.add(analysisId);fetch(`/api/analyses/${encodeURIComponent(analysisId)}/feedback`,{cache:"no-store"}).then(async response=>response.ok?response.json():null).then(manifest=>{if(!cancelled&&manifest)setFeedback(previous=>({...previous,[analysisId]:manifest}))}).catch(()=>feedbackLoads.current.delete(analysisId))}return()=>{cancelled=true}},[reportIds]);

  function updateCompletedResearch(
    report: AnalysisReport,
    patch: Partial<Pick<
      AnalysisReport,
      "company_research" | "education_research" | "linkedin_discovery"
    >>,
  ) {
    setReportOverrides((previous) => {
      const current = previous[report.analysis_id] ?? report;
      return {
        ...previous,
        [report.analysis_id]: mergeCompletedResearch(current, patch),
      };
    });
  }

  async function retryAi(report: Extract<AnalyzeItemResult, { status: "ok" }>["report"]) {
    setRetryingId(report.analysis_id);
    setRetryError(previous => ({ ...previous, [report.analysis_id]: "" }));
    try {
      const response = await fetch(`/api/analyses/${encodeURIComponent(report.analysis_id)}/ai/retry`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ aiEnabled: settings.aiEnabled }) });
      const payload = await response.json();
      if (!response.ok) throw new Error(t("analysisFailed"));
      setReportOverrides(previous => ({ ...previous, [report.analysis_id]: payload }));
    } catch {
      setRetryError(previous => ({ ...previous, [report.analysis_id]: t("analysisFailed") }));
    } finally {
      setRetryingId(null);
    }
  }

  useEffect(() => {
    if (!onActiveIndex) return;
    const ratios = new Map<Element, number>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
      let bestIndex = 0; let bestRatio = -1;
      reportRefs.current.forEach((element, index) => { const ratio = element ? ratios.get(element) ?? 0 : 0; if (ratio > bestRatio) { bestRatio = ratio; bestIndex = index; } });
      if (bestRatio > 0) onActiveIndex(bestIndex);
    }, { threshold: [0, 0.2, 0.4, 0.6, 0.8, 1] });
    reportRefs.current.forEach(element => { if (element) observer.observe(element); });
    return () => observer.disconnect();
  }, [items, onActiveIndex]);
  if (!items.length) {
    return null;
  }

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
        const grouped = partitionReviewFlags(recruiterReviewFlags(report, report.ai_analysis.report_language));
        const statusMessage = aiStatusMessage(
          report.ai_analysis.status,
          report.ai_analysis.failure_reason,
          settings.uiLanguage,
        );
        const checkedCount = Object.values(report.checklist.checks).filter(
          (check) => check.checked,
        ).length;
        return (
          <Card
            key={`${item.filename}-${itemIndex}`}
            ref={(node) => { reportRefs.current[itemIndex] = node; }}
            className={report.ai_analysis.status === "succeeded" ? "scroll-mt-20" : "report-enter scroll-mt-20"}
          >
            <CardHeader className="pb-0">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{item.filename}</CardTitle>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div
                key={`${report.ai_analysis.status}:${report.ai_analysis.attempt_count}`}
                className={report.ai_analysis.status === "succeeded" ? "report-enrichment-enter space-y-3" : "space-y-3"}
              >
                {statusMessage ? (
                  <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-3"><span className="flex items-center gap-2">{report.ai_analysis.status === "pending" ? <ThinkingOrb state="working" size={20} theme="auto" aria-label={t("aiAnalysisInProgress")} /> : null}{statusMessage}</span><span className="flex items-center gap-2">{report.ai_analysis.status === "failed"&&feedbackTarget(feedback[report.analysis_id],"operation_failure","ai_analysis","failure")?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(feedback[report.analysis_id],"operation_failure","ai_analysis","failure")!} failure/>:null}{report.ai_analysis.status === "failed" && report.ai_analysis.manual_retry_available ? <Button variant="outline" size="sm" disabled={retryingId === report.analysis_id} onClick={() => retryAi(report)}>{retryingId === report.analysis_id ? t("retryingAi") : t("retryAi")}</Button> : null}</span></div>
                    {retryError[report.analysis_id] ? <p className="mt-2 text-xs text-destructive">{retryError[report.analysis_id]}</p> : null}
                  </div>
                ) : null}

                <StructuralAuditPanel
                  audits={report.structural_audits}
                  language={settings.uiLanguage}
                  employment={report.ai_analysis.facts.employment}
                  education={report.ai_analysis.facts.education}
                  understanding={report.document_understanding}
                />

                {grouped.attention.length ? <HoverDisclosure
                  className="rounded-md border border-rose-500/30 p-3"
                  triggerClassName="text-sm font-medium"
                  title={`${t("needsAttention")} (${grouped.attention.length})`}
                  contentClassName="pt-3"
                >
                  <FlagList flags={grouped.attention} reportLanguage={report.ai_analysis.report_language} analysisId={report.analysis_id} manifest={feedback[report.analysis_id]} report={report} />
                </HoverDisclosure> : null}

                {grouped.worthKnowing.length ? <HoverDisclosure
                  className="rounded-md border border-sky-500/30 p-3"
                  triggerClassName="text-sm font-medium"
                  title={`${t("worthKnowing")} (${grouped.worthKnowing.length})`}
                  contentClassName="pt-3"
                >
                  <FlagList flags={grouped.worthKnowing} reportLanguage={report.ai_analysis.report_language} analysisId={report.analysis_id} manifest={feedback[report.analysis_id]} report={report} />
                </HoverDisclosure> : null}

                <StructuredFacts report={report} manifest={feedback[report.analysis_id]} />
                <FileDetailsDisclosure details={report.file_details} analysisId={report.analysis_id} manifest={feedback[report.analysis_id]} />
                <LinkInspectionPanel inspection={report.link_inspection} analysisId={report.analysis_id} manifest={feedback[report.analysis_id]} />
              </div>

              {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.company_research !== false ? <CompanyResearchPanel
                report={report}
                feedbackManifest={feedback[report.analysis_id]}
                onResearchChange={(research) => updateCompletedResearch(report, { company_research: research })}
              /> : null}

              {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.education_research !== false ? <EducationResearchPanel
                report={report}
                feedbackManifest={feedback[report.analysis_id]}
                onResearchChange={(research) => updateCompletedResearch(report, { education_research: research })}
              /> : null}
              {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.linkedin_research !== false ? <LinkedInResearchPanel
                report={report}
                feedbackManifest={feedback[report.analysis_id]}
                onDiscoveryChange={(discovery) => updateCompletedResearch(report, { linkedin_discovery: discovery })}
              /> : null}

              {grouped.remaining.length ? <HoverDisclosure
                className="rounded-md border p-3"
                triggerClassName="text-sm font-medium"
                title={`${t("remaining")} (${grouped.remaining.length})`}
                contentClassName="pt-3"
              >
                <FlagList flags={grouped.remaining} reportLanguage={report.ai_analysis.report_language} analysisId={report.analysis_id} manifest={feedback[report.analysis_id]} report={report} />
              </HoverDisclosure> : null}

              <HoverDisclosure
                className="rounded-md border p-3"
                triggerClassName="text-sm font-medium"
                title={`${t("checksRun")}: ${checkedCount}/${Object.keys(report.checklist.checks).length}`}
                contentClassName="pt-3"
              >
                <ul className="grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                  {Object.entries(report.checklist.checks).map(([id, check]) => (
                    <li key={id}>
                      {check.checked ? "✓" : "—"} {CHECK_LABELS[id as ChecklistId][settings.uiLanguage]}
                      {check.issue_count ? ` (${check.issue_count})` : ""}
                    </li>
                  ))}
                </ul>
              </HoverDisclosure>

              <div className="flex items-center justify-between gap-3"><p className="text-xs text-muted-foreground">{report.disclaimer}</p>{feedbackTarget(feedback[report.analysis_id],"report_overall","report","overall")?<FeedbackControl analysisId={report.analysis_id} target={feedbackTarget(feedback[report.analysis_id],"report_overall","report","overall")!}/>:null}</div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
