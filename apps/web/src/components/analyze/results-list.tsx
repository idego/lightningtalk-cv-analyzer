"use client";

import { useEffect, useRef, useState } from "react";
import type {
  AnalysisRecord,
  AnalysisReport,
  AnalyzeItemResult,
  EducationRecord,
  EmploymentRecord,
  SupportedField,
} from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";
import { CompanyResearchPanel } from "@/components/analyze/company-research";
import { EducationResearchPanel } from "@/components/analyze/education-research";
import { LinkedInResearchPanel } from "@/components/analyze/linkedin-research";
import { useCopy } from "@/lib/app-settings";

function value(field: SupportedField | null | undefined) {
  return field?.value ?? null;
}

function FieldView({
  label,
  field,
}: {
  label: string;
  field: SupportedField | null;
}) {
  if (!field) return null;
  return (
    <HoverDisclosure
      className="rounded-md border bg-muted/15 p-3"
      allowHover
      title={<span className="text-sm"><span className="text-muted-foreground">{label}: </span><strong>{field.value}</strong></span>}
      contentClassName="pt-2"
    >
      <p className="text-xs text-muted-foreground">
        {field.status === "ambiguous" ? "Ambiguous · " : ""}
        {field.evidence[0]?.excerpt ? `Evidence: „${field.evidence[0].excerpt}”` : "No evidence excerpt"}
      </p>
    </HoverDisclosure>
  );
}

function RecordState({ record }: { record: AnalysisRecord }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge variant="outline">{record.status}</Badge>
      {record.relation_status === "ambiguous" ? <Badge variant="outline">ambiguous relation</Badge> : null}
      {record.added_by_reviewer ? <Badge variant="secondary">added by reviewer</Badge> : null}
    </div>
  );
}

function DeclaredLocationView({ report }: { report: AnalysisReport }) {
  const field = report.base_analysis.profile.declared_location;
  if (!field) return null;
  const resolution = report.mechanical.location_resolution.find(
    (item) => item.subject === "declared_location",
  );
  const resolved = [resolution?.canonical_name, resolution?.country_code]
    .filter((item): item is string => typeof item === "string" && item.length > 0)
    .join(" · ");
  return (
    <HoverDisclosure
      className="rounded-md border bg-muted/15 p-3"
      allowHover
      title={<span className="text-sm"><span className="text-muted-foreground">Declared location: </span><strong>{field.value}</strong></span>}
      contentClassName="space-y-1 pt-2"
    >
      <p className="text-xs text-muted-foreground">{resolved ? `Resolved: ${resolved}` : "Geographic resolution unavailable"}</p>
      <p className="text-xs text-muted-foreground">{field.evidence[0]?.excerpt ? `Evidence: „${field.evidence[0].excerpt}”` : "No evidence excerpt"}</p>
    </HoverDisclosure>
  );
}

function EmploymentView({ record }: { record: EmploymentRecord }) {
  const title = [value(record.role), value(record.organization)].filter(Boolean).join(" · ") || "Employment entry";
  const detail = [
    [value(record.start_date), value(record.end_date)].filter(Boolean).join(" – "),
    value(record.location),
    value(record.relationship_type),
  ].filter(Boolean).join(" · ");
  return (
    <article className="rounded-md border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h4 className="font-medium">{title}</h4>{detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}</div>
        <RecordState record={record} />
      </div>
    </article>
  );
}

function EducationView({ record }: { record: EducationRecord }) {
  const title = [value(record.institution), value(record.program), value(record.degree), value(record.certificate)].filter(Boolean).join(" · ") || "Education entry";
  const detail = [
    [value(record.start_date), value(record.end_date)].filter(Boolean).join(" – "),
    value(record.location),
  ].filter(Boolean).join(" · ");
  return (
    <article className="rounded-md border p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><h4 className="font-medium">{title}</h4>{detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}</div>
        <RecordState record={record} />
      </div>
    </article>
  );
}

