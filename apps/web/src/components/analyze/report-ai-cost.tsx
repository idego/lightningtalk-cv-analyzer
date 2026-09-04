"use client";

import { useEffect, useState } from "react";
import { CircleDollarSign } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { useCopy } from "@/lib/app-settings";
import type { UsageTotals } from "@/lib/usage-types";
import { useAutoResearchState } from "@/lib/use-auto-research";

function formatCost(value: string | null, currency: "USD" | "PLN", locale: string, fractionDigits: number) {
  if (value === null) return "—";
  const amount = Number(value);
  if (!Number.isFinite(amount)) return "—";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
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
  const usd = usage ? formatCost(usage.estimated_cost_usd, "USD", locale, 2) : "…";
  const pln = usage ? formatCost(usage.estimated_cost_pln, "PLN", locale, 2) : "…";
  const detailedUsd = usage ? formatCost(usage.estimated_cost_usd, "USD", locale, 5) : "…";
  const detailedPln = usage ? formatCost(usage.estimated_cost_pln, "PLN", locale, 5) : "…";

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            tabIndex={0}
            aria-label={label}
            className="inline-flex max-w-full items-center gap-1.5 rounded-md border bg-muted/25 px-2 py-1 text-xs text-muted-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <CircleDollarSign className="size-3.5 shrink-0" />
            <span className="truncate tabular-nums">{failed ? `${label}: —` : `${usd} · ${pln}`}</span>
          </span>
        }
      />
      <TooltipContent>
        <div className="space-y-0.5">
          <p>{label}</p>
          {!failed ? <p className="tabular-nums text-center">{detailedUsd} · {detailedPln}</p> : null}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
