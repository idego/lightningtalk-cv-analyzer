"use client";

import { useEffect, useState } from "react";
import { LoaderCircle, Plus, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DEFAULT_PROFILE_BUILDER_PREFERENCES,
  type AnonymizationPolicy,
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

export function ProfileBuilderSettings() {
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
    Promise.all([getPreferences(), listCustomFields(), listTemplates()])
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
  }, [attempt]);

  async function saveProfileBuilderPreferences() {
    if (profileBuilderSaving || loading || loadError) return;
    setProfileBuilderSaving(true);
    setProfileBuilderMessage(null);
    try {
      const saved = await savePreferences(profileBuilderPreferences);
      setProfileBuilderPreferences(saved);
      setLastSaved(JSON.stringify(saved));
      setProfileBuilderMessage("Profile Builder conversion settings saved.");
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
    if (fieldBusy || !window.confirm(`Remove ${field.label} for future profiles? Saved profiles keep their existing value.`)) return;
    setFieldBusy(field.id);
    try {
      await apiDeleteCustomField(field.id);
      setCustomFields((current) => current.filter((_, itemIndex) => itemIndex !== index));
      setCustomFieldMessage(`${field.label} removed. Existing profile snapshots keep their current value.`);
    } catch {
      setCustomFieldMessage(`${field.label} could not be removed.`);
    } finally { setFieldBusy(null); }
  }

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

  return <div className="space-y-6" id="profile-builder-settings">
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4"><div><h3 className="font-medium">Profile Builder conversion settings</h3><p className="mt-1 text-sm text-muted-foreground">Defaults for newly converted profiles. Existing saved profiles stay unchanged.</p></div><Button variant="outline" size="sm" disabled={profileBuilderSaving || JSON.stringify(profileBuilderPreferences) === lastSaved} onClick={() => void saveProfileBuilderPreferences()}>{profileBuilderSaving ? <LoaderCircle className="animate-spin" /> : <Save />}{profileBuilderSaving ? "Saving…" : "Save"}</Button></div>
      <div className="mt-3 divide-y">
        {toggle("profile-auto-summary", "Generate AI Summary automatically", profileBuilderPreferences.auto_summary, auto_summary => setProfileBuilderPreferences((current) => ({ ...current, auto_summary })), false, "Create a short professional summary for each newly converted CV.")}
        {profileBuilderPreferences.auto_summary ? <div className="py-3"><label htmlFor="profile-summary-default" className="text-sm font-medium">Default Summary instruction</label><textarea id="profile-summary-default" rows={3} value={profileBuilderPreferences.summary_instruction} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, summary_instruction: event.target.value }))} className="mt-2 w-full resize-y rounded-lg border bg-background px-3 py-2 text-sm" /></div> : null}
        {toggle("profile-aggregate-tech", "Collect technologies from work experience", profileBuilderPreferences.aggregate_technologies, aggregate_technologies => setProfileBuilderPreferences((current) => ({ ...current, aggregate_technologies })))}
        <div className="grid gap-3 py-3 sm:grid-cols-2"><label className="space-y-1 text-sm"><span className="font-medium">Date format</span><select value={profileBuilderPreferences.date_format} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, date_format: event.target.value as ProfileBuilderPreferences["date_format"] }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="preserve">Preserve source</option><option value="yyyy-mm">YYYY-MM</option><option value="mm/yyyy">MM/YYYY</option><option value="yyyy">YYYY</option></select></label><label className="space-y-1 text-sm"><span className="font-medium">Default template</span><select value={profileBuilderPreferences.default_template_id} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, default_template_id: event.target.value }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="idego-default">IDEGO Default</option>{templateOptions.filter((item) => item.template.id !== "idego-default").map((item) => <option key={item.template.id} value={item.template.id}>{item.template.name}{item.template.visibility === "shared" ? " · shared" : " · private"}</option>)}</select></label></div>
        <div className="py-3"><label htmlFor="profile-filename-pattern" className="text-sm font-medium">Output filename pattern</label><input id="profile-filename-pattern" value={profileBuilderPreferences.filename_pattern} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, filename_pattern: event.target.value }))} className="mt-2 h-10 w-full rounded-md border bg-background px-3 text-sm" /><p className="mt-1 text-xs text-muted-foreground">Use {'{name}'}, {'{first_name}'}, {'{last_name}'}, {'{template}'}, {'{date}'}. Name placeholders use the document’s visibility settings.</p></div>
        <div className="py-3"><p className="mb-1 text-sm font-medium">Default anonymization</p><div className="grid gap-x-6 sm:grid-cols-2">{([['First name','hide_first_name'],['Last name','hide_last_name'],['Email','hide_email'],['Phone','hide_phone'],['Location','hide_location'],['LinkedIn','hide_linkedin'],['GitHub','hide_github'],['Portfolio','hide_portfolio'],['Other links','hide_other_links']] as const).map(([label,key]) => toggle(`profile-default-${key}`, `Hide ${label}`, profileBuilderPreferences.anonymization[key], checked => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, [key]: checked } }))))}</div><div className="grid gap-3 sm:grid-cols-2"><label className="space-y-1 text-sm"><span>Employer names</span><select value={profileBuilderPreferences.anonymization.employer_mode} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, employer_mode: event.target.value as AnonymizationPolicy["employer_mode"] } }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="show">Show</option><option value="hide">Hide</option></select></label><label className="space-y-1 text-sm"><span>Institution names</span><select value={profileBuilderPreferences.anonymization.institution_mode} onChange={(event) => setProfileBuilderPreferences((current) => ({ ...current, anonymization: { ...current.anonymization, institution_mode: event.target.value as AnonymizationPolicy["institution_mode"] } }))} className="h-10 w-full rounded-md border bg-background px-3"><option value="show">Show</option><option value="hide">Hide</option></select></label></div></div>
      </div>{profileBuilderMessage ? <p role="status" className="mt-3 text-sm text-muted-foreground">{profileBuilderMessage}</p> : null}
    </section>
    <section className="rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-4"><div><h3 className="font-medium">Organization custom fields</h3><p className="mt-1 text-sm text-muted-foreground">Additional details available in newly converted profiles. Existing profiles keep their current fields and values.</p></div><Button variant="outline" size="sm" disabled={fieldBusy !== null} onClick={addCustomField}><Plus />Add field</Button></div>
      <div className="mt-4 space-y-3">{customFields.length ? customFields.map((field,index) => <div key={field.id} className="rounded-lg border p-3"><div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_110px_auto_auto]"><input aria-label={`Custom field ${index + 1} label`} value={field.label} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,label:event.target.value} : item))} className="h-9 min-w-0 rounded-md border bg-background px-3 text-sm"/><select aria-label={`${field.label} type`} value={field.kind} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,kind:event.target.value as ProfileCustomFieldDefinition["kind"],options:event.target.value === "select" ? item.options : [],default_value:null} : item))} className="h-9 min-w-0 rounded-md border bg-background px-2 text-sm"><option value="text">Text</option><option value="number">Number</option><option value="boolean">Yes / No</option><option value="date">Date</option><option value="select">Select</option></select><Button variant="outline" size="sm" disabled={fieldBusy !== null} onClick={() => void saveCustomField(index)}><Save/>Save</Button><Button variant="ghost" size="icon-sm" disabled={fieldBusy !== null} onClick={() => void deleteCustomField(index)} aria-label={`Delete ${field.label}`}><Trash2/></Button></div>{field.kind === "select" ? <input aria-label={`${field.label} options`} defaultValue={field.options.join(", ")} onChange={(event) => setCustomFields((current) => current.map((item,i) => i === index ? {...item,options:event.target.value.split(",").map(v=>v.trim()).filter(Boolean)} : item))} className="mt-2 h-9 w-full rounded-md border bg-background px-3 text-sm" placeholder="Options, comma separated"/> : null}<div className="mt-2 flex items-center gap-2"><span className="text-xs text-muted-foreground">Default</span>{field.kind === "boolean" ? <select aria-label={`${field.label} default value`} value={field.default_value === true ? "true" : field.default_value === false ? "false" : ""} onChange={(event) => setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:event.target.value===""?null:event.target.value==="true"}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"><option value="">—</option><option value="true">Yes</option><option value="false">No</option></select> : field.kind === "select" ? <select aria-label={`${field.label} default value`} value={typeof field.default_value === "string" ? field.default_value : ""} onChange={(event)=>setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:event.target.value||null}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"><option value="">—</option>{field.options.map(option=><option key={option} value={option}>{option}</option>)}</select> : <input aria-label={`${field.label} default value`} type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"} value={field.default_value == null ? "" : String(field.default_value)} onChange={(event)=>setCustomFields((current)=>current.map((item,i)=>i===index?{...item,default_value:field.kind === "number"?(event.target.value===""?null:Number(event.target.value)):(event.target.value||null)}:item))} className="h-8 rounded-md border bg-background px-2 text-sm"/>}</div></div>) : <p className="text-sm text-muted-foreground">No custom fields configured.</p>}</div>{customFieldMessage ? <p role="status" className="mt-3 text-sm text-muted-foreground">{customFieldMessage}</p> : null}
    </section>
  </div>;
}
