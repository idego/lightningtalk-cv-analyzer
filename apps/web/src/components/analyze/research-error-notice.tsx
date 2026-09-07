"use client";

import { useState } from "react";
import { Copy } from "lucide-react";
import type { AutoResearchState } from "@/lib/auto-research";
import { formatResearchError, researchErrorDescription } from "@/lib/research-error-details";
import { useCopy } from "@/lib/app-settings";
import { Button } from "@/components/ui/button";

export function ResearchErrorNotice({ state }: { state?: AutoResearchState }) {
  const { settings, t } = useCopy();
  const [copied, setCopied] = useState<string | null>(null);
  const [copyFailed, setCopyFailed] = useState(false);
  if (state?.status === "manual-action") return <p className="text-sm text-muted-foreground">{t("automaticResearchAlreadyAttempted")}</p>;
  if (state?.status !== "failed") return null;
  const pl = settings.uiLanguage === "pl";
  const details = state.diagnostics;
  const text = details ? formatResearchError(details) : "";
  return <div role="alert" className="space-y-2 rounded-lg border border-destructive/25 bg-destructive/5 p-3 text-sm">
    <p className="text-destructive">{details ? researchErrorDescription(details, settings.uiLanguage) : t("automaticResearchFailed")}</p>
    {details ? <>
      <details><summary className="cursor-pointer text-xs font-medium">{pl ? "Szczegóły błędu" : "Error details"}</summary>
        <pre className="mt-2 select-text whitespace-pre-wrap break-all text-xs">{text}</pre>
      </details>
      <Button variant="outline" size="sm" onClick={async () => {
        try { await navigator.clipboard.writeText(text); setCopied(text); setCopyFailed(false); }
        catch { setCopyFailed(true); }
      }}><Copy />{copied === text ? (pl ? "Skopiowano" : "Copied") : (pl ? "Kopiuj szczegóły błędu" : "Copy error details")}</Button>
      {copyFailed ? <p role="status" className="text-xs">{pl ? "Rozwiń szczegóły i skopiuj je ręcznie." : "Expand the details and copy them manually."}</p> : null}
    </> : null}
  </div>;
}
