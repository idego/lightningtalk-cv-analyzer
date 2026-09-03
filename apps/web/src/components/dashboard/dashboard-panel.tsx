"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, Coins, FileCheck2, Gauge, ReceiptText, Sigma } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useCopy } from "@/lib/app-settings";
import type { DeploymentUsageSummary } from "@/lib/usage-types";

type DashboardLabels = {
  eyebrow: string;
  title: string;
  description: string;
  reports: string;
  totalTokens: string;
  input: string;
  cached: string;
  output: string;
  usd: string;
  pln: string;
  avgTokens: string;
  avgCost: string;
  perCompletedReport: string;
  operations: string;
  operationsDescription: string;
  operation: string;
  requests: string;
  tokens: string;
  estimatedCost: string;
  accountingNote: string;
  loadError: string;
  noUsage: string;
};

const labels: Record<"en" | "pl", DashboardLabels> = {
  en: {
    eyebrow: "Deployment usage",
    title: "AI usage dashboard",
    description: "Lifetime report throughput and estimated AI spend for this deployment.",
    reports: "Reports processed",
    totalTokens: "Total tokens",
    input: "Input",
    cached: "Cached input",
    output: "Output",
    usd: "Estimated cost · USD",
    pln: "Estimated cost · PLN",
    avgTokens: "Average tokens",
    avgCost: "Average estimated cost",
    perCompletedReport: "per completed report",
    operations: "Usage by operation",
    operationsDescription: "Compact accounting breakdown across AI provider request paths.",
    operation: "Operation",
    requests: "Requests",
    tokens: "Tokens",
    estimatedCost: "Estimated cost",
    accountingNote: "Completed base reports are counted once and remain in lifetime totals after report deletion. Costs use the pricing snapshot stored with each event and a fixed 1 USD = {rate} PLN conversion.",
    loadError: "Usage totals could not be loaded.",
    noUsage: "No AI usage has been recorded yet.",
  },
  pl: {
    eyebrow: "Użycie wdrożenia",
    title: "Dashboard użycia AI",
    description: "Łączna liczba raportów i szacowany koszt AI dla tego wdrożenia.",
    reports: "Przetworzone raporty",
    totalTokens: "Łączne tokeny",
    input: "Wejściowe",
    cached: "Wejściowe z cache",
    output: "Wyjściowe",
    usd: "Szacowany koszt · USD",
    pln: "Szacowany koszt · PLN",
    avgTokens: "Średnia tokenów",
    avgCost: "Średni szacowany koszt",
    perCompletedReport: "na ukończony raport",
    operations: "Użycie według operacji",
    operationsDescription: "Zwięzłe rozliczenie ścieżek wywołań dostawcy AI.",
    operation: "Operacja",
    requests: "Wywołania",
    tokens: "Tokeny",
    estimatedCost: "Szacowany koszt",
    accountingNote: "Ukończony raport bazowy jest liczony raz i pozostaje w sumach historycznych po usunięciu raportu. Koszty używają snapshotu cennika zapisanego przy zdarzeniu oraz stałego przelicznika 1 USD = {rate} PLN.",
    loadError: "Nie udało się wczytać danych o użyciu.",
    noUsage: "Nie zarejestrowano jeszcze użycia AI.",
  },
};

function formatNumber(value: number, locale: string, maximumFractionDigits = 0) {
  return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(value);
}

function formatCurrency(value: string | null, currency: "USD" | "PLN", locale: string) {
  if (value === null) return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  const absolute = Math.abs(amount);
  const maximumFractionDigits = absolute > 0 && absolute < 0.01 ? 6 : absolute < 1 ? 4 : 2;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: currency === "PLN" && absolute >= 0.01 ? 2 : 0,
    maximumFractionDigits,
  }).format(amount);
}

function operationLabel(operation: string, locale: "en" | "pl") {
  const known: Record<string, [string, string]> = {
    profile: ["Profile analysis", "Analiza profilu"],
    employment: ["Employment analysis", "Analiza zatrudnienia"],
    education: ["Education analysis", "Analiza edukacji"],
    review: ["Reviewer", "Reviewer"],
    company_research: ["Company research", "Research firmy"],
    education_research: ["Education research", "Research edukacji"],
    linkedin_discovery_research: ["LinkedIn discovery", "Wyszukiwanie LinkedIn"],
  };
  return known[operation]?.[locale === "pl" ? 1 : 0]
    ?? operation.replaceAll("_", " ").replace(/^./, (character) => character.toUpperCase());
}

