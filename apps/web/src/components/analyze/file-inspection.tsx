"use client";

import { CheckCircle2, FileText, ShieldAlert } from "lucide-react";
import type {
  FileDetail,
  FileDetailField,
  FileDetails,
  LinkCheckResult,
  LinkInspection,
  LinkOutcomeStatus,
} from "@/lib/analyze-types";
import { Badge } from "@/components/ui/badge";
import { HoverDisclosure } from "@/components/ui/hover-disclosure";

const FILE_DETAIL_ORDER: FileDetailField[] = [
  "author",
  "creator",
  "producer",
  "title",
  "subject",
  "creation_time",
  "modification_time",
  "created",
  "modified",
  "last_modifier",
  "revision",
];

const FILE_DETAIL_LABELS: Record<FileDetailField, string> = {
  author: "Author",
  creator: "Creator",
  producer: "Producer",
  title: "Title",
  subject: "Subject",
  creation_time: "Creation time",
  modification_time: "Modification time",
  created: "Created",
  modified: "Modified",
  last_modifier: "Last modifier",
  revision: "Revision",
};

export function FileDetailsDisclosure({ details }: { details?: FileDetails | null }) {
  if (!details) return null;

  return (
    <HoverDisclosure
      className="rounded-md border p-3"
      triggerClassName="min-h-8 text-sm font-medium"
      title={
        <span className="flex min-w-0 items-center gap-2">
          <FileText aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
          <span>File details</span>
          <span className="text-xs font-normal text-muted-foreground">({details.source_format.toUpperCase()})</span>
        </span>
      }
      contentClassName="pt-4"
    >
      <dl className="grid gap-x-6 gap-y-3 border-t pt-3 text-sm sm:grid-cols-2">
        {FILE_DETAIL_ORDER.map((field) => {
          const detail = details.fields[field];
          return (
            <div key={field} className="min-w-0">
              <dt className="text-xs font-semibold text-muted-foreground">{FILE_DETAIL_LABELS[field]}</dt>
              <dd className="mt-0.5 break-words leading-relaxed">
                {detail ? <FileDetailValue detail={detail} /> : <UnavailableValue />}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
        Metadata is document context only. It does not establish authenticity, identity, or location.
      </p>
    </HoverDisclosure>
  );
}

function FileDetailValue({ detail }: { detail: FileDetail }) {
  if (detail.status !== "available" || !detail.value) return <UnavailableValue />;
  return <span>{detail.value}</span>;
}

function UnavailableValue() {
  return <span className="text-muted-foreground">Unavailable</span>;
}

export function LinkInspectionPanel({ inspection }: { inspection?: LinkInspection | null }) {
  if (!inspection || !inspection.links.length) return null;

  const suspicious = inspection.links.filter((link) => link.status === "SUSPICIOUS");
  const unavailable = inspection.links.filter((link) => link.status === "UNAVAILABLE");
  const reachable = inspection.links.filter((link) => link.status === "REACHABLE");
  const notChecked = inspection.links.filter((link) => link.status === "NOT_CHECKED");

  return (
    <section aria-label="Link inspection" className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div>
          <h3 className="font-medium">Link inspection</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            Document-level checks only; they do not make a candidate-level finding.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {inspection.links.length} inspected
        </p>
      </div>

      {suspicious.length ? (
        <div className="space-y-2 pt-1" aria-label={`${suspicious.length} suspicious document links`}>
          {suspicious.map((link) => <LinkResultCard key={link.link_id} link={link} />)}
        </div>
      ) : null}

      {unavailable.length ? (
        <div className="space-y-2 pt-1" aria-label={`${unavailable.length} unavailable document links`}>
          {unavailable.map((link) => <LinkResultCard key={link.link_id} link={link} />)}
        </div>
      ) : null}

      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1"><CheckCircle2 aria-hidden="true" className="size-3.5" /> Reachable: {reachable.length}</span>
        <span>Unavailable: {unavailable.length}</span>
        {notChecked.length ? <span>Not checked: {notChecked.length}</span> : null}
      </p>
    </section>
  );
}

function LinkResultCard({ link }: { link: LinkCheckResult }) {
  const suspicious = link.status === "SUSPICIOUS";
  const statusLabel: LinkOutcomeStatus = suspicious ? "SUSPICIOUS" : "UNAVAILABLE";
  const title = link.title || "Document link needs review.";

  return (
    <HoverDisclosure
      className={suspicious
        ? "rounded-md border border-rose-500/40 bg-rose-500/5 p-3"
        : "rounded-md border bg-muted/15 p-3"}
      triggerClassName="min-h-8 text-sm"
      title={
        <span className="flex min-w-0 items-start gap-2">
          {suspicious ? <ShieldAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-rose-700 dark:text-rose-300" /> : null}
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              <Badge variant={suspicious ? "destructive" : "outline"}>{statusLabel}</Badge>
              <span className="font-medium leading-snug">{title}</span>
            </span>
            <span className="mt-1 block break-words text-xs font-normal leading-relaxed text-muted-foreground">
              {link.displayed_value ?? link.sanitized_target ?? "Embedded hyperlink target"}
            </span>
          </span>
        </span>
      }
      contentClassName="pt-3"
    >
      <dl className="grid gap-x-6 gap-y-3 border-t pt-3 text-sm sm:grid-cols-2">
        <LinkDetail label="Displayed value" value={link.displayed_value} />
        <LinkDetail label="Sanitized target" value={link.sanitized_target} wrap />
        <LinkDetail label="Reason code" value={link.reason_code} />
        <LinkDetail label="Source" value={`${link.source_location}${link.source_page ? ` · page ${link.source_page}` : ""}`} />
        <LinkDetail label="Terminal status" value={link.terminal_status ? String(link.terminal_status) : null} />
        <LinkDetail label="Terminal domain" value={link.terminal_registrable_domain} wrap />
      </dl>
      {link.source_evidence.length ? (
        <p className="mt-3 border-l-2 pl-2 text-xs leading-relaxed text-muted-foreground">
          Source evidence: “{link.source_evidence[0].excerpt}”
        </p>
      ) : null}
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        Review the declaration and its source in the CV. This outcome is not proof of a candidate problem.
      </p>
    </HoverDisclosure>
  );
}

function LinkDetail({ label, value, wrap = false }: { label: string; value: string | null; wrap?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className={wrap ? "mt-0.5 break-words leading-relaxed" : "mt-0.5 leading-relaxed"}>
        {value || <UnavailableValue />}
      </dd>
    </div>
  );
}
