"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
  ChevronDown,
  Check,
  ChevronUp,
  Download,
  Eye,
  EyeOff,
  History,
  LayoutTemplate,
  LoaderCircle,
  Pencil,
  Plus,
  RotateCcw,
  Sparkles,
  Languages,
  WandSparkles,
  Trash2,
  Upload,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAppSettings } from "@/lib/app-settings";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DEFAULT_ANONYMIZATION,
  DEFAULT_PROFILE_BUILDER_PREFERENCES,
  DEFAULT_PROFILE_TEMPLATE,
  PROFESSIONAL_SECTION_LABELS,
  PROFESSIONAL_SECTIONS,
  REVEALED_ANONYMIZATION,
  derivedPresentation,
  newProfileBuilderId,
  serializeProfileSnapshot,
  type AnonymizationPolicy,
  type CandidateProfile,
  type ProfileBuilderPreferences,
  type ProfileSnapshotPayload,
  type ProfileTemplate,
  type ProfileTemplateListItem,
  type ProfessionalProposal,
  type ProfessionalSectionName,
  type BatchConversionItem,
  type RecentProfileItem,
} from "@/components/profile-builder/profile-builder-model";

import { ProfileDocumentPreview } from "@/components/profile-builder/profile-document-preview";
import {
  ProfileBuilderApiError,
  createProfile as apiCreateProfile,
  deleteProfile as apiDeleteProfile,
  deleteTemplate as apiDeleteTemplate,
  exportProfileSnapshot,
  extractProfile as apiExtractProfile,
  generateProfileSummary,
  getPreferences,
  getProfile as apiGetProfile,
  listProfiles,
  listTemplates,
  savePreferences,
  transformProfile as apiTransformProfile,
  updateProfile as apiUpdateProfile,
} from "@/components/profile-builder/profile-builder-client";

const ACCEPT = ".pdf,.docx";
const PROFILE_BUILDER_MAX_BYTES = 10 * 1024 * 1024;

const EDITOR_SECTIONS = [
  "personal",
  "profile",
  "anonymization",
  "experience",
  "education",
  "languages",
  "certifications",
  "additional",
  "custom_fields",
] as const;
type EditorSectionId = (typeof EDITOR_SECTIONS)[number];

function nonEmptyLines(value: string) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string | null;
  onChange: (value: string | null) => void;
  placeholder?: string;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        value={value ?? ""}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value || null)}
      />
    </div>
  );
}

function TextareaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <textarea
        id={id}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="w-full resize-y rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
      />
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="size-4 accent-[var(--primary)]"
      />
    </label>
  );
}

