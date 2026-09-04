"use client";

import { useEffect, useState } from "react";
import { ReceiptText } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy } from "@/lib/app-settings";
import type { UsageTotals } from "@/lib/usage-types";
import { useAutoResearchState } from "@/lib/use-auto-research";

function compactCost(value: string | null, currency: "USD" | "PLN", locale: string) {
  if (value === null) return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  const absolute = Math.abs(amount);
  const maximumFractionDigits = absolute > 0 && absolute < 0.01 ? 6 : absolute < 1 ? 4 : 2;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits,
  }).format(amount);
}

export function ReportAiCost({ analysisId }: { analysisId: string }) {
  const { settings } = useCopy();
  const company = useAutoResearchState(analysisId, "company");
  const education = useAutoResearchState(analysisId, "education");
  const linkedin = useAutoResearchState(analysisId, "linkedin");
  const [usage, setUsage] = useState<UsageTotals | null>(null);
  const [failed, setFailed] = useState(false);
  const locale = settings.uiLanguage === "pl" ? "pl-PL" : "en-US";

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/analyses/${encodeURIComponent(analysisId)}/usage`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error(`report_usage_${response.status}`);
        return response.json() as Promise<UsageTotals>;
      })
      .then((value) => {
        setUsage(value);
        setFailed(false);
      })
      .catch((cause) => {
        if ((cause as Error).name !== "AbortError") setFailed(true);
      });
    return () => controller.abort();
  }, [analysisId, company?.status, education?.status, linkedin?.status]);

  const label = settings.uiLanguage === "pl" ? "Szacowany koszt AI raportu" : "Estimated report AI cost";
  const usd = usage ? compactCost(usage.estimated_cost_usd, "USD", locale) : "…";
  const pln = usage ? compactCost(usage.estimated_cost_pln, "PLN", locale) : "…";

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            aria-label={label}
            className="inline-flex max-w-full items-center gap-1.5 rounded-md border bg-muted/25 px-2 py-1 text-xs text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ReceiptText className="size-3.5 shrink-0" />
            <span className="truncate tabular-nums">{failed ? `${label}: —` : `${usd} · ${pln}`}</span>
          </span>
        }
      />
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}
