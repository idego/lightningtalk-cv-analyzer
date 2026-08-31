"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { updateAppSettings, useCopy, type AppLanguage, type CopyKey } from "@/lib/app-settings";

type Capability = { ready: boolean; version?: string | null; recovery?: string | null };
type Health = { status: string; ready: boolean; capabilities: Record<string, Capability> };
type RefreshFeedback = "idle" | "refreshing" | "updated";

type ProfileAnonymizationPolicy = {
  hide_first_name: boolean; hide_last_name: boolean; hide_email: boolean; hide_phone: boolean;
  hide_location: boolean; hide_linkedin: boolean; hide_github: boolean; hide_portfolio: boolean;
  employer_mode: "show" | "hide" | "genericize"; institution_mode: "show" | "hide";
};
type ProfileBuilderPreferences = {
  auto_summary: boolean; summary_instruction: string; anonymization: ProfileAnonymizationPolicy;
  aggregate_technologies: boolean; date_format: "preserve" | "yyyy-mm" | "mm/yyyy" | "yyyy";
  default_template_id: string; filename_pattern: string;
};
type CustomFieldDefinition = {
  id: string; label: string; kind: "text" | "number" | "boolean" | "date" | "select";
  options: string[]; default_value: string | number | boolean | null;
};
type TemplateOption = { template: { id: string; name: string; visibility: "private" | "shared" } };
const DEFAULT_PROFILE_BUILDER_PREFERENCES: ProfileBuilderPreferences = {
  auto_summary: false, summary_instruction: "", aggregate_technologies: true, date_format: "preserve",
  default_template_id: "idego-default", filename_pattern: "{name}-profile",
  anonymization: {
    hide_first_name: true, hide_last_name: true, hide_email: true, hide_phone: true, hide_location: true,
    hide_linkedin: true, hide_github: true, hide_portfolio: true, employer_mode: "hide", institution_mode: "hide",
  },
};