function MechanicalView({ report }: { report: AnalysisReport }) {
  const groups = [
    ["Phones", report.mechanical.phones],
    ["E-mails", report.mechanical.emails],
    ["Literal links", report.mechanical.literal_links],
    ["Postal candidates", report.mechanical.postal_candidates],
    ["Accepted postal addresses", report.mechanical.accepted_postal_addresses],
    ["E-mail findings", report.mechanical.email_findings],
    ["Direct comparisons", report.mechanical.comparisons],
  ] as const;
  const present = groups.filter(([, items]) => items.length);
  if (!present.length) return null;
  return (
    <HoverDisclosure
      className="rounded-md border p-3"
      triggerClassName="text-sm font-medium"
      title="Mechanical facts"
      contentClassName="space-y-3 pt-3"
    >
      {present.map(([label, items]) => (
        <div key={label}>
          <h4 className="text-xs font-semibold">{label}</h4>
          <ul className="mt-1 space-y-1 text-sm text-muted-foreground">
            {items.map((item, index) => (
              <li key={index}>
                {String(item.value ?? item.normalized_url ?? item.kind ?? item.relationship ?? item.country_code ?? "candidate")}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </HoverDisclosure>
  );
}

function AnalysisContent({
  report,
  onChange,
}: {
  report: AnalysisReport;
  onChange: (patch: Partial<Pick<AnalysisReport, "company_research" | "education_research" | "linkedin_discovery">>) => void;
}) {
  const { settings } = useCopy();
  const profile = report.base_analysis.profile;
  const review = report.base_analysis.review;
  return (
    <CardContent className="space-y-3">
      <section className="space-y-2">
        <h3 className="text-sm font-semibold">Profile</h3>
        <div className="grid gap-2 md:grid-cols-2">
          <FieldView label="Name" field={profile.candidate_name} />
          <FieldView label="Headline" field={profile.headline} />
          <DeclaredLocationView report={report} />
          <FieldView label="Summary" field={profile.summary} />
        </div>
        {profile.skills.length ? <p className="text-sm"><span className="text-muted-foreground">Skills: </span>{profile.skills.map((item) => item.value).join(", ")}</p> : null}
        {profile.languages.length ? <p className="text-sm"><span className="text-muted-foreground">Languages: </span>{profile.languages.map((item) => item.value).join(", ")}</p> : null}
      </section>

      <section className="space-y-2 border-t pt-3">
        <h3 className="text-sm font-semibold">Employment ({report.base_analysis.employment.length})</h3>
        {report.base_analysis.employment.length
          ? report.base_analysis.employment.map((record) => <EmploymentView key={record.id} record={record} />)
          : <p className="text-sm text-muted-foreground">No employment entries extracted.</p>}
      </section>

      <section className="space-y-2 border-t pt-3">
        <h3 className="text-sm font-semibold">Education ({report.base_analysis.education.length})</h3>
        {report.base_analysis.education.length
          ? report.base_analysis.education.map((record) => <EducationView key={record.id} record={record} />)
          : <p className="text-sm text-muted-foreground">No education entries extracted.</p>}
      </section>

      {review.added_profile_fields.length || review.added_candidate_ids.length || review.conflicts.length || review.coverage_gaps.length ? (
        <HoverDisclosure
          className="rounded-md border border-amber-500/30 p-3"
          triggerClassName="text-sm font-medium"
          title="Reviewer changes and gaps"
          contentClassName="space-y-1 pt-3 text-sm text-muted-foreground"
        >
          {review.added_profile_fields.length ? <p>Added missing profile fields: {review.added_profile_fields.join(", ")}</p> : null}
          {review.added_candidate_ids.length ? <p>Added missing candidates: {review.added_candidate_ids.length}</p> : null}
          {review.conflicts.length ? <p>Conflicts: {review.conflicts.length}</p> : null}
          {review.coverage_gaps.length ? <p>Coverage gaps: {review.coverage_gaps.length}</p> : null}
          {review.rejected.length ? <p>Rejected candidates or fields: {review.rejected.length}</p> : null}
        </HoverDisclosure>
      ) : null}

      {Object.values(report.base_analysis.pass_statuses).some((pass) => pass.status !== "completed") ? (
        <div className="rounded-md border border-amber-500/30 p-3 text-sm">
          <p className="font-medium">Incomplete analysis passes</p>
          <ul className="mt-1 space-y-1 text-muted-foreground">
            {Object.entries(report.base_analysis.pass_statuses)
              .filter(([, pass]) => pass.status !== "completed")
              .map(([name, pass]) => <li key={name}>{name}: {pass.status}{pass.failure_reason ? ` (${pass.failure_reason})` : ""}</li>)}
          </ul>
        </div>
      ) : null}

      <MechanicalView report={report} />

      {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.company_research !== false ? (
        <CompanyResearchPanel report={report} onResearchChange={(company_research) => onChange({ company_research })} />
      ) : null}
      {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.education_research !== false ? (
        <EducationResearchPanel report={report} onResearchChange={(education_research) => onChange({ education_research })} />
      ) : null}
      {settings.aiEnabled && report.ai_features_enabled !== false && report.ai_capabilities?.linkedin_research !== false ? (
        <LinkedInResearchPanel report={report} onDiscoveryChange={(linkedin_discovery) => onChange({ linkedin_discovery })} />
      ) : null}

      {report.limitations.length ? (
        <HoverDisclosure
          className="rounded-md border p-3"
          triggerClassName="text-sm font-medium"
          title={`Limitations (${report.limitations.length})`}
          contentClassName="pt-3"
        >
          <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
            {report.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
          </ul>
        </HoverDisclosure>
      ) : null}
    </CardContent>
  );
}

export function ResultsList({
  items,
  onActiveIndex,
}: {
  items: AnalyzeItemResult[];
  onActiveIndex?: (index: number) => void;
}) {
  const reportRefs = useRef<Array<HTMLElement | null>>([]);
  const [overrides, setOverrides] = useState<Record<string, AnalysisReport>>({});

  useEffect(() => {
    if (!onActiveIndex) return;
    const ratios = new Map<Element, number>();
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        ratios.set(entry.target, entry.isIntersecting ? entry.intersectionRatio : 0);
      }
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
    }, { threshold: [0, 0.25, 0.5, 0.75, 1] });
    reportRefs.current.forEach((element) => {
      if (element) observer.observe(element);
    });
    return () => observer.disconnect();
  }, [items, onActiveIndex]);

  return (
    <div className="space-y-4">
      {items.map((item, index) => {
        if (item.status === "error") {
          return (
            <Card
              key={`${item.filename}-${index}`}
              ref={(node) => { reportRefs.current[index] = node; }}
              className="border-destructive/40"
            >
              <CardHeader>
                <CardTitle className="text-base">{item.filename}</CardTitle>
                <CardDescription className="text-destructive">{item.error}</CardDescription>
              </CardHeader>
            </Card>
          );
        }
        const report = overrides[item.report.analysis_id] ?? item.report;
        const update = (patch: Partial<Pick<AnalysisReport, "company_research" | "education_research" | "linkedin_discovery">>) => {
          setOverrides((current) => ({
            ...current,
            [report.analysis_id]: { ...report, ...patch },
          }));
        };
        return (
          <Card
            key={report.analysis_id}
            ref={(node) => { reportRefs.current[index] = node; }}
            className="scroll-mt-20"
          >
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{item.filename}</CardTitle>
                  <CardDescription>{report.strategy.name} · {report.strategy.version}</CardDescription>
                </div>
                <Badge variant="outline">{report.base_analysis.status}</Badge>
              </div>
            </CardHeader>
            <AnalysisContent report={report} onChange={update} />
          </Card>
        );
      })}
    </div>
  );
}
