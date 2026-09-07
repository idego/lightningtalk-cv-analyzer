"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, Plus, Save, Trash2, Shield, UserRound } from "lucide-react";
import { profileFilename } from "@/components/profile-builder/profile-filename";
import { ProfileDocumentPreview } from "@/components/profile-builder/profile-document-preview";
import { useConfirmation } from "@/components/ui/use-confirmation";
import { Button } from "@/components/ui/button";
import {
  DEFAULT_PROFILE_BUILDER_PREFERENCES,
  DEFAULT_PROFILE_TEMPLATE,
  PROFILE_TEMPLATE_SAMPLE_PROFILE,
    type ProfileBuilderPreferences,
  type ProfileCustomFieldDefinition,
  type ProfileTemplateListItem,
} from "@/components/profile-builder/profile-builder-model";
import {
  deleteCustomField as apiDeleteCustomField,
  getPreferences,
  listCustomFields,
  listTemplates,
  saveCustomField as apiSaveCustomField,
  savePreferences,
} from "@/components/profile-builder/profile-builder-client";

export function ProfileBuilderSettings({ scope = "team", onSaved, onDirtyChange }: {
  scope?: "personal" | "team";
  onSaved?: (preferences: ProfileBuilderPreferences) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const { confirm, confirmationDialog } = useConfirmation();
  const [profileBuilderPreferences, setProfileBuilderPreferences] = useState<ProfileBuilderPreferences>(DEFAULT_PROFILE_BUILDER_PREFERENCES);
  const [profileBuilderMessage, setProfileBuilderMessage] = useState<string | null>(null);
  const [profileBuilderSaving, setProfileBuilderSaving] = useState(false);
  const [customFields, setCustomFields] = useState<ProfileCustomFieldDefinition[]>([]);
  const [customFieldMessage, setCustomFieldMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [fieldBusy, setFieldBusy] = useState<string | null>(null);
  const [lastSaved, setLastSaved] = useState("");
  const [templateOptions, setTemplateOptions] = useState<ProfileTemplateListItem[]>([]);

  useEffect(() => {
    let active = true;
    Promise.all([scope === "personal" ? getPreferences() : Promise.resolve(DEFAULT_PROFILE_BUILDER_PREFERENCES), scope === "team" ? listCustomFields() : Promise.resolve([]), scope === "personal" ? listTemplates() : Promise.resolve([])])
      .then(([preferences, fields, templates]) => {
        if (!active) return;
        setProfileBuilderPreferences(preferences);
        setLastSaved(JSON.stringify(preferences));
        setCustomFields(fields);
        setTemplateOptions(templates);
      })
      .catch(() => { if (active) setLoadError(true); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [attempt, scope]);

  useEffect(() => {
    onDirtyChange?.(!loading && !loadError && JSON.stringify(profileBuilderPreferences) !== lastSaved);
  }, [profileBuilderPreferences, lastSaved, loading, loadError, onDirtyChange]);

  async function saveProfileBuilderPreferences() {
    if (profileBuilderSaving || loading || loadError) return;
    setProfileBuilderSaving(true);
    setProfileBuilderMessage(null);
    try {
      const saved = await savePreferences(profileBuilderPreferences);
      setProfileBuilderPreferences(saved);
      setLastSaved(JSON.stringify(saved));
      setProfileBuilderMessage("Your preferences are saved.");
      onSaved?.(saved);
    } catch {
      setProfileBuilderMessage("Your preferences could not be saved.");
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
    if (fieldBusy) return;
    if (!field.label.trim()) { setCustomFieldMessage("Custom field label is required."); return; }
    setCustomFieldMessage(null);
    setFieldBusy(field.id);
    try {
      const saved = await apiSaveCustomField({ ...field, label: field.label.trim() });
      setCustomFields((current) => current.map((item, itemIndex) => itemIndex === index ? saved : item));
      setCustomFieldMessage(`${saved.label} saved.`);
    } catch {
      setCustomFieldMessage(`${field.label} could not be saved. Check its type, options, and default value.`);
    } finally { setFieldBusy(null); }
  }

  async function deleteCustomField(index: number) {
    const field = customFields[index];
    if (fieldBusy || !await confirm(`Remove ${field.label} for future profiles? Saved profiles keep their existing value.`)) return;
    setFieldBusy(field.id);
    try {
      await apiDeleteCustomField(field.id);
      setCustomFields((current) => current.filter((_, itemIndex) => itemIndex !== index));
      setCustomFieldMessage(`${field.label} removed. Saved profiles keep this field.`);
    } catch {
      setCustomFieldMessage(`${field.label} could not be removed.`);
    } finally { setFieldBusy(null); }
  }

  const previewTemplate = templateOptions.find((item) => item.template.id === profileBuilderPreferences.default_template_id)?.template ?? DEFAULT_PROFILE_TEMPLATE;
  const exampleFilename = profileFilename(profileBuilderPreferences.filename_pattern,
    profileBuilderPreferences.anonymization.hide_first_name ? "" : "Alex",
    profileBuilderPreferences.anonymization.hide_last_name ? "" : "Morgan",
    previewTemplate.name, "pdf");

  const toggle = (id: string, label: string, checked: boolean, onChange: (checked: boolean) => void, disabled = false, description?: string) => (
    <label htmlFor={id} className={`flex items-center justify-between gap-4 py-3 ${disabled ? "text-muted-foreground" : ""}`}>
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {description ? <span className="mt-1 block text-xs text-muted-foreground">{description}</span> : null}
      </span>
      <input id={id} type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} className="size-4 accent-primary" />
    </label>
  );
  if (loading) return <div role="status" className="flex items-center gap-2 rounded-xl border bg-card p-5 text-sm text-muted-foreground"><LoaderCircle className="size-4 animate-spin" />Loading Profile Builder settings…</div>;
  if (loadError) return <div role="alert" className="space-y-3 rounded-xl border bg-card p-5 text-sm"><p>Profile Builder settings could not be loaded. No defaults have been changed.</p><Button variant="outline" onClick={() => { setLoadError(false); setLoading(true); setAttempt((value) => value + 1); }}>Retry settings</Button></div>;

  return <div className="min-w-0 space-y-6" id="profile-builder-settings">{confirmationDialog}
    {scope === "personal" ? <section className="space-y-5">
      <div className="flex items-start gap-3 rounded-lg bg-muted/30 p-3 text-sm">
        <UserRound className="mt-0.5 size-4 shrink-0" aria-hidden />
        <p>Applies to each new profile you generate.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-sm"><span className="font-medium">Template</span>
          <select value={profileBuilderPreferences.default_template_id} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, default_template_id: event.target.value }))} className="h-10 w-full rounded-lg border bg-background px-3">
            <option value="idego-default">IDEGO Default</option>
            {templateOptions.filter((item) => item.template.id !== "idego-default").map((item) => <option key={item.template.id} value={item.template.id}>{item.template.name}</option>)}
          </select>
        </label>
        <label className="space-y-2 text-sm"><span className="font-medium">Dates</span>
          <select value={profileBuilderPreferences.date_format} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, date_format: event.target.value as ProfileBuilderPreferences["date_format"] }))} className="h-10 w-full rounded-lg border bg-background px-3">
            <option value="preserve">Keep dates as written in the CV</option><option value="yyyy-mm">Year and month · 2026-09</option><option value="mm/yyyy">Month and year · 09/2026</option><option value="yyyy">Year only · 2026</option>
          </select>
        </label>
      </div>
      <details className="rounded-lg border p-4"><summary className="cursor-pointer text-sm font-medium">Preview template</summary><div className="mt-3 h-80 min-w-0 overflow-hidden [contain:inline-size]"><ProfileDocumentPreview profile={PROFILE_TEMPLATE_SAMPLE_PROFILE} template={previewTemplate} fillHeight /></div></details>
      <div className="rounded-lg border px-4">
        {toggle("profile-auto-summary", "Add a short summary", profileBuilderPreferences.auto_summary, auto_summary => setProfileBuilderPreferences((current) => ({ ...current, auto_summary })), false, "You can edit it afterwards.")}
        {profileBuilderPreferences.auto_summary ? <label className="mb-4 block space-y-2 text-sm"><span>What should the summary focus on? <span className="text-muted-foreground">(optional)</span></span><textarea rows={2} placeholder="For example: recent projects and leadership experience" value={profileBuilderPreferences.summary_instruction} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, summary_instruction: event.target.value }))} className="w-full rounded-lg border bg-background p-3" /></label> : null}
      </div>
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium"><Shield className="mr-2 inline size-4" aria-hidden />Anonymization</summary>
        <p className="mt-3 text-xs text-muted-foreground">Also check descriptions for names before sharing.</p>
        <div className="mt-3 flex gap-2">{([true, false] as const).map((hide) => <Button key={String(hide)} variant="outline" size="sm" onClick={() => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, hide_first_name: hide, hide_last_name: hide, hide_email: hide, hide_phone: hide, hide_location: hide, hide_linkedin: hide, hide_github: hide, hide_portfolio: hide, hide_other_links: hide, employer_mode: hide ? "hide" : "show", institution_mode: hide ? "hide" : "show" } }))}>{hide ? "Hide all" : "Show all"}</Button>)}</div>
        <div className="grid gap-x-6 sm:grid-cols-2">{([['First name','hide_first_name'],['Last name','hide_last_name'],['Email','hide_email'],['Phone','hide_phone'],['Location','hide_location'],['LinkedIn','hide_linkedin'],['GitHub','hide_github'],['Portfolio','hide_portfolio'],['Other links','hide_other_links']] as const).map(([label,key]) => toggle(`profile-default-${key}`, `Hide ${label.toLowerCase()}`, profileBuilderPreferences.anonymization[key], checked => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, [key]: checked } }))))}
        {toggle("profile-hide-employers", "Hide employer names", profileBuilderPreferences.anonymization.employer_mode === "hide", hide => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, employer_mode: hide ? "hide" : "show" } })))}
        {toggle("profile-hide-institutions", "Hide school and university names", profileBuilderPreferences.anonymization.institution_mode === "hide", hide => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, institution_mode: hide ? "hide" : "show" } })))}
        </div>
      </details>
      <label className="block space-y-2 text-sm"><span className="font-medium">Downloaded file name</span>
        <select value={["{name}-profile", "{name}-{template}", "candidate-profile-{date}"].includes(profileBuilderPreferences.filename_pattern) ? profileBuilderPreferences.filename_pattern : "custom"} onChange={(event) => { if (event.target.value !== "custom") setProfileBuilderPreferences((current) => ({ ...current, filename_pattern: event.target.value })); }} className="h-10 w-full rounded-lg border bg-background px-3">
          <option value="{name}-profile">Candidate name + profile</option><option value="{name}-{template}">Candidate name + template</option><option value="candidate-profile-{date}">Candidate profile + date</option>
          {!["{name}-profile", "{name}-{template}", "candidate-profile-{date}"].includes(profileBuilderPreferences.filename_pattern) ? <option value="custom">Your existing custom name</option> : null}
        </select>
        <span className="block text-xs text-muted-foreground">Example: {exampleFilename}</span>
      </label>
      <details className="rounded-lg border p-4"><summary className="cursor-pointer text-sm font-medium">More options</summary>
        {toggle("profile-aggregate-tech", "List technologies mentioned in work experience", profileBuilderPreferences.aggregate_technologies, aggregate_technologies => setProfileBuilderPreferences((current) => ({ ...current, aggregate_technologies })))}
        <label className="block space-y-2 text-sm"><span>Custom file name</span><input value={profileBuilderPreferences.filename_pattern} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, filename_pattern: event.target.value }))} className="h-10 w-full rounded-lg border bg-background px-3" /><span className="block text-xs text-muted-foreground">Available fields: {'{name}'}, {'{first_name}'}, {'{last_name}'}, {'{template}'}, {'{date}'}.</span></label>
      </details>
      <div className="sticky bottom-0 flex items-center justify-between gap-3 border-t bg-background py-3">
        <p role="status" className="text-sm text-muted-foreground">{profileBuilderMessage ?? (JSON.stringify(profileBuilderPreferences) !== lastSaved ? "Unsaved changes" : "")}</p>
        <Button disabled={profileBuilderSaving || JSON.stringify(profileBuilderPreferences) === lastSaved} onClick={() => void saveProfileBuilderPreferences()}>{profileBuilderSaving ? <LoaderCircle className="animate-spin" /> : <Save />}{profileBuilderSaving ? "Saving…" : "Save my preferences"}</Button>
      </div>
    </section> : <>
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4"><div><h3 className="font-medium">Profile fields for the team</h3><p className="mt-1 text-sm text-muted-foreground">For everyone’s new profiles.</p></div><Button variant="outline" size="sm" disabled={fieldBusy !== null} onClick={addCustomField}><Plus />Add field</Button></div>
      <div className="mt-4 space-y-3">{customFields.length ? customFields.map((field,index) => <div key={field.id} className="rounded-lg border p-3"><div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_110px_auto_auto]"><input aria-label={`Custom field ${index + 1} label`} value={field.label} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,label:event.target.value} : item))} className="h-9 min-w-0 rounded-md border bg-background px-3 text-sm"/><select aria-label={`${field.label} type`} value={field.kind} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,kind:event.target.value as ProfileCustomFieldDefinition["kind"],options:event.target.value === "select" ? item.options : [],default_value:null} : item))} className="h-9 min-w-0 rounded-md border bg-background px-2 text-sm"><option value="text">Text</option><option value="number">Number</option><option value="boolean">Yes / No</option><option value="date">Date</option><option value="select">Select</option></select><Button variant="outline" size="sm" disabled={fieldBusy !== null} onClick={() => void saveCustomField(index)}><Save/>Save</Button><Button variant="ghost" size="icon-sm" disabled={fieldBusy !== null} onClick={() => void deleteCustomField(index)} aria-label={`Delete ${field.label}`}><Trash2/></Button></div>{field.kind === "select" ? <input aria-label={`${field.label} options`} defaultValue={field.options.join(", ")} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,options:event.target.value.split(",").map(v=>v.trim()).filter(Boolean)} : item))} className="mt-2 h-9 w-full rounded-md border bg-background px-3 text-sm" placeholder="Options, comma separated"/> : null}<div className="mt-2 flex items-center gap-2"><span className="text-xs text-muted-foreground">Default</span>{field.kind === "boolean" ? <select aria-label={`${field.label} default value`} value={field.default_value === true ? "true" : field.default_value === false ? "false" : ""} onChange={(event) => setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:event.target.value===""?null:event.target.value==="true"}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"><option value="">—</option><option value="true">Yes</option><option value="false">No</option></select> : field.kind === "select" ? <select aria-label={`${field.label} default value`} value={typeof field.default_value === "string" ? field.default_value : ""} onChange={(event)=>setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:event.target.value||null}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"><option value="">—</option>{field.options.map(option=><option key={option} value={option}>{option}</option>)}</select> : <input aria-label={`${field.label} default value`} type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"} value={field.default_value == null ? "" : String(field.default_value)} onChange={(event)=>setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:field.kind === "number"?(event.target.value===""?null:Number(event.target.value)):(event.target.value||null)}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"/>}</div></div>) : <p className="text-sm text-muted-foreground">No custom fields configured.</p>}</div>{customFieldMessage ? <p role="status" className="mt-3 text-sm text-muted-foreground">{customFieldMessage}</p> : null}
    </section>
    </>}
  </div>;
}
