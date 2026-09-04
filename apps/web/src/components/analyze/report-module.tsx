"use client";

import { Lightbulb } from "lucide-react";
import type { AnalysisReport } from "@/lib/analyze-types";
import { adaptReportInterface } from "@/lib/report-interface-adapter";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { CompanyResearchPanel } from "@/components/analyze/company-research";
import { EducationResearchPanel } from "@/components/analyze/education-research";
import { LinkedInResearchPanel } from "@/components/analyze/linkedin-research";
import { FlagList, StructuredFacts } from "@/components/analyze/results-list";
import { SectionTitle } from "@/components/analyze/section-title";
import { useCopy } from "@/lib/app-settings";

export const reportModuleCategories = ["report", "attention", "worth_knowing", "company_research", "education_research", "linkedin_discovery"] as const;
export type ReportModuleCategory = (typeof reportModuleCategories)[number];

export function isReportModuleCategory(value: unknown): value is ReportModuleCategory {
  return typeof value === "string" && (reportModuleCategories as readonly string[]).includes(value);
}

export function isAnalysisReport(value: unknown): value is AnalysisReport {
  if (!value || typeof value !== "object") return false;
  const report = value as Partial<AnalysisReport>;
  return typeof report.analysis_id === "string" && Boolean(report.base_analysis && typeof report.base_analysis === "object");
}

/** Renders one report module exactly as the analysis view does, without feedback or research actions. */
export function ReportModule({ report, category }: { report: AnalysisReport; category: ReportModuleCategory }) {
  const { settings, t } = useCopy();
  const presentation = adaptReportInterface(report, settings.uiLanguage);

  switch (category) {
    case "report":
      return <StructuredFacts overview={presentation.overview} report={report} readOnly />;
    case "attention":
      return <HoverDisclosure className="rounded-md border border-rose-500/30 p-3" triggerClassName="text-sm font-medium" title={`${t("needsAttention")} (${presentation.attention.length})`} defaultOpen contentClassName="pt-3">
        <FlagList flags={presentation.attention} />
      </HoverDisclosure>;
    case "worth_knowing":
      return <HoverDisclosure className="rounded-md border border-sky-500/30 p-3" triggerClassName="text-sm font-medium" title={<SectionTitle icon={<Lightbulb className="size-4" />}>{t("worthKnowing")} ({presentation.worthKnowing.length})</SectionTitle>} defaultOpen contentClassName="pt-3">
        <FlagList flags={presentation.worthKnowing} />
      </HoverDisclosure>;
    case "company_research":
      return <CompanyResearchPanel report={report} readOnly />;
    case "education_research":
      return <EducationResearchPanel report={report} readOnly />;
    case "linkedin_discovery":
      return <LinkedInResearchPanel report={report} readOnly />;
  }
}
