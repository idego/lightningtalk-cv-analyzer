"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { updateAppSettings, useCopy, type AppLanguage, type CopyKey } from "@/lib/app-settings";

type Capability = { ready: boolean; version?: string | null; recovery?: string | null };
type Health = { status: string; ready: boolean; capabilities: Record<string, Capability> };
type RefreshFeedback = "idle" | "refreshing" | "updated";

const capabilityLabels: Record<string, CopyKey> = {
  database: "database", geonames: "geoNamesResolver", base_analysis: "baseAnalysis",
  company_research: "companyResearch", education_research: "educationResearch", linkedin_research: "linkedinResearch",
};

export function SettingsPanel() {
  const { settings, t } = useCopy();
  const [health, setHealth] = useState<Health | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshFeedback, setRefreshFeedback] = useState<RefreshFeedback>("idle");
  const [retentionDays, setRetentionDays] = useState("90");
  const [retentionLoading, setRetentionLoading] = useState(true);
  const [retentionMessage, setRetentionMessage] = useState<string | null>(null);
  const [confirmDeleteAll, setConfirmDeleteAll] = useState(false);
  const [deletingAll, setDeletingAll] = useState(false);

  const refresh = useCallback(async (showFeedback = true) => {
    const startedAt = Date.now();
    if (showFeedback) setRefreshFeedback("refreshing");
    setLoading(true);
    try {
      const response = await fetch("/api/health", { cache: "no-store" });
      setHealth(await response.json());
    } catch {
      setHealth({ status: "unavailable", ready: false, capabilities: {} });
    } finally {
      if (showFeedback) {
        const remainingFeedbackTime = Math.max(0, 500 - (Date.now() - startedAt));
        await new Promise((resolve) => window.setTimeout(resolve, remainingFeedbackTime));
        setRefreshFeedback("updated");
      }
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(false); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  useEffect(() => {
    if (refreshFeedback !== "updated") return;
    const timer = window.setTimeout(() => setRefreshFeedback("idle"), 1800);
    return () => window.clearTimeout(timer);
  }, [refreshFeedback]);
  useEffect(() => {
    void fetch("/api/settings/retention", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("retention_unavailable");
        const body = await response.json() as { days: number };
        setRetentionDays(String(body.days));
      })
      .catch(() => setRetentionMessage(t("retentionUnavailable")))
      .finally(() => setRetentionLoading(false));
  }, [t]);

  async function saveRetention() {
    const days = Number(retentionDays);
    if (!Number.isInteger(days) || days < 1 || days > 3650) {
      setRetentionMessage(t("enterWholeNumber"));
      return;
    }
    setRetentionLoading(true);
    setRetentionMessage(null);
    const response = await fetch("/api/settings/retention", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ days }),
    });
    setRetentionLoading(false);
    setRetentionMessage(response.ok ? t("saved") : t("retentionCouldNotSave"));
  }

  async function deleteAllAnalyses() {
    if (!confirmDeleteAll) {
      setConfirmDeleteAll(true);
      return;
    }
    setDeletingAll(true);
    try {
      const response = await fetch("/api/analyses", { method: "DELETE" });
      setRetentionMessage(response.ok ? t("allAnalysesDeleted") : t("analysesCouldNotDelete"));
    } catch {
      setRetentionMessage(t("analysesCouldNotDelete"));
    } finally {
      setDeletingAll(false);
      setConfirmDeleteAll(false);
    }
  }

  const languageSelect = (value: AppLanguage, onChange: (value: AppLanguage) => void) => (
    <select value={value} onChange={(event) => onChange(event.target.value as AppLanguage)} className="h-10 rounded-md border bg-background px-3 text-sm">
      <option value="en">English</option><option value="pl">Polski</option>
    </select>
  );
  const toggle = (id: string, label: string, checked: boolean, onChange: (checked: boolean) => void, disabled = false, description?: string) => (
    <label htmlFor={id} className={`flex items-center justify-between gap-4 py-3 ${disabled ? "text-muted-foreground" : ""}`}>
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {description ? <span className="mt-1 block text-xs text-muted-foreground">{description}</span> : null}
      </span>
      <input id={id} type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} className="size-4 accent-primary" />
    </label>
  );
  const companyResearchAvailable = health?.capabilities.company_research?.ready === true;
  const educationResearchAvailable = health?.capabilities.education_research?.ready === true;
  const linkedinResearchAvailable = health?.capabilities.linkedin_research?.ready === true;
  const anyResearchAvailable = companyResearchAvailable || educationResearchAvailable || linkedinResearchAvailable;

  return <div className="mx-auto w-full max-w-3xl space-y-8">
    <section className="divide-y rounded-xl border bg-card px-5">
      <div className="flex flex-wrap items-center justify-between gap-4 py-5"><h3 className="font-medium">{t("uiLanguage")}</h3>{languageSelect(settings.uiLanguage, uiLanguage => updateAppSettings({ uiLanguage }))}</div>
      <div className="flex flex-wrap items-center justify-between gap-4 py-5"><div><h3 className="font-medium">{t("reportLanguage")}</h3><p className="text-sm text-muted-foreground">{t("reportLanguageDescription")}</p></div>{languageSelect(settings.reportLanguage, reportLanguage => updateAppSettings({ reportLanguage }))}</div>
    </section>
    <section className="rounded-xl border bg-card p-5">
      <h3 className="font-medium">{t("analysisSettings")}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{t("analysisSettingsDescription")}</p>
      <div className="mt-3 divide-y">
        {toggle("ai-enabled", t("useAiFeatures"), settings.aiEnabled && anyResearchAvailable, aiEnabled => updateAppSettings({ aiEnabled }), !anyResearchAvailable, anyResearchAvailable ? t("useAiFeaturesDescription") : t("aiUnavailable"))}
        {toggle("preview-findings-on-hover", t("previewFindingsOnHover"), settings.previewFindingsOnHover, previewFindingsOnHover => updateAppSettings({ previewFindingsOnHover }))}
        {toggle("expand-sections-by-default", t("expandSectionsByDefault"), settings.expandSectionsByDefault, expandSectionsByDefault => updateAppSettings({ expandSectionsByDefault }))}
        {settings.aiEnabled && anyResearchAvailable ? <>
        {toggle("auto-research", t("runResearchAutomatically"), settings.autoResearchEnabled && anyResearchAvailable, autoResearchEnabled => updateAppSettings({ autoResearchEnabled }), !anyResearchAvailable)}
        <div className="pl-4">
          {toggle("auto-company", t("companyResearch"), settings.autoCompanyResearch && companyResearchAvailable, autoCompanyResearch => updateAppSettings({ autoCompanyResearch }), !settings.autoResearchEnabled || !companyResearchAvailable)}
          {toggle("auto-education", t("educationResearch"), settings.autoEducationResearch && educationResearchAvailable, autoEducationResearch => updateAppSettings({ autoEducationResearch }), !settings.autoResearchEnabled || !educationResearchAvailable)}
          {toggle("auto-linkedin", t("linkedinDiscovery"), settings.autoLinkedinDiscovery && linkedinResearchAvailable, autoLinkedinDiscovery => updateAppSettings({ autoLinkedinDiscovery }), !settings.autoResearchEnabled || !linkedinResearchAvailable)}
        </div>
        </> : null}
      </div>
      {settings.aiEnabled && anyResearchAvailable ? <p className="mt-3 text-xs text-muted-foreground">{t("linkedinDiscoveryDescription")}</p> : null}
    </section>
    <section className="rounded-xl border bg-card p-5">
      <h3 className="font-medium">{t("dataRetention")}</h3>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <label htmlFor="retention-days">{t("keepFor")}</label>
        <input id="retention-days" type="number" min={1} max={3650} value={retentionDays} onChange={(event) => setRetentionDays(event.target.value)} className="h-10 w-24 rounded-md border bg-background px-3" />
        <span>{t("days")}</span>
        <Button variant="outline" onClick={() => void saveRetention()} disabled={retentionLoading}>{t("save")}</Button>
      </div>
      <div className="mt-5 border-t pt-5"><Button variant={confirmDeleteAll ? "destructive" : "outline"} className={confirmDeleteAll ? undefined : "text-destructive hover:text-destructive"} disabled={deletingAll} onBlur={() => setConfirmDeleteAll(false)} onKeyDown={(event) => { if (event.key === "Escape") setConfirmDeleteAll(false); }} onClick={() => void deleteAllAnalyses()}><Trash2 />{t(deletingAll ? "deleting" : confirmDeleteAll ? "confirmDeleteAll" : "deleteAll")}</Button></div>
      {retentionMessage ? <p className="mt-3 text-sm text-muted-foreground">{retentionMessage}</p> : null}
    </section>
    <section className="rounded-xl border bg-card p-5">
      <div className="mb-4 flex items-center justify-between gap-4"><h3 className="font-medium">{t("health")}</h3><Button variant="outline" size="sm" onClick={() => void refresh()} disabled={loading}><RefreshCw className={loading ? "animate-spin" : ""} />{t(refreshFeedback === "refreshing" ? "refreshing" : refreshFeedback === "updated" ? "updated" : "refresh")}</Button></div>
      <div className={`mb-3 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${health?.ready ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-amber-500/10 text-amber-800 dark:text-amber-200"}`}>{health?.ready ? <CheckCircle2 className="size-4" /> : <CircleAlert className="size-4" />}{health?.ready ? t("ready") : t("degraded")}</div>
      <div className="divide-y">
        {Object.entries(health?.capabilities ?? {}).map(([name, capability]) => <div key={name} className="flex items-start justify-between gap-4 py-3 text-sm"><div><p className="font-medium">{capabilityLabels[name] ? t(capabilityLabels[name]) : name}</p>{capability.recovery ? <p className="mt-1 text-xs text-muted-foreground">{capability.recovery}</p> : null}</div><div className="flex items-center gap-2 whitespace-nowrap">{capability.version ? <span className="text-xs text-muted-foreground">{capability.version}</span> : null}{capability.ready ? <CheckCircle2 className="size-4 text-emerald-600" /> : <CircleAlert className="size-4 text-amber-600" />}</div></div>)}
        {!loading && !Object.keys(health?.capabilities ?? {}).length ? <p className="py-4 text-sm text-destructive">{t("apiHealthUnavailable")}</p> : null}
      </div>
    </section>
  </div>;
}