function TemplateManagerDialog({
  open,
  onOpenChange,
  items,
  selectedTemplate,
  onSelect,
  onDelete,
  onEdit,
  onCreate,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: ProfileTemplateListItem[];
  selectedTemplate: ProfileTemplate;
  onSelect: (template: ProfileTemplate) => void;
  onDelete: (item: ProfileTemplateListItem) => void;
  onEdit: (templateId: string) => void;
  onCreate: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Templates</DialogTitle>
          <DialogDescription>Choose the layout used for preview and export, or open the Template Creator.</DialogDescription>
        </DialogHeader>
        <div className="max-h-[55vh] space-y-2 overflow-y-auto pr-1">
          {items.map((item) => {
            const selected = item.template.id === selectedTemplate.id;
            return <div key={item.template.id} className={`flex items-center gap-3 rounded-xl border p-3 ${selected ? "border-primary/40 bg-primary/5" : ""}`}>
              <button type="button" className="min-w-0 flex-1 text-left" onClick={() => onSelect(item.template)}>
                <span className="flex items-center gap-2"><span className="truncate font-medium">{item.template.name}</span>{selected ? <Check className="size-4 text-primary" /> : null}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{item.template.description || "Custom profile template"}{item.built_in ? item.customized ? " · customized default" : " · built-in" : item.overrides_shared ? " · private override of shared" : item.template.visibility === "shared" ? " · shared" : " · private"}</span>
              </button>
              <Button variant="ghost" size="icon-sm" aria-label={`Edit ${item.template.name}`} onClick={() => onEdit(item.template.id)}><Pencil /></Button>
              {(!item.built_in || item.customized) ? <Button variant="ghost" size="icon-sm" aria-label={item.built_in ? "Reset built-in template" : `Delete ${item.template.name}`} onClick={() => onDelete(item)}><Trash2 /></Button> : null}
            </div>;
          })}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCreate}><Plus />Create template</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function ProfileBuilderWorkspace() {
  const settings = useAppSettings();
  const router = useRouter();
  const searchParams = useSearchParams();
  const reopenProfileId = searchParams.get("profile");
  const [profileId, setProfileId] = useState<string | null>(null);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [sourceFilename, setSourceFilename] = useState<string | null>(null);
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [anonymization, setAnonymization] = useState(DEFAULT_ANONYMIZATION);
  const [selectedTemplate, setSelectedTemplate] = useState<ProfileTemplate>(DEFAULT_PROFILE_TEMPLATE);
  const [templateItems, setTemplateItems] = useState<ProfileTemplateListItem[]>([
    { template: DEFAULT_PROFILE_TEMPLATE, built_in: true, customized: false, created_at: null, updated_at: null },
  ]);
  const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
  const [recentProfiles, setRecentProfiles] = useState<RecentProfileItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [openingProfileId, setOpeningProfileId] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [batchItems, setBatchItems] = useState<BatchConversionItem[]>([]);
  const [batchRunning, setBatchRunning] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [summaryInstruction, setSummaryInstruction] = useState("");
  const [summaryGenerating, setSummaryGenerating] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [profileBuilderPreferences, setProfileBuilderPreferences] = useState<ProfileBuilderPreferences>(DEFAULT_PROFILE_BUILDER_PREFERENCES);
  const [profileBuilderReady, setProfileBuilderReady] = useState(false);
  const [transformDialogOpen, setTransformDialogOpen] = useState(false);
  const [transformMode, setTransformMode] = useState<"action" | "translation">("action");
  const [transformInstruction, setTransformInstruction] = useState("");
  const [transformLanguage, setTransformLanguage] = useState<"en" | "pl" | "de" | "fr" | "es">("en");
  const [transformSections, setTransformSections] = useState<Set<ProfessionalSectionName>>(() => new Set(["summary"]));
  const [transformProposal, setTransformProposal] = useState<ProfessionalProposal | null>(null);
  const [acceptedTransformSections, setAcceptedTransformSections] = useState<Set<ProfessionalSectionName>>(() => new Set());
  const [transformRunning, setTransformRunning] = useState(false);
  const [transformError, setTransformError] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Set<EditorSectionId>>(
    () => new Set(EDITOR_SECTIONS),
  );
  const latestSnapshotRef = useRef<(ProfileSnapshotPayload & { profile_id: string }) | null>(null);
  const lastSavedSnapshotRef = useRef<string | null>(null);
  const templateSelectionLockedRef = useRef(false);
  const saveInFlightRef = useRef(false);
  const saveQueuedRef = useRef(false);
  const lastSaveOkRef = useRef(true);

  const presentation = useMemo(
    () => (profile ? derivedPresentation(profile, anonymization) : null),
    [profile, anonymization],
  );

  const refreshRecentProfiles = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setRecentProfiles(await listProfiles());
    } catch {
      setRecentProfiles([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const refreshProfileBuilderPreferences = useCallback(async () => {
    try {
      const preferences = await getPreferences();
      setProfileBuilderPreferences(preferences);
      return preferences;
    } catch {
      setProfileBuilderPreferences(DEFAULT_PROFILE_BUILDER_PREFERENCES);
      return DEFAULT_PROFILE_BUILDER_PREFERENCES;
    }
  }, []);

  const refreshTemplates = useCallback(async (preferredTemplateId?: string) => {
    try {
      const templates = await listTemplates();
      const items = templates.length ? templates : [
        { template: DEFAULT_PROFILE_TEMPLATE, built_in: true, customized: false, created_at: null, updated_at: null },
      ];
      setTemplateItems(items);
      setSelectedTemplate((current) => {
        if (templateSelectionLockedRef.current) return current;
        return items.find((item) => item.template.id === preferredTemplateId)?.template
          ?? items.find((item) => item.template.id === current.id)?.template
          ?? items[0].template;
      });
    } catch {
      setTemplateItems((current) => current.length ? current : [
        { template: DEFAULT_PROFILE_TEMPLATE, built_in: true, customized: false, created_at: null, updated_at: null },
      ]);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const preferences = await refreshProfileBuilderPreferences();
          await Promise.all([
            refreshRecentProfiles(),
            refreshTemplates(preferences.default_template_id),
          ]);
        } finally {
          setProfileBuilderReady(true);
        }
      })();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshProfileBuilderPreferences, refreshRecentProfiles, refreshTemplates]);

  const flushAutosave = useCallback(async function flushAutosaveNow() {
    if (saveInFlightRef.current) {
      saveQueuedRef.current = true;
      return;
    }
    const snapshot = latestSnapshotRef.current;
    if (!snapshot) return;
    const serialized = serializeProfileSnapshot(snapshot);
    if (serialized === lastSavedSnapshotRef.current) {
      lastSaveOkRef.current = true;
      setSaveStatus("saved");
      return;
    }
    saveInFlightRef.current = true;
    setSaveStatus("saving");
    try {
      const savedSnapshot = await apiUpdateProfile(snapshot.profile_id, {
        source_filename: snapshot.source_filename,
        profile: snapshot.profile,
        anonymization: snapshot.anonymization,
        template: snapshot.template,
      });
      const savedSerialized = serializeProfileSnapshot(savedSnapshot);
      lastSavedSnapshotRef.current = savedSerialized;
      lastSaveOkRef.current = true;
      setSaveStatus("saved");

      const latest = latestSnapshotRef.current;
      if (
        savedSerialized !== serialized
        && latest?.profile_id === snapshot.profile_id
        && serializeProfileSnapshot(latest) === serialized
      ) {
        latestSnapshotRef.current = {
          profile_id: snapshot.profile_id,
          ...savedSnapshot,
        };
        setProfile(savedSnapshot.profile);
        setSourceFilename(savedSnapshot.source_filename);
      }
      void refreshRecentProfiles();
    } catch {
      lastSaveOkRef.current = false;
      setSaveStatus("error");
    } finally {
      saveInFlightRef.current = false;
      if (saveQueuedRef.current) {
        saveQueuedRef.current = false;
        void flushAutosaveNow();
      }
    }
  }, [refreshRecentProfiles]);

  useEffect(() => {
    const hasUnsavedSnapshot = () => {
      const snapshot = latestSnapshotRef.current;
      return Boolean(
        snapshot
        && serializeProfileSnapshot(snapshot) !== lastSavedSnapshotRef.current
      );
    };
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasUnsavedSnapshot()) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      if (!hasUnsavedSnapshot()) return;
      if (saveInFlightRef.current) saveQueuedRef.current = true;
      else void flushAutosave();
    };
  }, [flushAutosave]);

  const flushCurrentProfile = useCallback(async () => {
    if (!profileId || !profile || !sourceFilename) return true;
    latestSnapshotRef.current = {
      profile_id: profileId,
      source_filename: sourceFilename,
      profile,
      anonymization,
      template: selectedTemplate,
    };
    if (saveInFlightRef.current) saveQueuedRef.current = true;
    else void flushAutosave();
    while (saveInFlightRef.current || saveQueuedRef.current) {
      await new Promise((resolve) => window.setTimeout(resolve, 25));
    }
    return lastSaveOkRef.current;
  }, [profileId, profile, sourceFilename, anonymization, selectedTemplate, flushAutosave]);

  const openStoredProfile = useCallback(async (storedProfileId: string) => {
    setOpeningProfileId(storedProfileId);
    setError(null);
    try {
      if (profileId && profileId !== storedProfileId) {
        const saved = await flushCurrentProfile();
        if (!saved) {
          setError("Autosave failed, so the other profile was not opened.");
          return;
        }
      }
      const stored = await apiGetProfile(storedProfileId);
      templateSelectionLockedRef.current = true;
      setProfileId(stored.profile_id);
      setProfile(stored.profile);
      setSourceFilename(stored.source_filename);
      setSourceFile(null);
      setAnonymization(stored.anonymization);
      setSelectedTemplate(stored.template);
      setExpandedSections(new Set(EDITOR_SECTIONS));
      lastSavedSnapshotRef.current = serializeProfileSnapshot(stored);
      latestSnapshotRef.current = {
        profile_id: stored.profile_id,
        source_filename: stored.source_filename,
        profile: stored.profile,
        anonymization: stored.anonymization,
        template: stored.template,
      };
      lastSaveOkRef.current = true;
      setSaveStatus("saved");
    } catch {
      setError("This recent profile is no longer available.");
      void refreshRecentProfiles();
    } finally {
      setOpeningProfileId(null);
    }
  }, [profileId, flushCurrentProfile, refreshRecentProfiles]);

  useEffect(() => {
    if (!reopenProfileId || profileId === reopenProfileId) return;
    if (profile && !profileId) return;
    const timer = window.setTimeout(() => { void openStoredProfile(reopenProfileId); }, 0);
    return () => window.clearTimeout(timer);
  }, [reopenProfileId, profile, profileId, openStoredProfile]);


  useEffect(() => {
    if (!profileId || !profile || !sourceFilename) {
      latestSnapshotRef.current = null;
      return;
    }
    latestSnapshotRef.current = {
      profile_id: profileId,
      source_filename: sourceFilename,
      profile,
      anonymization,
      template: selectedTemplate,
    };
    const serialized = serializeProfileSnapshot({
      source_filename: sourceFilename,
      profile,
      anonymization,
      template: selectedTemplate,
    });
    if (serialized === lastSavedSnapshotRef.current) return;
    const timer = window.setTimeout(() => { void flushAutosave(); }, 750);
    return () => window.clearTimeout(timer);
  }, [profileId, profile, sourceFilename, anonymization, selectedTemplate, flushAutosave]);

  function sectionIsOpen(section: EditorSectionId) {
    return expandedSections.has(section);
  }

  function toggleSection(section: EditorSectionId) {
    setExpandedSections((current) => {
      const next = new Set(current);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  }

  function sectionToggle(section: EditorSectionId, label: string) {
    const open = sectionIsOpen(section);
    return (
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`${open ? "Collapse" : "Expand"} ${label}`}
        aria-expanded={open}
        onClick={() => toggleSection(section)}
      >
        {open ? <ChevronUp /> : <ChevronDown />}
      </Button>
    );
  }

  function mutate(mutator: (draft: CandidateProfile) => void) {
    setProfile((current) => {
      if (!current) return current;
      const draft = structuredClone(current);
      mutator(draft);
      return draft;
    });
  }

  async function requestProfileExtraction(file: File): Promise<{ filename: string; profile: CandidateProfile }> {
    if (!settings.aiEnabled) throw new Error("Enable AI features in Settings before extracting a profile.");
    if (!/\.(pdf|docx)$/i.test(file.name)) throw new Error("Choose PDF or DOCX files only.");
    if (file.size > PROFILE_BUILDER_MAX_BYTES) throw new Error("CV files must be 10 MB or smaller.");
    try {
      const payload = await apiExtractProfile(file, settings.aiEnabled);
      return { filename: payload.filename ?? file.name, profile: payload.profile };
    } catch (cause) {
      if (cause instanceof ProfileBuilderApiError) {
        if (cause.detail === "profile_builder_ai_disabled_for_request") throw new Error("Enable AI features in Settings before extracting a profile.");
        if (cause.detail === "profile_builder_ai_disabled") throw new Error("Profile Builder needs AI enabled on this deployment.");
        if (cause.detail === "profile_builder_file_size_limit_exceeded") throw new Error("CV files must be 10 MB or smaller.");
        if (cause.detail === "document_text_too_sparse") throw new Error("The CV does not contain enough extractable text.");
      }
      throw new Error("Profile extraction failed. Check the file and try again.");
    }
  }


  async function persistExtractedProfile(filename: string, extractedProfile: CandidateProfile) {
    try {
      return await apiCreateProfile({
        source_filename: filename,
        profile: extractedProfile,
        anonymization: profileBuilderPreferences.anonymization,
        template: selectedTemplate,
      });
    } catch {
      throw new Error("Profile was extracted, but it could not be saved.");
    }
  }


  function queueFiles(files: File[]) {
    if (!profileBuilderReady) { setError("Conversion defaults are still loading. Try again in a moment."); return; }
    if (files.length > 10) { setError("Batch conversion supports up to 10 CVs at once."); return; }
    if (files.some((file) => !/\.(pdf|docx)$/i.test(file.name))) { setError("Batch conversion accepts PDF or DOCX files only."); return; }
    if (files.some((file) => file.size > PROFILE_BUILDER_MAX_BYTES)) { setError("Each CV must be 10 MB or smaller."); return; }
    const supported = files;
    if (!supported.length) { setError("Choose PDF or DOCX files."); return; }
    if (supported.length === 1) { setBatchItems([]); void extract(supported[0]); return; }
    setError(null);
    setBatchItems(supported.map((file) => ({
      id: globalThis.crypto.randomUUID(), file, status: "queued", profile_id: null, candidate_name: null, error: null,
    })));
  }

  async function runBatchConversion() {
    if (batchRunning || !batchItems.length) return;
    setBatchRunning(true);
    setError(null);
    for (const item of batchItems) {
      if (item.status === "completed") continue;
      setBatchItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, status: "processing", error: null } : entry));
      try {
        const extracted = await requestProfileExtraction(item.file);
        const persisted = await persistExtractedProfile(extracted.filename, extracted.profile);
        const candidateName = [persisted.snapshot.profile.personal.first_name, persisted.snapshot.profile.personal.last_name].filter(Boolean).join(" ") || null;
        setBatchItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, status: "completed", profile_id: persisted.profileId, candidate_name: candidateName } : entry));
      } catch (cause) {
        setBatchItems((current) => current.map((entry) => entry.id === item.id ? { ...entry, status: "failed", error: cause instanceof Error ? cause.message : "Conversion failed." } : entry));
      }
    }
    setBatchRunning(false);
    void refreshRecentProfiles();
  }

  async function extract(file: File) {
    if (extracting) return;
    setError(null);
    setSourceFile(file);
    setSourceFilename(file.name);
    setProfileId(null);
    setExtracting(true);
    try {
      const extracted = await requestProfileExtraction(file);
      const persisted = await persistExtractedProfile(extracted.filename, extracted.profile);
      templateSelectionLockedRef.current = true;
      setProfile(persisted.snapshot.profile);
      setProfileId(persisted.profileId);
      setSourceFilename(persisted.snapshot.source_filename);
      setAnonymization(persisted.snapshot.anonymization);
      setSelectedTemplate(persisted.snapshot.template);
      lastSavedSnapshotRef.current = serializeProfileSnapshot(persisted.snapshot);
      latestSnapshotRef.current = { profile_id: persisted.profileId, ...persisted.snapshot };
      lastSaveOkRef.current = true;
      setSaveStatus("saved");
      void refreshRecentProfiles();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Profile extraction failed.");
    } finally {
      setExtracting(false);
    }
  }


  async function deleteRecentProfile(item: RecentProfileItem) {
    if (!window.confirm(`Delete ${item.candidate_name ?? item.source_filename}?`)) return;
    try {
      await apiDeleteProfile(item.profile_id);
      setRecentProfiles((current) => current.filter((profileItem) => profileItem.profile_id !== item.profile_id));
    } catch {
      setError("The recent profile could not be deleted.");
    }
  }

  async function persistDefaultTemplate(templateId: string) {
    try {
      const saved = await savePreferences({
        ...profileBuilderPreferences,
        default_template_id: templateId,
      });
      setProfileBuilderPreferences(saved);
      return true;
    } catch {
      setError("The default template could not be saved.");
      return false;
    }
  }


  function selectTemplate(template: ProfileTemplate) {
    templateSelectionLockedRef.current = true;
    setSelectedTemplate(structuredClone(template));
    setTemplateDialogOpen(false);
    if (!profile) void persistDefaultTemplate(template.id);
  }

  async function deleteTemplate(item: ProfileTemplateListItem) {
    const action = item.built_in
      ? "Reset the customized IDEGO Default template for the internal team?"
      : item.overrides_shared
        ? `Remove your private override of ${item.template.name}? The shared team version will become visible again.`
        : item.template.visibility === "shared"
          ? `Delete shared template ${item.template.name} for the entire internal team?`
          : `Delete private template ${item.template.name}?`;
    if (!window.confirm(action)) return;
    try {
      await apiDeleteTemplate(item.template.id);
    } catch {
      setError("The template could not be deleted.");
      return;
    }
    if (item.overrides_shared) {
      templateSelectionLockedRef.current = false;
      await refreshTemplates(item.template.id);
      return;
    }
    if (selectedTemplate.id === item.template.id) {
      templateSelectionLockedRef.current = true;
      setSelectedTemplate(DEFAULT_PROFILE_TEMPLATE);
    }
    if (profileBuilderPreferences.default_template_id === item.template.id) {
      await persistDefaultTemplate(DEFAULT_PROFILE_TEMPLATE.id);
    }
    await refreshTemplates(
      profileBuilderPreferences.default_template_id === item.template.id
        ? DEFAULT_PROFILE_TEMPLATE.id
        : undefined,
    );
  }

  async function openTemplateCreator(templateId: string | null) {
    setTemplateDialogOpen(false);
    const saved = await flushCurrentProfile();
    if (!saved) {
      setError("Autosave failed, so Template Creator was not opened. Retry after the profile saves.");
      return;
    }
    const returnQuery = profileId ? `?profile=${encodeURIComponent(profileId)}` : "";
    router.push(`/profile-builder/templates/${encodeURIComponent(templateId ?? "new")}${returnQuery}`);
  }

  function openTransform(mode: "action" | "translation") {
    setTransformMode(mode);
    setTransformProposal(null);
    setTransformError(null);
    setTransformInstruction("");
    setTransformSections(new Set(mode === "translation"
      ? ["headline", "summary", "skills", "technologies", "experience", "education", "languages", "certifications", "additional_sections"]
      : ["summary"]));
    setAcceptedTransformSections(new Set());
    setTransformDialogOpen(true);
  }

  async function runProfileTransform() {
    if (!profile || transformRunning || !transformSections.size) return;
    if (transformMode === "action" && !transformInstruction.trim()) {
      setTransformError("Describe what the AI should change.");
      return;
    }
    if (!settings.aiEnabled) {
      setTransformError("Enable AI features in Settings first.");
      return;
    }
    setTransformRunning(true);
    setTransformError(null);
    try {
      const sections = [...transformSections];
      const proposal = await apiTransformProfile(
        profile,
        sections,
        transformInstruction,
        transformMode,
        transformMode === "translation" ? transformLanguage : null,
        settings.aiEnabled,
      );
      setTransformProposal(proposal);
      setAcceptedTransformSections(new Set(sections.filter((section) => {
        const currentValue = profile[section];
        const proposedValue = proposal[section];
        return JSON.stringify(currentValue) !== JSON.stringify(proposedValue);
      })));
    } catch (cause) {
      setTransformError(cause instanceof Error ? cause.message : "AI transform failed.");
    } finally {
      setTransformRunning(false);
    }
  }

  function acceptProfileTransform() {
    if (!transformProposal || !acceptedTransformSections.size) return;
    mutate((draft) => {
      for (const section of acceptedTransformSections) {
        switch (section) {
          case "headline": draft.headline = transformProposal.headline; break;
          case "summary": draft.summary = transformProposal.summary; break;
          case "skills": draft.skills = structuredClone(transformProposal.skills); break;
          case "technologies": draft.technologies = structuredClone(transformProposal.technologies); break;
          case "experience": draft.experience = structuredClone(transformProposal.experience); break;
          case "education": draft.education = structuredClone(transformProposal.education); break;
          case "languages": draft.languages = structuredClone(transformProposal.languages); break;
          case "certifications": draft.certifications = structuredClone(transformProposal.certifications); break;
          case "additional_sections": draft.additional_sections = structuredClone(transformProposal.additional_sections); break;
        }
      }
    });
    setTransformDialogOpen(false);
    setTransformProposal(null);
  }

  async function generateSummary() {
    if (!profile || summaryGenerating) return;
    if (!settings.aiEnabled) {
      setSummaryError("Enable AI features in Settings before generating a summary.");
      return;
    }
    setSummaryGenerating(true);
    setSummaryError(null);
    try {
      const summary = await generateProfileSummary(
        profile,
        summaryInstruction.trim() || null,
        settings.aiEnabled,
      );
      mutate((draft) => {
        draft.summary = summary;
      });
    } catch (cause) {
      setSummaryError(cause instanceof Error ? cause.message : "AI summary generation failed.");
    } finally {
      setSummaryGenerating(false);
    }
  }

  function outputFilename(
    extension: "docx" | "pdf",
    snapshot: ProfileSnapshotPayload | null,
  ) {
    if (!snapshot) return `candidate-profile.${extension}`;
    const exported = derivedPresentation(snapshot.profile, snapshot.anonymization);
    const first = exported.personal.first_name?.trim() ?? "";
    const last = exported.personal.last_name?.trim() ?? "";
    const name = [first, last].filter(Boolean).join(" ") || "candidate";
    const today = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
    const rendered = profileBuilderPreferences.filename_pattern
      .replaceAll("{name}", name)
      .replaceAll("{first_name}", first)
      .replaceAll("{last_name}", last)
      .replaceAll("{template}", snapshot.template.name)
      .replaceAll("{date}", today)
      .replace(/[^\p{L}\p{N}._ -]+/gu, "-")
      .replace(/\s+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^[._-]+|[._-]+$/g, "")
      .toLowerCase();
    return `${rendered || "candidate-profile"}.${extension}`;
  }

  async function exportProfile(format: "docx" | "pdf") {
    if (!profile) return;
    setError(null);
    setExporting(true);
    try {
      const saved = await flushCurrentProfile();
      const filenameSnapshot = saved && latestSnapshotRef.current
        ? {
            source_filename: latestSnapshotRef.current.source_filename,
            profile: latestSnapshotRef.current.profile,
            anonymization: latestSnapshotRef.current.anonymization,
            template: latestSnapshotRef.current.template,
          }
        : null;
      const blob = await exportProfileSnapshot(format, {
        profile,
        anonymization,
        template_id: selectedTemplate.id,
        template: selectedTemplate,
      });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = outputFilename(format, filenameSnapshot);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `${format.toUpperCase()} export failed.`);
    } finally {
      setExporting(false);
    }
  }

  async function exportDocx() { await exportProfile("docx"); }
  async function exportPdf() { await exportProfile("pdf"); }

  async function reset() {
    const saved = await flushCurrentProfile();
    if (!saved) {
      setError("Autosave failed, so the current profile was not closed.");
      return;
    }
    setProfileId(null);
    setProfile(null);
    setSourceFilename(null);
    setSourceFile(null);
    setAnonymization(profileBuilderPreferences.anonymization);
    setSummaryInstruction("");
    setSummaryError(null);
    setExpandedSections(new Set(EDITOR_SECTIONS));
    setSaveStatus("idle");
    setError(null);
    latestSnapshotRef.current = null;
    lastSavedSnapshotRef.current = null;
    lastSaveOkRef.current = true;
    templateSelectionLockedRef.current = false;
    void refreshRecentProfiles();
    void refreshTemplates(profileBuilderPreferences.default_template_id);
  }

  if (!profile || !presentation) {
    return (
      <div className="mx-auto max-w-5xl space-y-6">
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold tracking-tight">Profile Builder</h2>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Convert one CV or a batch of up to 10, edit the structured profile, and export the exact current snapshot to DOCX or PDF.
          </p>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Upload candidate CV</CardTitle>
            <CardDescription>PDF or DOCX, up to 10 at once and 10 MB each. National identifiers are redacted before AI extraction.</CardDescription>
          </CardHeader>
          <CardContent>
            <label
              className="flex min-h-64 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-muted-foreground/30 bg-muted/20 p-8 text-center transition-colors hover:bg-muted/35"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                if (extracting || batchRunning || !profileBuilderReady) return;
                queueFiles(Array.from(event.dataTransfer.files));
              }}
            >
              <input
                type="file"
                accept={ACCEPT}
                multiple
                className="hidden"
                disabled={extracting || batchRunning || !settings.aiEnabled || !profileBuilderReady}
                onChange={(event) => {
                  const files = Array.from(event.target.files ?? []);
                  if (files.length) queueFiles(files);
                  event.target.value = "";
                }}
              />
              {extracting ? (
                <LoaderCircle className="mb-4 size-9 animate-spin text-primary" />
              ) : (
                <Upload className="mb-4 size-9 text-primary" />
              )}
              <p className="font-medium">{!profileBuilderReady ? "Loading conversion defaults…" : extracting ? "Extracting candidate profile…" : batchRunning ? "Batch conversion in progress…" : "Drop CVs here or click to select"}</p>
              <p className="mt-1 text-xs text-muted-foreground">Accepted: PDF, DOCX · maximum 10 files · 10 MB each</p>
              {!settings.aiEnabled ? (
                <p className="mt-3 text-xs font-medium text-amber-700 dark:text-amber-400">
                  AI features are disabled in Settings. Profile extraction is paused.
                </p>
              ) : null}
            </label>
            {batchItems.length ? <div className="mt-4 overflow-hidden rounded-xl border">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-muted/25 px-4 py-3">
                <div><p className="text-sm font-medium">Batch conversion · {batchItems.length} CVs</p><p className="text-xs text-muted-foreground">Each successful CV becomes its own saved profile.</p></div>
                <div className="flex gap-2"><Button variant="ghost" size="sm" disabled={batchRunning} onClick={() => setBatchItems([])}>Clear</Button><Button size="sm" disabled={batchRunning || batchItems.every((item) => item.status === "completed")} onClick={() => void runBatchConversion()}>{batchRunning ? <LoaderCircle className="animate-spin" /> : null}{batchRunning ? "Converting…" : batchItems.some((item) => item.status === "failed") ? "Retry failed" : "Convert batch"}</Button></div>
              </div>
              <ul className="divide-y">{batchItems.map((item) => <li key={item.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                <span className="min-w-0 flex-1"><span className="block truncate font-medium">{item.candidate_name ?? item.file.name}</span>{item.error ? <span className="block truncate text-xs text-destructive">{item.error}</span> : null}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{item.status === "processing" ? "Processing…" : item.status === "completed" ? "Completed" : item.status === "failed" ? "Failed" : "Queued"}</span>
                {item.status === "processing" ? <LoaderCircle className="size-4 animate-spin" /> : item.profile_id ? <Button variant="ghost" size="sm" render={<Link href={`/profile-builder?profile=${encodeURIComponent(item.profile_id)}`} />}>Open</Button> : null}
              </li>)}</ul>
            </div> : null}
            {error ? (
              <div className="mt-4 flex flex-wrap items-center gap-3" aria-live="polite">
                <p className="min-w-0 flex-1 text-sm text-destructive">
                  {sourceFilename ? `${sourceFilename}: ` : ""}{error}
                </p>
                {sourceFile ? (
                  <Button variant="outline" size="sm" disabled={extracting} onClick={() => void extract(sourceFile)}>
                    Retry
                  </Button>
                ) : null}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
          <section className="overflow-hidden rounded-xl border bg-card">
            <div className="flex items-center gap-2 border-b px-5 py-4">
              <History className="size-4" />
              <div className="min-w-0 flex-1">
                <h2 className="font-medium">Recent profiles</h2>
                <p className="text-xs text-muted-foreground">Reopen an extracted profile with its exact saved template and visibility settings.</p>
              </div>
              <Button variant="ghost" size="sm" render={<Link href="/profiles" />}>View all</Button>
            </div>
            {historyLoading ? <div className="flex items-center justify-center py-9"><LoaderCircle className="size-5 animate-spin text-muted-foreground" /></div> : null}
            {!historyLoading && !recentProfiles.length ? <p className="px-5 py-8 text-sm text-muted-foreground">No recent profiles yet.</p> : null}
            {recentProfiles.length ? <ul className="divide-y">{recentProfiles.slice(0, 10).map((item) => (
              <li key={item.profile_id} className="flex min-w-0 items-center gap-2 px-3 py-2">
                <button type="button" onClick={() => void openStoredProfile(item.profile_id)} disabled={openingProfileId === item.profile_id} className="min-w-0 flex-1 rounded-md px-2 py-2 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60">
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="truncate text-sm font-medium">{item.candidate_name ?? item.source_filename}</span>
                    <time className="shrink-0 text-xs text-muted-foreground">{new Intl.DateTimeFormat(settings.uiLanguage, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.updated_at))}</time>
                  </span>
                  <span className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
                    <span className="truncate">{item.source_filename}</span>
                    <span aria-hidden>·</span>
                    <span className="truncate">{item.template_name}</span>
                  </span>
                </button>
                {openingProfileId === item.profile_id ? <LoaderCircle className="size-4 shrink-0 animate-spin text-muted-foreground" /> : null}
                <Button variant="ghost" size="icon" className="size-8 shrink-0" aria-label={`Delete ${item.candidate_name ?? item.source_filename}`} onClick={() => void deleteRecentProfile(item)}><Trash2 className="size-4" /></Button>
              </li>
            ))}</ul> : null}
          </section>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2"><LayoutTemplate className="size-4" />Current template</CardTitle>
              <CardDescription>Used for the next CV and carried with every saved profile.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border bg-muted/20 p-4">
                <p className="font-medium">{selectedTemplate.name}</p>
                <p className="mt-1 text-xs text-muted-foreground">{selectedTemplate.description || "Custom profile template"}</p>
                <p className="mt-3 text-xs text-muted-foreground">{selectedTemplate.sections.filter((section) => section.visible).length} visible blocks · {selectedTemplate.typography.font_family}</p>
              </div>
              <Button variant="outline" className="w-full" onClick={() => setTemplateDialogOpen(true)}><LayoutTemplate />Manage templates</Button>
            </CardContent>
          </Card>
        </div>

        <TemplateManagerDialog
          open={templateDialogOpen}
          onOpenChange={setTemplateDialogOpen}
          items={templateItems}
          selectedTemplate={selectedTemplate}
          onSelect={selectTemplate}
          onDelete={(item) => { void deleteTemplate(item); }}
          onEdit={(templateId) => { void openTemplateCreator(templateId); }}
          onCreate={() => { void openTemplateCreator(null); }}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[1800px] space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{sourceFilename ?? "Candidate profile"}</p>
          <p className="text-xs text-muted-foreground">
            Template: {selectedTemplate.name}
            {saveStatus === "saving" ? " · Saving…" : saveStatus === "saved" ? " · Saved" : saveStatus === "error" ? " · Autosave failed" : ""}
          </p>
        </div>
        <Button variant="outline" onClick={() => setTemplateDialogOpen(true)}>
          <LayoutTemplate />Manage template
        </Button>
        <Button variant="outline" onClick={() => openTransform("action")} disabled={!settings.aiEnabled}>
          <WandSparkles />AI Actions
        </Button>
        <Button variant="outline" onClick={() => openTransform("translation")} disabled={!settings.aiEnabled}>
          <Languages />Translate
        </Button>
        <Button variant="outline" onClick={() => void reset()}>
          <RotateCcw data-icon="inline-start" />New CV
        </Button>
        <Button variant="outline" onClick={() => void exportPdf()} disabled={exporting}>
          <Download />PDF
        </Button>
        <Button onClick={() => void exportDocx()} disabled={exporting}>
          {exporting ? <LoaderCircle className="animate-spin" data-icon="inline-start" /> : <Download data-icon="inline-start" />}
          {exporting ? "Exporting…" : "DOCX"}
        </Button>
      </div>
      {error ? <p className="rounded-lg border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{error}</p> : null}
      <TemplateManagerDialog
        open={templateDialogOpen}
        onOpenChange={setTemplateDialogOpen}
        items={templateItems}
        selectedTemplate={selectedTemplate}
        onSelect={selectTemplate}
        onDelete={(item) => { void deleteTemplate(item); }}
        onEdit={(templateId) => { void openTemplateCreator(templateId); }}
        onCreate={() => { void openTemplateCreator(null); }}
      />
      <Dialog open={transformDialogOpen} onOpenChange={(open) => {
        setTransformDialogOpen(open);
        if (!open) { setTransformProposal(null); setTransformError(null); }
      }}>
        <DialogContent className="sm:max-w-5xl">
          <DialogHeader>
            <DialogTitle>{transformMode === "translation" ? "Translate profile" : "AI Actions"}</DialogTitle>
            <DialogDescription>
              {transformProposal
                ? "Review every proposed section and accept only the changes you want."
                : transformMode === "translation"
                  ? "Translate selected professional sections. Personal/contact data is never sent."
                  : "Describe the rewrite and choose which professional sections AI may change."}
            </DialogDescription>
          </DialogHeader>
          {!transformProposal ? <div className="space-y-4">
            {transformMode === "translation" ? <div className="space-y-1.5">
              <Label htmlFor="profile-transform-language">Target language</Label>
              <select id="profile-transform-language" value={transformLanguage} onChange={(event) => setTransformLanguage(event.target.value as typeof transformLanguage)} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm">
                <option value="en">English</option><option value="pl">Polish</option><option value="de">German</option><option value="fr">French</option><option value="es">Spanish</option>
              </select>
            </div> : <div className="space-y-1.5">
              <Label htmlFor="profile-transform-instruction">Instruction</Label>
              <textarea id="profile-transform-instruction" rows={4} maxLength={12000} value={transformInstruction} onChange={(event) => setTransformInstruction(event.target.value)} placeholder="Example: Make the profile more concise and emphasize backend ownership for the pasted job description…" className="w-full resize-y rounded-lg border border-input bg-background px-3 py-2 text-sm" />
            </div>}
            <div>
              <p className="mb-2 text-sm font-medium">Sections AI may change</p>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {PROFESSIONAL_SECTIONS.map((section) => <label key={section} className="flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm">
                  <input type="checkbox" checked={transformSections.has(section)} onChange={(event) => setTransformSections((current) => {
                    const next = new Set(current); if (event.target.checked) next.add(section); else next.delete(section); return next;
                  })} />
                  {PROFESSIONAL_SECTION_LABELS[section]}
                </label>)}
              </div>
            </div>
            {transformError ? <p className="text-sm text-destructive">{transformError}</p> : null}
          </div> : <div className="max-h-[62vh] space-y-3 overflow-y-auto pr-1">
            {[...transformSections].map((section) => {
              const before = profile[section];
              const after = transformProposal[section];
              const changed = JSON.stringify(before) !== JSON.stringify(after);
              return <div key={section} className={`rounded-xl border p-3 ${changed ? "" : "opacity-60"}`}>
                <label className="mb-3 flex items-center gap-2 font-medium">
                  <input type="checkbox" disabled={!changed} checked={acceptedTransformSections.has(section)} onChange={(event) => setAcceptedTransformSections((current) => {
                    const next = new Set(current); if (event.target.checked) next.add(section); else next.delete(section); return next;
                  })} />
                  {PROFESSIONAL_SECTION_LABELS[section]}{changed ? "" : " · unchanged"}
                </label>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="min-w-0"><p className="mb-1 text-xs font-medium text-muted-foreground">Before</p><pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-2 text-xs">{typeof before === "string" || before == null ? String(before ?? "") : JSON.stringify(before, null, 2)}</pre></div>
                  <div className="min-w-0"><p className="mb-1 text-xs font-medium text-muted-foreground">Proposed</p><pre className="max-h-52 overflow-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-2 text-xs">{typeof after === "string" || after == null ? String(after ?? "") : JSON.stringify(after, null, 2)}</pre></div>
                </div>
              </div>;
            })}
          </div>}
          <DialogFooter>
            {transformProposal ? <>
              <Button variant="outline" onClick={() => { setTransformProposal(null); setAcceptedTransformSections(new Set()); }}>Back</Button>
              <Button disabled={!acceptedTransformSections.size} onClick={acceptProfileTransform}>Accept selected ({acceptedTransformSections.size})</Button>
            </> : <Button disabled={transformRunning || !transformSections.size} onClick={() => void runProfileTransform()}>
              {transformRunning ? <LoaderCircle className="animate-spin" /> : transformMode === "translation" ? <Languages /> : <WandSparkles />}
              {transformRunning ? "Generating preview…" : "Preview changes"}
            </Button>}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-card px-3 py-2">
            <p className="text-sm font-medium">Profile sections</p>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => setExpandedSections(new Set(EDITOR_SECTIONS))}>
                <ChevronDown />Expand all
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setExpandedSections(new Set())}>
                <ChevronUp />Collapse all
              </Button>
            </div>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Personal information</CardTitle>
              <CardDescription>Canonical values. Anonymization below only changes preview/export.</CardDescription>
              <CardAction>{sectionToggle("personal", "Personal information")}</CardAction>
            </CardHeader>
            {sectionIsOpen("personal") ? <CardContent className="grid gap-3 sm:grid-cols-2">
              <Field label="First name" value={profile.personal.first_name} onChange={(value) => mutate((draft) => { draft.personal.first_name = value; })} />
              <Field label="Last name" value={profile.personal.last_name} onChange={(value) => mutate((draft) => { draft.personal.last_name = value; })} />
              <Field label="Email" value={profile.personal.email} onChange={(value) => mutate((draft) => { draft.personal.email = value; })} />
              <Field label="Phone" value={profile.personal.phone} onChange={(value) => mutate((draft) => { draft.personal.phone = value; })} />
              <Field label="Location" value={profile.personal.location} onChange={(value) => mutate((draft) => { draft.personal.location = value; })} />
              <Field label="LinkedIn" value={profile.personal.links.linkedin} onChange={(value) => mutate((draft) => { draft.personal.links.linkedin = value; })} />
              <Field label="GitHub" value={profile.personal.links.github} onChange={(value) => mutate((draft) => { draft.personal.links.github = value; })} />
              <Field label="Portfolio" value={profile.personal.links.portfolio} onChange={(value) => mutate((draft) => { draft.personal.links.portfolio = value; })} />
              <div className="space-y-2 sm:col-span-2">
                <div className="flex items-center justify-between">
                  <Label>Other links</Label>
                  <Button variant="ghost" size="sm" onClick={() => mutate((draft) => { draft.personal.links.other.push({ label: "", url: "" }); })}>
                    <Plus />Add link
                  </Button>
                </div>
                {profile.personal.links.other.map((link, index) => (
                  <div key={index} className="grid gap-2 sm:grid-cols-[0.45fr_1fr_auto]">
                    <Input aria-label={`Other link ${index + 1} label`} value={link.label} placeholder="Label" onChange={(event) => mutate((draft) => { draft.personal.links.other[index].label = event.target.value; })} />
                    <Input aria-label={`Other link ${index + 1} URL`} value={link.url} placeholder="https://…" onChange={(event) => mutate((draft) => { draft.personal.links.other[index].url = event.target.value; })} />
                    <Button variant="ghost" size="icon" aria-label="Remove link" onClick={() => mutate((draft) => { draft.personal.links.other.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                ))}
              </div>
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader><CardTitle>Profile</CardTitle><CardAction>{sectionToggle("profile", "Profile")}</CardAction></CardHeader>
            {sectionIsOpen("profile") ? <CardContent className="space-y-3">
              <Field label="Headline" value={profile.headline} onChange={(value) => mutate((draft) => { draft.headline = value; })} />
              <TextareaField label="Summary" value={profile.summary ?? ""} rows={5} onChange={(value) => mutate((draft) => { draft.summary = value || null; })} />
              <div className="rounded-xl border bg-muted/20 p-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="flex items-center gap-2 text-sm font-medium"><Sparkles className="size-4" />AI Summary</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">GPT-5.6 Luna · reasoning none · max 384 output tokens</p>
                  </div>
                  <Button
                    variant={profile.summary ? "outline" : "default"}
                    size="sm"
                    disabled={summaryGenerating || !settings.aiEnabled}
                    onClick={() => void generateSummary()}
                  >
                    {summaryGenerating ? <LoaderCircle className="animate-spin" /> : <Sparkles />}
                    {summaryGenerating ? "Generating…" : profile.summary ? "Regenerate" : "Generate"}
                  </Button>
                </div>
                <div className="mt-3 space-y-1.5">
                  <Label htmlFor="profile-summary-instruction">Instruction or job description (optional)</Label>
                  <textarea
                    id="profile-summary-instruction"
                    rows={3}
                    maxLength={12000}
                    value={summaryInstruction}
                    onChange={(event) => setSummaryInstruction(event.target.value)}
                    placeholder="Example: Focus on Python backend experience and leadership, or paste the job description here."
                    className="w-full resize-y rounded-lg border border-input bg-background px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                  />
                </div>
                {summaryError ? <p className="mt-2 text-sm text-destructive">{summaryError}</p> : null}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <TextareaField label="Skills" value={profile.skills.join("\n")} rows={5} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.skills = nonEmptyLines(value); })} />
                <TextareaField label="Technologies" value={profile.technologies.join("\n")} rows={5} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.technologies = nonEmptyLines(value); })} />
              </div>
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Anonymization</CardTitle>
              <CardDescription>Private by default. These controls only change preview/export and never delete canonical data.</CardDescription>
              <CardAction>{sectionToggle("anonymization", "Anonymization")}</CardAction>
            </CardHeader>
            {sectionIsOpen("anonymization") ? <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-muted/45 px-3 py-2">
                <div>
                  <p className="text-sm font-medium">Visibility preset</p>
                  <p className="text-xs text-muted-foreground">Start anonymized, then reveal only what this profile needs.</p>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="outline" size="sm" onClick={() => setAnonymization(DEFAULT_ANONYMIZATION)}>
                    <EyeOff />Select all
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setAnonymization(REVEALED_ANONYMIZATION)}>
                    <Eye />Deselect all
                  </Button>
                </div>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {([
                  ["Hide first name", "hide_first_name"],
                  ["Hide last name", "hide_last_name"],
                  ["Hide email", "hide_email"],
                  ["Hide phone", "hide_phone"],
                  ["Hide location", "hide_location"],
                  ["Hide LinkedIn", "hide_linkedin"],
                  ["Hide GitHub", "hide_github"],
                  ["Hide portfolio", "hide_portfolio"],
                ] as const).map(([label, key]) => (
                  <Toggle key={key} label={label} checked={anonymization[key]} onChange={(checked) => setAnonymization((current) => ({ ...current, [key]: checked }))} />
                ))}
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="profile-builder-employer-mode">Employer names</Label>
                  <select id="profile-builder-employer-mode" value={anonymization.employer_mode} onChange={(event) => setAnonymization((current) => ({ ...current, employer_mode: event.target.value as AnonymizationPolicy["employer_mode"] }))} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                    <option value="show">Show</option>
                    <option value="hide">Hide</option>
                    <option value="genericize">Genericize</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="profile-builder-institution-mode">Institution names</Label>
                  <select id="profile-builder-institution-mode" value={anonymization.institution_mode} onChange={(event) => setAnonymization((current) => ({ ...current, institution_mode: event.target.value as AnonymizationPolicy["institution_mode"] }))} className="h-8 w-full rounded-lg border border-input bg-background px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50">
                    <option value="show">Show</option>
                    <option value="hide">Hide</option>
                  </select>
                </div>
              </div>
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Experience</CardTitle>
              <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.experience.push({ id: newProfileBuilderId("experience"), company: null, company_category: null, role: null, project: null, location: null, start_date: null, end_date: null, current: false, responsibilities: [], achievements: [], technologies: [] }); })}><Plus />Add</Button>{sectionToggle("experience", "Experience")}</div></CardAction>
            </CardHeader>
            {sectionIsOpen("experience") ? <CardContent className="space-y-3">
              {profile.experience.length ? profile.experience.map((entry, index) => (
                <div key={entry.id} className="space-y-3 rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-medium">{entry.role || entry.company || `Experience ${index + 1}`}</p>
                    <Button variant="ghost" size="icon-sm" aria-label="Remove experience" onClick={() => mutate((draft) => { draft.experience.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Role" value={entry.role} onChange={(value) => mutate((draft) => { draft.experience[index].role = value; })} />
                    <Field label="Company" value={entry.company} onChange={(value) => mutate((draft) => { draft.experience[index].company = value; })} />
                    <Field label="Company category" value={entry.company_category} placeholder="Optional generic label" onChange={(value) => mutate((draft) => { draft.experience[index].company_category = value; })} />
                    <Field label="Project" value={entry.project} onChange={(value) => mutate((draft) => { draft.experience[index].project = value; })} />
                    <Field label="Location" value={entry.location} onChange={(value) => mutate((draft) => { draft.experience[index].location = value; })} />
                    <div className="grid grid-cols-2 gap-2">
                      <Field label="Start" value={entry.start_date} onChange={(value) => mutate((draft) => { draft.experience[index].start_date = value; })} />
                      <Field label="End" value={entry.end_date} onChange={(value) => mutate((draft) => { draft.experience[index].end_date = value; })} />
                    </div>
                  </div>
                  <Toggle label="Current role" checked={entry.current} onChange={(checked) => mutate((draft) => { draft.experience[index].current = checked; })} />
                  <TextareaField label="Responsibilities" value={entry.responsibilities.join("\n")} rows={4} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.experience[index].responsibilities = nonEmptyLines(value); })} />
                  <TextareaField label="Achievements" value={entry.achievements.join("\n")} rows={3} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.experience[index].achievements = nonEmptyLines(value); })} />
                  <TextareaField label="Technologies" value={entry.technologies.join("\n")} rows={3} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.experience[index].technologies = nonEmptyLines(value); })} />
                </div>
              )) : <p className="text-sm text-muted-foreground">No experience entries extracted.</p>}
            </CardContent> : null}
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Education</CardTitle>
              <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.education.push({ id: newProfileBuilderId("education"), institution: null, degree: null, field: null, start_date: null, end_date: null, location: null, description: null }); })}><Plus />Add</Button>{sectionToggle("education", "Education")}</div></CardAction>
            </CardHeader>
            {sectionIsOpen("education") ? <CardContent className="space-y-3">
              {profile.education.length ? profile.education.map((entry, index) => (
                <div key={entry.id} className="space-y-3 rounded-xl border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="truncate text-sm font-medium">{entry.institution || entry.degree || `Education ${index + 1}`}</p>
                    <Button variant="ghost" size="icon-sm" aria-label="Remove education" onClick={() => mutate((draft) => { draft.education.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field label="Institution" value={entry.institution} onChange={(value) => mutate((draft) => { draft.education[index].institution = value; })} />
                    <Field label="Degree" value={entry.degree} onChange={(value) => mutate((draft) => { draft.education[index].degree = value; })} />
                    <Field label="Field" value={entry.field} onChange={(value) => mutate((draft) => { draft.education[index].field = value; })} />
                    <Field label="Location" value={entry.location} onChange={(value) => mutate((draft) => { draft.education[index].location = value; })} />
                    <Field label="Start" value={entry.start_date} onChange={(value) => mutate((draft) => { draft.education[index].start_date = value; })} />
                    <Field label="End" value={entry.end_date} onChange={(value) => mutate((draft) => { draft.education[index].end_date = value; })} />
                  </div>
                  <TextareaField label="Description" value={entry.description ?? ""} rows={3} onChange={(value) => mutate((draft) => { draft.education[index].description = value || null; })} />
                </div>
              )) : <p className="text-sm text-muted-foreground">No education entries extracted.</p>}
            </CardContent> : null}
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Languages</CardTitle>
                <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.languages.push({ id: newProfileBuilderId("language"), language: "", level: null }); })}><Plus />Add</Button>{sectionToggle("languages", "Languages")}</div></CardAction>
              </CardHeader>
              {sectionIsOpen("languages") ? <CardContent className="space-y-2">
                {profile.languages.map((entry, index) => (
                  <div key={entry.id} className="grid grid-cols-[1fr_0.7fr_auto] gap-2">
                    <Input aria-label={`Language ${index + 1}`} value={entry.language} placeholder="Language" onChange={(event) => mutate((draft) => { draft.languages[index].language = event.target.value; })} />
                    <Input aria-label={`Language ${index + 1} level`} value={entry.level ?? ""} placeholder="Level" onChange={(event) => mutate((draft) => { draft.languages[index].level = event.target.value || null; })} />
                    <Button variant="ghost" size="icon" aria-label="Remove language" onClick={() => mutate((draft) => { draft.languages.splice(index, 1); })}><Trash2 /></Button>
                  </div>
                ))}
              </CardContent> : null}
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Certifications</CardTitle>
                <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.certifications.push({ id: newProfileBuilderId("certification"), name: "", issuer: null, date: null, url: null }); })}><Plus />Add</Button>{sectionToggle("certifications", "Certifications")}</div></CardAction>
              </CardHeader>
              {sectionIsOpen("certifications") ? <CardContent className="space-y-3">
                {profile.certifications.map((entry, index) => (
                  <div key={entry.id} className="space-y-2 rounded-lg border p-3">
                    <div className="grid grid-cols-[1fr_auto] gap-2"><Input aria-label={`Certification ${index + 1} name`} value={entry.name} placeholder="Certification" onChange={(event) => mutate((draft) => { draft.certifications[index].name = event.target.value; })} /><Button variant="ghost" size="icon" aria-label="Remove certification" onClick={() => mutate((draft) => { draft.certifications.splice(index, 1); })}><Trash2 /></Button></div>
                    <div className="grid grid-cols-2 gap-2"><Input aria-label={`Certification ${index + 1} issuer`} value={entry.issuer ?? ""} placeholder="Issuer" onChange={(event) => mutate((draft) => { draft.certifications[index].issuer = event.target.value || null; })} /><Input aria-label={`Certification ${index + 1} date`} value={entry.date ?? ""} placeholder="Date" onChange={(event) => mutate((draft) => { draft.certifications[index].date = event.target.value || null; })} /></div>
                    <Input aria-label={`Certification ${index + 1} URL`} value={entry.url ?? ""} placeholder="URL" onChange={(event) => mutate((draft) => { draft.certifications[index].url = event.target.value || null; })} />
                  </div>
                ))}
              </CardContent> : null}
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Additional sections</CardTitle>
              <CardAction><div className="flex items-center gap-1"><Button variant="outline" size="sm" onClick={() => mutate((draft) => { draft.additional_sections.push({ id: newProfileBuilderId("additional"), title: "New section", items: [] }); })}><Plus />Add</Button>{sectionToggle("additional", "Additional sections")}</div></CardAction>
            </CardHeader>
            {sectionIsOpen("additional") ? <CardContent className="space-y-3">
              {profile.additional_sections.map((section, index) => (
                <div key={section.id} className="space-y-2 rounded-lg border p-3">
                  <div className="grid grid-cols-[1fr_auto] gap-2"><Input aria-label={`Additional section ${index + 1} title`} value={section.title} onChange={(event) => mutate((draft) => { draft.additional_sections[index].title = event.target.value; })} /><Button variant="ghost" size="icon" aria-label="Remove section" onClick={() => mutate((draft) => { draft.additional_sections.splice(index, 1); })}><Trash2 /></Button></div>
                  <TextareaField label="Items" value={section.items.join("\n")} rows={4} placeholder="One per line" onChange={(value) => mutate((draft) => { draft.additional_sections[index].items = nonEmptyLines(value); })} />
                </div>
              ))}
            </CardContent> : null}
          </Card>


          <Card>
            <CardHeader>
              <CardTitle>Custom fields</CardTitle>
              <CardDescription>Organization-defined profile metadata. Definitions and defaults are managed in Settings.</CardDescription>
              <CardAction>{sectionToggle("custom_fields", "Custom fields")}</CardAction>
            </CardHeader>
            {sectionIsOpen("custom_fields") ? <CardContent className="grid gap-3 sm:grid-cols-2">
              {profile.custom_fields.length ? profile.custom_fields.map((field, index) => (
                <div key={field.id} className="space-y-1.5">
                  <Label htmlFor={`profile-custom-${field.id}`}>{field.label}</Label>
                  {field.kind === "boolean" ? <label className="flex h-9 items-center gap-2 rounded-lg border px-3 text-sm">
                    <input id={`profile-custom-${field.id}`} type="checkbox" checked={field.value === true} onChange={(event) => mutate((draft) => { draft.custom_fields[index].value = event.target.checked; })} />
                    {field.value === true ? "Yes" : "No"}
                  </label> : field.kind === "select" ? <select id={`profile-custom-${field.id}`} value={typeof field.value === "string" ? field.value : ""} onChange={(event) => mutate((draft) => { draft.custom_fields[index].value = event.target.value || null; })} className="h-9 w-full rounded-lg border border-input bg-background px-3 text-sm">
                    <option value="">—</option>{field.options.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select> : <Input
                    id={`profile-custom-${field.id}`}
                    type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"}
                    value={field.value == null ? "" : String(field.value)}
                    onChange={(event) => mutate((draft) => {
                      draft.custom_fields[index].value = field.kind === "number"
                        ? (event.target.value === "" ? null : Number(event.target.value))
                        : (event.target.value || null);
                    })}
                  />}
                </div>
              )) : <p className="text-sm text-muted-foreground sm:col-span-2">No organization custom fields are configured.</p>}
            </CardContent> : null}
          </Card>
        </div>

        <aside className="min-w-0 xl:sticky xl:top-20">
          <ProfileDocumentPreview
            profile={presentation}
            template={selectedTemplate}
            label="Anonymized A4 layout preview"
          />
        </aside>
      </div>
    </div>
  );
}
