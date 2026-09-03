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
import { type AppLanguage, useCopy } from "@/lib/app-settings";

type DeploymentUsageSummary = {
  reports_processed: number;
  total_tokens: number;
  input_tokens: number;
  cached_input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: string;
  estimated_cost_pln: string;
  average_tokens_per_report: number;
  average_estimated_cost_usd: string;
  average_estimated_cost_pln: string;
  fx_rate: string;
  by_operation: Record<string, {
    calls: number;
    tokens: number;
    estimated_cost_usd: string;
  }>;
};

const DASHBOARD_CURRENCY_STORAGE_KEY = "cv-analyzer-dashboard-currency";

const labels: Record<AppLanguage, {
  eyebrow: string;
  title: string;
  description: string;
  reports: string;
  tokenMetric: string;
  total: string;
  average: string;
  cost: string;
  totalTokens: string;
  input: string;
  cached: string;
  output: string;
  usd: string;
  pln: string;
  avgTokens: string;
  avgCost: string;
  perCompletedReport: string;
  breakdownTitle: string;
  breakdownDescription: string;
  tableOp: string;
  tableCalls: string;
  tableTokens: string;
  tableCost: string;
  noUsage: string;
  loadError: string;
  accountingNote: string;
}> = {
  en: {
    eyebrow: "Deployment health",
    title: "AI Usage",
    description: "Deployment-wide token consumption and estimated AI provider cost ledgered across completed analyses.",
    reports: "Reports processed",
    tokenMetric: "Tokens",
    total: "Total",
    average: "Average",
    cost: "Estimated cost",
    totalTokens: "Total tokens",
    input: "Prompt",
    cached: "Cached",
    output: "Completion",
    usd: "Estimated cost (USD)",
    pln: "Estimated cost (PLN)",
    avgTokens: "Avg. tokens / report",
    avgCost: "Avg. cost / report",
    perCompletedReport: "Per processed report",
    breakdownTitle: "Usage by operation",
    breakdownDescription: "Detailed consumption grouped by pipeline step across all processed reports.",
    tableOp: "Operation",
    tableCalls: "Calls",
    tableTokens: "Tokens",
    tableCost: "Est. Cost (USD)",
    noUsage: "No AI operations have been ledgered yet.",
    loadError: "Failed to load usage metrics.",
    accountingNote: "Counts and estimates reflect immutable accounting facts ledgered upon successful provider completion. Retained deployment totals survive report deletion and omit personal data. PLN estimates use the configured deployment rate (1 USD = {rate} PLN).",
  },
  pl: {
    eyebrow: "Kondycja wdrożenia",
    title: "Zużycie AI",
    description: "Łączne zużycie tokenów i szacowany koszt dostawców AI zarejestrowane dla przetworzonych analiz.",
    reports: "Przetworzone raporty",
    tokenMetric: "Tokeny",
    total: "Łącznie",
    average: "Średnio",
    cost: "Szacowany koszt",
    totalTokens: "Łącznie tokenów",
    input: "Prompt",
    cached: "Cache",
    output: "Odpowiedź",
    usd: "Szacowany koszt (USD)",
    pln: "Szacowany koszt (PLN)",
    avgTokens: "Śr. tokenów / raport",
    avgCost: "Śr. koszt / raport",
    perCompletedReport: "Na przetworzony raport",
    breakdownTitle: "Zużycie według operacji",
    breakdownDescription: "Szczegółowe zużycie z podziałem na etapy analizy dla wszystkich przetworzonych raportów.",
    tableOp: "Operacja",
    tableCalls: "Wywołania",
    tableTokens: "Tokeny",
    tableCost: "Szac. koszt (USD)",
    noUsage: "Nie zarejestrowano jeszcze żadnych operacji AI.",
    loadError: "Nie udało się pobrać statystyk zużycia.",
    accountingNote: "Statystyki odzwierciedlają niezmienne fakty księgowe rejestrowane po udanej odpowiedzi dostawcy. Zachowane sumy przetrwają usunięcie raportów i nie zawierają danych osobowych. Wartości w PLN bazują na kursie wdrożenia (1 USD = {rate} PLN).",
  },
};

function formatNumber(value: number, locale: string, fractionDigits = 0): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits: fractionDigits,
    minimumFractionDigits: fractionDigits,
  }).format(value);
}

function formatCurrency(amount: string | number, currency: "USD" | "PLN", locale: string): string {
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
  const { settings } = useCopy();
  const locale = settings.uiLanguage === "pl" ? "pl-PL" : "en-US";
  const copy = labels[settings.uiLanguage];
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
      {error ? <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{copy.loadError}</div> : null}

      <section className="space-y-4" aria-label={copy.title}>
        <div className="flex w-fit items-center gap-3 py-1">
          <span className="flex size-9 items-center justify-center rounded-md bg-muted text-foreground"><FileCheck2 className="size-4" /></span>
          <div>
            <p className="text-xs font-medium text-muted-foreground">{copy.reports}</p>
            <p className="text-xl font-semibold tracking-tight tabular-nums">{reports}</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <MetricCard
            icon={<Sigma className="size-4" />}
            title={copy.tokenMetric}
            value={displayedTokens}
            action={<MetricSwitch value={tokenMode} onChange={setTokenMode} label={copy.tokenMetric} options={[{ value: "total", label: copy.total }, { value: "average", label: copy.average }]} />}
            detail={tokenMode === "average"
              ? copy.perCompletedReport
              : summary ? <span className="flex flex-wrap gap-x-3 gap-y-1"><span>{copy.input}: {formatNumber(summary.input_tokens, locale)}</span><span>{copy.cached}: {formatNumber(summary.cached_input_tokens, locale)}</span><span>{copy.output}: {formatNumber(summary.output_tokens, locale)}</span></span> : null}
          />
          <MetricCard
            icon={<ReceiptText className="size-4" />}
            title={copy.cost}
            value={displayedCost}
            detail={currency === "PLN" ? `1 USD = ${exchangeRate} PLN` : undefined}
            action={<MetricSwitch value={currency} onChange={selectCurrency} label={copy.cost} options={[{ value: "USD", label: "USD" }, { value: "PLN", label: "PLN" }]} />}
          />
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">{copy.breakdownTitle}</CardTitle>
          <CardDescription>{copy.breakdownDescription}</CardDescription>
        </CardHeader>
        <CardContent>
          {summary && Object.keys(summary.by_operation).length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-xs font-medium text-muted-foreground">
                    <th className="pb-3 pr-4 font-medium">{copy.tableOp}</th>
                    <th className="pb-3 px-4 font-medium text-right">{copy.tableCalls}</th>
                    <th className="pb-3 px-4 font-medium text-right">{copy.tableTokens}</th>
                    <th className="pb-3 pl-4 font-medium text-right">{copy.tableCost}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {Object.entries(summary.by_operation).map(([op, stats]) => (
                    <tr key={op} className="hover:bg-muted/30">
                      <td className="py-3 pr-4 font-mono text-xs">{op}</td>
                      <td className="py-3 px-4 text-right tabular-nums">{formatNumber(stats.calls, locale)}</td>
                      <td className="py-3 px-4 text-right tabular-nums">{formatNumber(stats.tokens, locale)}</td>
                      <td className="py-3 pl-4 text-right tabular-nums">{formatCurrency(stats.estimated_cost_usd, "USD", locale)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : summary ? <p className="px-4 py-6 text-sm text-muted-foreground">{copy.noUsage}</p> : <div className="h-28 animate-pulse bg-muted/20" />}
        </CardContent>
      </Card>
    </div>
  );
}