function MetricCard({
  icon,
  title,
  value,
  detail,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  detail?: React.ReactNode;
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="flex size-7 items-center justify-center rounded-md bg-muted text-foreground">{icon}</span>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold tracking-tight tabular-nums">{value}</p>
        {detail ? <div className="mt-2 text-xs leading-relaxed text-muted-foreground">{detail}</div> : null}
      </CardContent>
    </Card>
  );
}

export function DashboardPanel() {
  const { settings } = useCopy();
  const locale = settings.uiLanguage === "pl" ? "pl-PL" : "en-US";
  const copy = labels[settings.uiLanguage];
  const [summary, setSummary] = useState<DeploymentUsageSummary | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/dashboard/summary", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`usage_summary_${response.status}`);
        return response.json() as Promise<DeploymentUsageSummary>;
      })
      .then((value) => {
        setSummary(value);
        setError(false);
      })
      .catch((cause) => {
        if ((cause as Error).name !== "AbortError") setError(true);
      });
    return () => controller.abort();
  }, []);

  const accountingNote = useMemo(
    () => copy.accountingNote.replace("{rate}", summary?.fx_rate ?? "3.75"),
    [copy.accountingNote, summary?.fx_rate],
  );

  const loadingValue = error ? "—" : summary ? null : "…";
  const reports = loadingValue ?? formatNumber(summary!.reports_processed, locale);
  const tokens = loadingValue ?? formatNumber(summary!.total_tokens, locale);
  const usd = loadingValue ?? formatCurrency(summary!.estimated_cost_usd, "USD", locale);
  const pln = loadingValue ?? formatCurrency(summary!.estimated_cost_pln, "PLN", locale);
  const avgTokens = loadingValue ?? formatNumber(summary!.average_tokens_per_report, locale, 1);
  const avgUsd = loadingValue ?? formatCurrency(summary!.average_estimated_cost_usd, "USD", locale);
  const avgPln = loadingValue ?? formatCurrency(summary!.average_estimated_cost_pln, "PLN", locale);

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <section className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">{copy.eyebrow}</p>
        <h2 className="text-2xl font-semibold tracking-tight">{copy.title}</h2>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">{copy.description}</p>
      </section>

      {error ? <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{copy.loadError}</div> : null}

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label={copy.title}>
        <MetricCard icon={<FileCheck2 className="size-4" />} title={copy.reports} value={reports} />
        <MetricCard
          icon={<Sigma className="size-4" />}
          title={copy.totalTokens}
          value={tokens}
          detail={summary ? <span className="flex flex-wrap gap-x-3 gap-y-1"><span>{copy.input}: {formatNumber(summary.input_tokens, locale)}</span><span>{copy.cached}: {formatNumber(summary.cached_input_tokens, locale)}</span><span>{copy.output}: {formatNumber(summary.output_tokens, locale)}</span></span> : null}
        />
        <MetricCard icon={<ReceiptText className="size-4" />} title={copy.usd} value={usd} />
        <MetricCard icon={<Coins className="size-4" />} title={copy.pln} value={pln} />
        <MetricCard icon={<Gauge className="size-4" />} title={copy.avgTokens} value={avgTokens} detail={copy.perCompletedReport} />
        <MetricCard icon={<Activity className="size-4" />} title={copy.avgCost} value={avgUsd} detail={<><span>{avgPln}</span><span className="mx-1">·</span>{copy.perCompletedReport}</>} />
      </section>

      <Card>
        <CardHeader className="border-b">
          <CardTitle>{copy.operations}</CardTitle>
          <CardDescription>{copy.operationsDescription}</CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          {summary?.operations.length ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-4">{copy.operation}</TableHead>
                  <TableHead className="text-right">{copy.requests}</TableHead>
                  <TableHead className="text-right">{copy.tokens}</TableHead>
                  <TableHead className="pr-4 text-right">{copy.estimatedCost}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {summary.operations.map((operation) => (
                  <TableRow key={operation.key}>
                    <TableCell className="pl-4 font-medium">{operationLabel(operation.key, settings.uiLanguage)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(operation.attempts, locale)}</TableCell>
                    <TableCell className="text-right tabular-nums">{formatNumber(operation.total_tokens, locale)}</TableCell>
                    <TableCell className="pr-4 text-right tabular-nums">
                      <span className="block">{formatCurrency(operation.estimated_cost_usd, "USD", locale)}</span>
                      <span className="block text-xs text-muted-foreground">{formatCurrency(operation.estimated_cost_pln, "PLN", locale)}</span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : summary ? <p className="px-4 py-6 text-sm text-muted-foreground">{copy.noUsage}</p> : <div className="h-28 animate-pulse bg-muted/20" />}
        </CardContent>
      </Card>

      <p className="max-w-4xl text-xs leading-relaxed text-muted-foreground">{accountingNote}</p>
    </div>
  );
}
