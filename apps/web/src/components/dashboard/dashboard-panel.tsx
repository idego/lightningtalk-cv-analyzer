"use client";

import { useEffect, useMemo, useState } from "react";
import {
  FileCheck2,
  ReceiptText,
  Sigma,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useCopy } from "@/lib/app-settings";
import type { DeploymentUsageSummary } from "@/lib/usage-types";

const DASHBOARD_CURRENCY_STORAGE_KEY = "cv-analyzer-dashboard-currency";

function formatNumber(value: number, locale: string, fractionDigits = 0): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
}

function formatCurrency(amount: string | number | null, currency: "USD" | "PLN", locale: string): string {
  if (amount === null) return "—";
  const numeric = typeof amount === "number" ? amount : Number.parseFloat(amount);
  if (Number.isNaN(numeric)) return "—";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: numeric < 1 ? 4 : 2,
    maximumFractionDigits: numeric < 1 ? 4 : 2,
  }).format(numeric);
}

function MetricCard({
  icon,
  title,
  value,
  detail,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  value: React.ReactNode;
  detail?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <Card className="gap-2">
      <CardHeader className="flex flex-row items-center justify-between pb-1">
        <CardTitle className="text-xs font-medium text-muted-foreground flex items-center gap-1.5">
          {icon}
          {title}
        </CardTitle>
        {action ? <div>{action}</div> : null}
      </CardHeader>
      <CardContent className="space-y-1">
        <div className="text-2xl font-semibold tracking-tight tabular-nums">{value}</div>
        {detail ? <div className="text-xs text-muted-foreground">{detail}</div> : null}
      </CardContent>
    </Card>
  );
}

function MetricSwitch<T extends string>({
  value,
  onChange,
  options,
  label,
}: {
  value: T;
  onChange: (value: T) => void;
  options: Array<{ value: T; label: string }>;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex items-center rounded-full border border-border/70 bg-muted/40 p-0.5 text-xs"
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          className={`rounded-full px-2 py-0.5 font-medium transition-colors ${
            value === option.value
              ? "bg-background text-foreground shadow-xs"
              : "text-muted-foreground hover:text-foreground"
          }`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function DashboardPanel() {
  const { settings, t } = useCopy();
  const locale = settings.uiLanguage === "pl" ? "pl-PL" : "en-US";
  const [summary, setSummary] = useState<DeploymentUsageSummary | null>(null);
  const [error, setError] = useState(false);
  const [tokenMode, setTokenMode] = useState<"total" | "average">("total");
  const [currency, setCurrency] = useState<"USD" | "PLN">("USD");

  useEffect(() => {
    try {
      const storedCurrency = window.localStorage.getItem(DASHBOARD_CURRENCY_STORAGE_KEY);
      if (storedCurrency === "USD" || storedCurrency === "PLN") {
        const timer = window.setTimeout(() => setCurrency(storedCurrency), 0);
        return () => window.clearTimeout(timer);
      }
    } catch { /* Browser storage is optional. */ }
  }, []);

  function selectCurrency(nextCurrency: "USD" | "PLN") {
    setCurrency(nextCurrency);
    try { window.localStorage.setItem(DASHBOARD_CURRENCY_STORAGE_KEY, nextCurrency); } catch { /* Keep the in-memory choice. */ }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/dashboard/summary", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("fetch failed");
        const data = await response.json();
        setSummary(data);
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(true);
      });
    return () => controller.abort();
  }, []);

  const exchangeRate = useMemo(() => summary?.fx_rate ?? "3.75", [summary?.fx_rate]);

  const loadingValue = error ? "—" : summary ? null : "…";
  const reports = loadingValue ?? formatNumber(summary!.reports_processed, locale);
  const totalTokens = loadingValue ?? formatNumber(summary!.total_tokens, locale);
  const usd = loadingValue ?? formatCurrency(summary!.estimated_cost_usd, "USD", locale);
  const pln = loadingValue ?? formatCurrency(summary!.estimated_cost_pln, "PLN", locale);
  const avgTokens = loadingValue ?? formatNumber(summary!.average_tokens_per_report, locale, 1);
  const displayedTokens = tokenMode === "total" ? totalTokens : avgTokens;
  const displayedCost = currency === "USD" ? usd : pln;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      {error ? <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{t("dashboardLoadError")}</div> : null}

      <section className="space-y-4" aria-label={t("dashboardUsageTitle")}>
        <div className="flex w-fit items-center gap-3 py-1">
          <span className="flex size-9 items-center justify-center rounded-md bg-muted text-foreground"><FileCheck2 className="size-4" /></span>
          <div>
            <p className="text-xs font-medium text-muted-foreground">{t("dashboardReportsProcessed")}</p>
            <p className="text-xl font-semibold tracking-tight tabular-nums">{reports}</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <MetricCard
            icon={<Sigma className="size-4" />}
            title={t("dashboardTokens")}
            value={displayedTokens}
            action={<MetricSwitch value={tokenMode} onChange={setTokenMode} label={t("dashboardTokens")} options={[{ value: "total", label: t("dashboardTotal") }, { value: "average", label: t("dashboardAverage") }]} />}
            detail={tokenMode === "average"
              ? t("dashboardPerProcessedReport")
              : summary ? <span className="flex flex-wrap gap-x-3 gap-y-1"><span>{t("dashboardPrompt")}: {formatNumber(summary.input_tokens, locale)}</span><span>{t("dashboardCached")}: {formatNumber(summary.cached_input_tokens, locale)}</span><span>{t("dashboardCompletion")}: {formatNumber(summary.output_tokens, locale)}</span></span> : null}
          />
          <MetricCard
            icon={<ReceiptText className="size-4" />}
            title={t("dashboardEstimatedCost")}
            value={displayedCost}
            detail={currency === "PLN" ? `1 USD = ${exchangeRate} PLN` : undefined}
            action={<MetricSwitch value={currency} onChange={selectCurrency} label={t("dashboardEstimatedCost")} options={[{ value: "USD", label: "USD" }, { value: "PLN", label: "PLN" }]} />}
          />
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("dashboardUsageByOperation")}</CardTitle>
          <CardDescription>{t("dashboardBreakdownDescription")}</CardDescription>
        </CardHeader>
        <CardContent>
          {summary?.operations.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs font-medium text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">{t("dashboardOperation")}</th>
                    <th className="pb-3 px-4 font-medium text-right">{t("dashboardCalls")}</th>
                    <th className="pb-3 px-4 font-medium text-right">{t("dashboardTokens")}</th>
                    <th className="pb-3 pl-4 font-medium text-right">{t("dashboardEstimatedCostUsd")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {summary.operations.map((operation) => (
                    <tr key={operation.key} className="hover:bg-muted/30">
                      <td className="py-3 pr-4 font-mono text-xs">{operation.key}</td>
                      <td className="py-3 px-4 text-right tabular-nums">{formatNumber(operation.attempts, locale)}</td>
                      <td className="py-3 px-4 text-right tabular-nums">{formatNumber(operation.total_tokens, locale)}</td>
                      <td className="py-3 pl-4 text-right tabular-nums">{formatCurrency(operation.estimated_cost_usd, "USD", locale)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : summary ? <p className="px-4 py-6 text-sm text-muted-foreground">{t("dashboardNoUsage")}</p> : <div className="h-28 animate-pulse bg-muted/20" />}
        </CardContent>
      </Card>
    </div>
  );
}