const capabilityLabels: Record<string, CopyKey> = {
  database: "database", geonames: "geoNamesResolver", document_ai: "aiDocumentAnalysis",
  company_research: "companyResearch", education_research: "educationResearch", linkedin_research: "linkedinResearch", link_checks: "linkChecks",
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
  const [profileBuilderPreferences, setProfileBuilderPreferences] = useState<ProfileBuilderPreferences>(DEFAULT_PROFILE_BUILDER_PREFERENCES);
  const [profileBuilderMessage, setProfileBuilderMessage] = useState<string | null>(null);
  const [profileBuilderSaving, setProfileBuilderSaving] = useState(false);
  const [customFields, setCustomFields] = useState<CustomFieldDefinition[]>([]);
  const [customFieldMessage, setCustomFieldMessage] = useState<string | null>(null);
  const [templateOptions, setTemplateOptions] = useState<TemplateOption[]>([]);

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

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void Promise.all([
        fetch("/api/profile-builder/preferences", { cache: "no-store" })
          .then(async (response) => { if (!response.ok) throw new Error(); setProfileBuilderPreferences(await response.json() as ProfileBuilderPreferences); })
          .catch(() => setProfileBuilderPreferences(DEFAULT_PROFILE_BUILDER_PREFERENCES)),
        fetch("/api/profile-builder/custom-fields", { cache: "no-store" })
          .then(async (response) => { if (!response.ok) throw new Error(); const body = await response.json() as { fields?: CustomFieldDefinition[] }; setCustomFields(body.fields ?? []); })
          .catch(() => setCustomFieldMessage("Custom fields are unavailable.")),
        fetch("/api/profile-builder/templates", { cache: "no-store" })
          .then(async (response) => { if (!response.ok) throw new Error(); const body = await response.json() as { templates?: TemplateOption[] }; setTemplateOptions(body.templates ?? []); })
          .catch(() => setTemplateOptions([])),
      ]);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  async function saveProfileBuilderPreferences() {
    setProfileBuilderSaving(true);
    setProfileBuilderMessage(null);
    try {
      const response = await fetch("/api/profile-builder/preferences", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profileBuilderPreferences),
      });
      if (response.ok) {
        window.localStorage.setItem("cv-profile-builder-selected-template-v1", profileBuilderPreferences.default_template_id);
      }
      setProfileBuilderMessage(response.ok ? "Profile Builder conversion settings saved." : "Conversion settings could not be saved.");
    } catch {
      setProfileBuilderMessage("Conversion settings could not be saved.");
    } finally {
      setProfileBuilderSaving(false);
    }
  }

  function addCustomField() {
    setCustomFields((current) => [...current, {
      id: `field-${globalThis.crypto.randomUUID()}`,
      label: "New field",
      kind: "text",
      options: [],
      default_value: null,
    }]);
  }

  async function saveCustomField(index: number) {
    const field = customFields[index];
    if (!field.label.trim()) { setCustomFieldMessage("Custom field label is required."); return; }
    setCustomFieldMessage(null);
    const response = await fetch(`/api/profile-builder/custom-fields/${encodeURIComponent(field.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...field, label: field.label.trim() }),
    });
    setCustomFieldMessage(response.ok ? `${field.label} saved.` : `${field.label} could not be saved.`);
  }

  async function deleteCustomField(index: number) {
    const field = customFields[index];
    const response = await fetch(`/api/profile-builder/custom-fields/${encodeURIComponent(field.id)}`, { method: "DELETE" });
    if (response.ok || response.status === 404) {
      setCustomFields((current) => current.filter((_, itemIndex) => itemIndex !== index));
      setCustomFieldMessage(`${field.label} removed. Existing profile snapshots keep their current value.`);
    } else setCustomFieldMessage(`${field.label} could not be removed.`);
  }

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
  const serverAiAvailable = health?.capabilities.document_ai?.ready === true;

  return <div className="mx-auto w-full max-w-3xl space-y-8">
    <section className="divide-y rounded-xl border bg-card px-5">
      <div className="flex flex-wrap items-center justify-between gap-4 py-5"><h3 className="font-medium">{t("uiLanguage")}</h3>{languageSelect(settings.uiLanguage, uiLanguage => updateAppSettings({ uiLanguage }))}</div>
      <div className="flex flex-wrap items-center justify-between gap-4 py-5"><div><h3 className="font-medium">{t("reportLanguage")}</h3><p className="text-sm text-muted-foreground">{t("reportLanguageDescription")}</p></div>{languageSelect(settings.reportLanguage, reportLanguage => updateAppSettings({ reportLanguage }))}</div>
    </section>
    <section className="rounded-xl border bg-card p-5">
      <h3 className="font-medium">{t("analysisSettings")}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{t("analysisSettingsDescription")}</p>
      <div className="mt-3 divide-y">
        {toggle("ai-enabled", t("useAiFeatures"), settings.aiEnabled && serverAiAvailable, aiEnabled => updateAppSettings({ aiEnabled }), !serverAiAvailable, serverAiAvailable ? t("useAiFeaturesDescription") : t("aiUnavailable"))}
        {toggle("preview-findings-on-hover", t("previewFindingsOnHover"), settings.previewFindingsOnHover, previewFindingsOnHover => updateAppSettings({ previewFindingsOnHover }))}
        {toggle("expand-sections-by-default", t("expandSectionsByDefault"), settings.expandSectionsByDefault, expandSectionsByDefault => updateAppSettings({ expandSectionsByDefault }))}
        {settings.aiEnabled && serverAiAvailable ? <>
        {toggle("auto-research", t("runResearchAutomatically"), settings.autoResearchEnabled, autoResearchEnabled => updateAppSettings({ autoResearchEnabled }))}
        <div className="pl-4">
          {toggle("auto-company", t("companyResearch"), settings.autoCompanyResearch, autoCompanyResearch => updateAppSettings({ autoCompanyResearch }), !settings.autoResearchEnabled)}
          {toggle("auto-education", t("educationResearch"), settings.autoEducationResearch, autoEducationResearch => updateAppSettings({ autoEducationResearch }), !settings.autoResearchEnabled)}
          {toggle("auto-linkedin", t("linkedinDiscovery"), settings.autoLinkedinDiscovery, autoLinkedinDiscovery => updateAppSettings({ autoLinkedinDiscovery }), !settings.autoResearchEnabled)}
        </div>
        </> : null}
      </div>
      {settings.aiEnabled && serverAiAvailable ? <p className="mt-3 text-xs text-muted-foreground">{t("linkedinDiscoveryDescription")}</p> : null}
    </section>
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4"><div><h3 className="font-medium">Profile Builder conversion settings</h3><p className="mt-1 text-sm text-muted-foreground">Defaults for newly converted profiles. Existing saved profiles stay unchanged.</p></div><Button variant="outline" size="sm" disabled={profileBuilderSaving} onClick={() => void saveProfileBuilderPreferences()}><Save />Save</Button></div>
      <div className="mt-3 divide-y">
        {toggle("profile-auto-summary", "Generate AI Summary automatically", profileBuilderPreferences.auto_summary, auto_summary => setProfileBuilderPreferences((current) => ({ ...current, auto_summary })), !settings.aiEnabled || !serverAiAvailable, "GPT-5.6 Luna, reasoning disabled.")}
        {profileBuilderPreferences.auto_summary ? <div className="py-3"><label htmlFor="profile-summary-default" className="text-sm font-medium">Default Summary instruction</label><textarea id="profile-summary-default" rows={3} value={profileBuilderPreferences.summary_instruction} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, summary_instruction: event.target.value }))} className="mt-2 w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm" /></div> : null}
        {toggle("profile-aggregate-tech", "Aggregate technologies", profileBuilderPreferences.aggregate_technologies, aggregate_technologies => setProfileBuilderPreferences((current) => ({ ...current, aggregate_technologies })))}
        <div className="grid gap-3 py-3 sm:grid-cols-2"><label className="space-y-1 text-sm"><span className="font-medium">Date format</span><select value={profileBuilderPreferences.date_format} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, date_format: event.target.value as ProfileBuilderPreferences["date_format"] }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="preserve">Preserve source</option><option value="yyyy-mm">YYYY-MM</option><option value="mm/yyyy">MM/YYYY</option><option value="yyyy">YYYY</option></select></label><label className="space-y-1 text-sm"><span className="font-medium">Default template</span><select value={profileBuilderPreferences.default_template_id} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, default_template_id: event.target.value }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="idego-default">IDEGO Default</option>{templateOptions.filter((item) => item.template.id !== "idego-default").map((item) => <option key={item.template.id} value={item.template.id}>{item.template.name}{item.template.visibility === "shared" ? " · shared" : " · private"}</option>)}</select></label></div>
        <div className="py-3"><label htmlFor="profile-filename-pattern" className="text-sm font-medium">Output filename pattern</label><input id="profile-filename-pattern" value={profileBuilderPreferences.filename_pattern} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, filename_pattern: event.target.value }))} className="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm" /><p className="mt-1 text-xs text-muted-foreground">Use {'{name}'}, {'{first_name}'}, {'{last_name}'}, {'{template}'}, {'{date}'}. Hidden identity never leaks into the filename.</p></div>
        <div className="py-3"><p className="mb-1 text-sm font-medium">Default anonymization</p><div className="grid gap-x-6 sm:grid-cols-2">{([['First name','hide_first_name'],['Last name','hide_last_name'],['Email','hide_email'],['Phone','hide_phone'],['Location','hide_location'],['LinkedIn','hide_linkedin'],['GitHub','hide_github'],['Portfolio','hide_portfolio']] as const).map(([label,key]) => toggle(`profile-default-${key}`, `Hide ${label}`, profileBuilderPreferences.anonymization[key], checked => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, [key]: checked } }))))}</div><div className="grid gap-3 sm:grid-cols-2"><label className="space-y-1 text-sm"><span>Employer names</span><select value={profileBuilderPreferences.anonymization.employer_mode} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, employer_mode: event.target.value as ProfileAnonymizationPolicy["employer_mode"] } }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="show">Show</option><option value="hide">Hide</option><option value="genericize">Genericize</option></select></label><label className="space-y-1 text-sm"><span>Institution names</span><select value={profileBuilderPreferences.anonymization.institution_mode} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, institution_mode: event.target.value as ProfileAnonymizationPolicy["institution_mode"] } }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="show">Show</option><option value="hide">Hide</option></select></label></div></div>
      </div>{profileBuilderMessage ? <p className="mt-3 text-sm text-muted-foreground">{profileBuilderMessage}</p> : null}
    </section>
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4"><div><h3 className="font-medium">Organization custom fields</h3><p className="mt-1 text-sm text-muted-foreground">Shared metadata schema for availability, rate, account manager, and similar fields.</p></div><Button variant="outline" size="sm" onClick={addCustomField}><Plus />Add field</Button></div>
      <div className="mt-4 space-y-3">{customFields.length ? customFields.map((field,index) => <div key={field.id} className="rounded-lg border p-3"><div className="grid gap-2 sm:grid-cols-[1fr_150px_auto_auto]"><input aria-label={`Custom field ${index + 1} label`} value={field.label} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,label:event.target.value} : item))} className="h-9 rounded-md border bg-background px-3 text-sm"/><select aria-label={`${field.label} type`} value={field.kind} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,kind:event.target.value as CustomFieldDefinition["kind"],options:event.target.value === "select" ? item.options : [],default_value:null} : item))} className="h-9 rounded-md border bg-background px-2 text-sm"><option value="text">Text</option><option value="number">Number</option><option value="boolean">Yes / No</option><option value="date">Date</option><option value="select">Select</option></select><Button variant="outline" size="sm" onClick={() => void saveCustomField(index)}><Save/>Save</Button><Button variant="ghost" size="icon-sm" onClick={() => void deleteCustomField(index)} aria-label={`Delete ${field.label}`}><Trash2/></Button></div>{field.kind === "select" ? <input aria-label={`${field.label} options`} value={field.options.join(", ")} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,options:event.target.value.split(",").map(v=>v.trim()).filter(Boolean)} : item))} className="mt-2 h-9 w-full rounded-md border bg-background px-3 text-sm" placeholder="Options, comma separated"/> : null}<div className="mt-2 flex items-center gap-2"><span className="text-xs text-muted-foreground">Default</span>{field.kind === "boolean" ? <select value={field.default_value === true ? "true" : field.default_value === false ? "false" : ""} onChange={(event) => setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:event.target.value===""?null:event.target.value==="true"}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"><option value="">—</option><option value="true">Yes</option><option value="false">No</option></select> : field.kind === "select" ? <select value={typeof field.default_value === "string" ? field.default_value : ""} onChange={(event)=>setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:event.target.value||null}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"><option value="">—</option>{field.options.map(option=><option key={option} value={option}>{option}</option>)}</select> : <input type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"} value={field.default_value == null ? "" : String(field.default_value)} onChange={(event)=>setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:field.kind === "number"?(event.target.value===""?null:Number(event.target.value)):(event.target.value||null)}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"/>}</div></div>) : <p className="text-sm text-muted-foreground">No custom fields configured.</p>}</div>{customFieldMessage ? <p className="mt-3 text-sm text-muted-foreground">{customFieldMessage}</p> : null}
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
