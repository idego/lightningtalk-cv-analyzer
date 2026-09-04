"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { updateAppSettings, useCopy, type AppLanguage, type CopyKey } from "@/lib/app-settings";

type Capability = { ready: boolean; version?: string | null; recovery?: string | null };
type Health = { status: string; ready: boolean; capabilities: Record<string, Capability> };
type RefreshFeedback = "idle" | "refreshing" | "updated";

const capabilityLabels: Record<string, CopyKey> = {
  database: "database", geonames: "geoNamesResolver", postal_reference_data: "postalReferenceData", base_analysis: "baseAnalysis",
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
  const [retentionCanManage, setRetentionCanManage] = useState(false);
  const [retentionConfirmOpen, setRetentionConfirmOpen] = useState(false);
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
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
        const body = await response.json() as { days: number; canManage?: boolean };
        setRetentionDays(String(body.days));
        setRetentionCanManage(body.canManage === true);
      })
      .catch(() => setRetentionMessage(t("retentionUnavailable")))
      .finally(() => setRetentionLoading(false));
  }, [t]);

  function requestRetentionSave() {
    const days = Number(retentionDays);
    if (!Number.isInteger(days) || days < 1 || days > 3650) {
      setRetentionMessage(t("enterWholeNumber"));
      return;
    }
    if (!retentionCanManage) {
      setRetentionMessage(t("retentionOwnerOnly"));
      return;
    }
    setRetentionMessage(null);
    setRetentionConfirmOpen(true);
  }

  async function saveRetention() {
    const days = Number(retentionDays);
    setRetentionLoading(true);
    setRetentionMessage(null);
    try {
      const response = await fetch("/api/settings/retention", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ days }),
      });
      setRetentionMessage(response.ok ? t("saved") : t("retentionCouldNotSave"));
    } catch {
      setRetentionMessage(t("retentionCouldNotSave"));
    } finally {
      setRetentionLoading(false);
      setRetentionConfirmOpen(false);
    }
  }

  async function deleteAllAnalyses() {
    setDeletingAll(true);
    try {
      const response = await fetch("/api/analyses", { method: "DELETE" });
      setRetentionMessage(response.ok ? t("allAnalysesDeleted") : t("analysesCouldNotDelete"));
    } catch {
      setRetentionMessage(t("analysesCouldNotDelete"));
    } finally {
      setDeletingAll(false);
      setDeleteAllOpen(false);
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
      <p className="mt-1 text-sm text-muted-foreground">{t("retentionGlobalDescription")}</p>
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <label htmlFor="retention-days">{t("keepFor")}</label>
        <input id="retention-days" type="number" min={1} max={3650} value={retentionDays} disabled={retentionLoading || !retentionCanManage} onChange={(event) => setRetentionDays(event.target.value)} className="h-10 w-24 rounded-md border bg-background px-3 disabled:cursor-not-allowed disabled:opacity-60" />
        <span>{t("days")}</span>
        <Button variant="outline" onClick={requestRetentionSave} disabled={retentionLoading || !retentionCanManage}>{t("save")}</Button>
      </div>
      {!retentionLoading && !retentionCanManage ? <p className="mt-2 text-xs text-muted-foreground">{t("retentionOwnerOnly")}</p> : null}
      <div className="mt-5 border-t pt-5"><Button variant="outline" className="text-destructive hover:text-destructive" disabled={deletingAll} onClick={() => setDeleteAllOpen(true)}><Trash2 />{t("deleteAll")}</Button></div>
      {retentionMessage ? <p className="mt-3 text-sm text-muted-foreground">{retentionMessage}</p> : null}
      <Dialog open={retentionConfirmOpen} onOpenChange={(open) => { if (!retentionLoading) setRetentionConfirmOpen(open); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("confirmRetentionChange")}</DialogTitle>
            <DialogDescription>{t("retentionGlobalConfirm", { days: retentionDays })}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={retentionLoading} onClick={() => setRetentionConfirmOpen(false)}>{t("cancel")}</Button>
            <Button disabled={retentionLoading} onClick={() => void saveRetention()}>{t("save")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={deleteAllOpen} onOpenChange={(open) => { if (!deletingAll) setDeleteAllOpen(open); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("deleteAll")}</DialogTitle>
            <DialogDescription>{t("deleteAllDescription")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={deletingAll} onClick={() => setDeleteAllOpen(false)}>{t("cancel")}</Button>
            <Button variant="destructive" disabled={deletingAll} onClick={() => void deleteAllAnalyses()}><Trash2 />{t(deletingAll ? "deleting" : "confirmDeleteAll")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
