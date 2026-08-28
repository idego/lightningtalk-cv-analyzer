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
import { useCopy, type CopyKey } from "@/lib/app-settings";

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

const FILE_DETAIL_LABELS: Record<FileDetailField, CopyKey> = {
  author: "author",
  creator: "creator",
  producer: "producer",
  title: "title",
  subject: "subject",
  creation_time: "creationTime",
  modification_time: "modificationTime",
  created: "created",
  modified: "modified",
  last_modifier: "lastModifier",
  revision: "revision",
};

export function FileDetailsDisclosure({ details }: { details?: FileDetails | null }) {
  const { t } = useCopy();
  if (!details) return null;

  return (
    <HoverDisclosure
      className="rounded-md border p-3"
      triggerClassName="min-h-8 text-sm font-medium"
      title={
        <span className="flex min-w-0 items-center gap-2">
          <FileText aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
          <span>{t("fileDetails")}</span>
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
              <dt className="text-xs font-semibold text-muted-foreground">{t(FILE_DETAIL_LABELS[field])}</dt>
              <dd className="mt-0.5 break-words leading-relaxed">
                {detail ? <FileDetailValue detail={detail} /> : <UnavailableValue />}
              </dd>
            </div>
          );
        })}
      </dl>
      <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
        {t("metadataDisclaimer")}
      </p>
    </HoverDisclosure>
  );
}

function FileDetailValue({ detail }: { detail: FileDetail }) {
  if (detail.status !== "available" || !detail.value) return <UnavailableValue />;
  return <span>{detail.value}</span>;
}

function UnavailableValue() {
  const { t } = useCopy();
  return <span className="text-muted-foreground">{t("unavailable")}</span>;
}

export function LinkInspectionPanel({ inspection }: { inspection?: LinkInspection | null }) {
  const { t } = useCopy();
  if (!inspection || !inspection.links.length) return null;

  const suspicious = inspection.links.filter((link) => link.status === "SUSPICIOUS");
  const unavailable = inspection.links.filter((link) => link.status === "UNAVAILABLE");
  const reachable = inspection.links.filter((link) => link.status === "REACHABLE");
  const notChecked = inspection.links.filter((link) => link.status === "NOT_CHECKED");

  return (
    <section aria-label={t("linkInspection")} className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div>
          <h3 className="font-medium">{t("linkInspection")}</h3>
          <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
            {t("documentLinkChecksOnly")}
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {t("inspected", { count: inspection.links.length })}
        </p>
      </div>

      {suspicious.length ? (
        <div className="space-y-2 pt-1" aria-label={t("suspiciousDocumentLinks", { count: suspicious.length })}>
          {suspicious.map((link) => <LinkResultCard key={link.link_id} link={link} />)}
        </div>
      ) : null}

      {unavailable.length ? (
        <div className="space-y-2 pt-1" aria-label={t("unavailableDocumentLinks", { count: unavailable.length })}>
          {unavailable.map((link) => <LinkResultCard key={link.link_id} link={link} />)}
        </div>
      ) : null}

      <p className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t pt-3 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1"><CheckCircle2 aria-hidden="true" className="size-3.5" /> {t("reachable")}: {reachable.length}</span>
        <span>{t("unavailable")}: {unavailable.length}</span>
        {notChecked.length ? <span>{t("notChecked")}: {notChecked.length}</span> : null}
      </p>
    </section>
  );
}

function LinkResultCard({ link }: { link: LinkCheckResult }) {
  const { t } = useCopy();
  const suspicious = link.status === "SUSPICIOUS";
  const statusLabel: LinkOutcomeStatus = suspicious ? "SUSPICIOUS" : "UNAVAILABLE";
  const title = link.title || t("documentLinkNeedsReview");

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
              {link.displayed_value ?? link.sanitized_target ?? t("embeddedHyperlinkTarget")}
            </span>
          </span>
        </span>
      }
      contentClassName="pt-3"
    >
      <dl className="grid gap-x-6 gap-y-3 border-t pt-3 text-sm sm:grid-cols-2">
        <LinkDetail label={t("displayedValue")} value={link.displayed_value} />
        <LinkDetail label={t("sanitizedTarget")} value={link.sanitized_target} wrap />
        <LinkDetail label={t("reasonCode")} value={link.reason_code} />
        <LinkDetail label={t("source")} value={`${link.source_location}${link.source_page ? ` · ${t("page")} ${link.source_page}` : ""}`} />
        <LinkDetail label={t("terminalStatus")} value={link.terminal_status ? String(link.terminal_status) : null} />
        <LinkDetail label={t("terminalDomain")} value={link.terminal_registrable_domain} wrap />
      </dl>
      {link.source_evidence.length ? (
        <p className="mt-3 border-l-2 pl-2 text-xs leading-relaxed text-muted-foreground">
          {t("sourceEvidence")}: “{link.source_evidence[0].excerpt}”
        </p>
      ) : null}
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
        {t("reviewDeclaration")}
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
