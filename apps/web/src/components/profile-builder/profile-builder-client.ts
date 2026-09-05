import {
  type CandidateProfile,
  type PersistedProfileResponse,
  type ProfileBuilderPreferences,
  type ProfileCustomFieldDefinition,
  type ProfileExtractionResponse,
  type ProfileSnapshotPayload,
  type ProfileTemplate,
  type ProfileTemplateListItem,
  type ProfessionalProposal,
  type ProfessionalSectionName,
  type RecentProfileItem,
  type StoredProfile,
} from "@/components/profile-builder/profile-builder-model";

export class ProfileBuilderApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(profileErrorMessage(status, detail));
  }
}

function profileErrorMessage(status: number, detail: unknown): string {
  const messages: Record<string, string> = {
    network_error: "Connection lost. Check your connection and try again.",
    profile_builder_ai_disabled: "CV conversion is unavailable. You can still edit saved profiles and download DOCX.",
    profile_builder_ai_disabled_for_request: "CV conversion is unavailable for this request.",
    profile_builder_file_size_limit_exceeded: "This CV is too large. Choose a PDF or DOCX no larger than 10 MB.",
    profile_builder_ingestion_failed: "This CV could not be read. Try a text-based PDF or DOCX export.",
    profile_builder_extraction_failed: "The CV could not be converted. Check the file and try again.",
    profile_pdf_converter_unavailable: "PDF export is unavailable. Download DOCX instead.",
    profile_pdf_conversion_timeout: "PDF preparation took too long. Try again or download DOCX.",
    profile_pdf_conversion_failed: "PDF preparation failed. Try again or download DOCX.",
    profile_summary_invalid_response: "A reliable summary could not be generated. Try again or edit the summary yourself.",
    profile_transform_invalid_response: "The proposed edit could not be validated. Your profile has not changed; try again.",
    profile_translation_invalid_response: "The translation could not be validated. Your profile has not changed; try again.",
    profile_builder_invalid_persistence_response: "The save could not be confirmed. Keep this page open and retry.",
  };
  if (typeof detail === "string" && messages[detail]) return messages[detail];
  if (status === 401) return "Your session has expired. Sign in again before continuing.";
  if (status === 403) return "You do not have permission to make this change.";
  if (status === 404) return "This profile or template is no longer available.";
  if (status === 413) return "This request is too large. Reduce the file or profile size and try again.";
  if (status === 422 || status === 400) return "Some details are invalid. Check your entries and try again.";
  if (status === 503 || status === 504) return "This service is temporarily unavailable. Try again shortly.";
  return "The request could not be completed. Your current edits are still here; try again.";
}

async function profileRequest(path: string, init?: RequestInit): Promise<Response> {
  try { return await fetch(`/api/profile-builder/${path}`, { cache: "no-store", ...init }); }
  catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ProfileBuilderApiError(0, "network_error");
  }
}

async function jsonRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await profileRequest(path, init);
  const payload = await response.json().catch(() => ({})) as T & { detail?: string; error?: string };
  if (!response.ok) {
    throw new ProfileBuilderApiError(
      response.status,
      payload.detail ?? payload.error ?? "profile_builder_request_failed",
    );
  }
  return payload;
}

function jsonBody(method: "POST" | "PUT", body: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export async function listProfiles() {
  return (await jsonRequest<{ profiles?: RecentProfileItem[] }>("profiles")).profiles ?? [];
}

export function getProfile(profileId: string) {
  return jsonRequest<StoredProfile>(`profiles/${encodeURIComponent(profileId)}`);
}

export async function createProfile(snapshot: ProfileSnapshotPayload) {
  const payload = await jsonRequest<PersistedProfileResponse>("profiles", jsonBody("POST", snapshot));
  if (!payload.profile_id || !payload.snapshot) {
    throw new ProfileBuilderApiError(502, "profile_builder_invalid_persistence_response");
  }
  return { profileId: payload.profile_id, snapshot: payload.snapshot };
}

export async function updateProfile(profileId: string, snapshot: ProfileSnapshotPayload) {
  const payload = await jsonRequest<{ updated?: boolean; snapshot?: ProfileSnapshotPayload }>(
    `profiles/${encodeURIComponent(profileId)}`,
    jsonBody("PUT", snapshot),
  );
  if (!payload.updated || !payload.snapshot) {
    throw new ProfileBuilderApiError(502, "profile_builder_invalid_persistence_response");
  }
  return payload.snapshot;
}

export function deleteProfile(profileId: string) {
  return jsonRequest<{ deleted: boolean }>(`profiles/${encodeURIComponent(profileId)}`, { method: "DELETE" });
}

export async function listTemplates() {
  return (await jsonRequest<{ templates?: ProfileTemplateListItem[] }>("templates")).templates ?? [];
}

export function getTemplate(templateId: string) {
  return jsonRequest<ProfileTemplateListItem>(`templates/${encodeURIComponent(templateId)}`);
}

export async function saveTemplate(template: ProfileTemplate) {
  const payload = await jsonRequest<{ saved?: boolean; template?: ProfileTemplate }>(
    `templates/${encodeURIComponent(template.id)}`,
    jsonBody("PUT", template),
  );
  if (!payload.saved || !payload.template) {
    throw new ProfileBuilderApiError(502, "profile_builder_invalid_template_response");
  }
  return payload.template;
}

export function deleteTemplate(templateId: string) {
  return jsonRequest<{ deleted: boolean; reset_to_builtin?: boolean }>(
    `templates/${encodeURIComponent(templateId)}`,
    { method: "DELETE" },
  );
}

export function getPreferences() {
  return jsonRequest<ProfileBuilderPreferences>("preferences");
}

export async function savePreferences(preferences: ProfileBuilderPreferences) {
  const payload = await jsonRequest<{ saved?: boolean; preferences?: ProfileBuilderPreferences }>(
    "preferences",
    jsonBody("PUT", preferences),
  );
  if (!payload.saved || !payload.preferences) {
    throw new ProfileBuilderApiError(502, "profile_builder_invalid_preferences_response");
  }
  return payload.preferences;
}

export async function listCustomFields() {
  return (await jsonRequest<{ fields?: ProfileCustomFieldDefinition[] }>("custom-fields")).fields ?? [];
}

export async function saveCustomField(definition: ProfileCustomFieldDefinition) {
  const payload = await jsonRequest<{ saved?: boolean; field?: ProfileCustomFieldDefinition }>(
    `custom-fields/${encodeURIComponent(definition.id)}`,
    jsonBody("PUT", definition),
  );
  if (!payload.saved || !payload.field) {
    throw new ProfileBuilderApiError(502, "profile_builder_invalid_custom_field_response");
  }
  return payload.field;
}

export function deleteCustomField(fieldId: string) {
  return jsonRequest<{ deleted: boolean }>(`custom-fields/${encodeURIComponent(fieldId)}`, { method: "DELETE" });
}

export function extractProfile(file: File, aiEnabled: boolean) {
  const form = new FormData();
  form.append("file", file, file.name);
  return jsonRequest<ProfileExtractionResponse>("extract", {
    method: "POST",
    body: form,
    headers: { "X-AI-Enabled": String(aiEnabled) },
  });
}

export async function generateProfileSummary(
  profile: CandidateProfile,
  instruction: string | null,
  aiEnabled: boolean,
) {
  const payload = await jsonRequest<{ summary?: string }>("summary", {
    ...jsonBody("POST", { profile, instruction }),
    headers: {
      "Content-Type": "application/json",
      "X-AI-Enabled": String(aiEnabled),
    },
  });
  if (!payload.summary) throw new ProfileBuilderApiError(502, "profile_summary_failed");
  return payload.summary;
}

export async function transformProfile(
  profile: CandidateProfile,
  sections: ProfessionalSectionName[],
  instruction: string,
  mode: "action" | "translation",
  targetLanguage: "en" | "pl" | "de" | "fr" | "es" | null,
  aiEnabled: boolean,
) {
  const payload = await jsonRequest<{ proposal?: ProfessionalProposal }>("transform", {
    ...jsonBody("POST", {
      profile,
      sections,
      instruction,
      mode,
      target_language: targetLanguage,
    }),
    headers: {
      "Content-Type": "application/json",
      "X-AI-Enabled": String(aiEnabled),
    },
  });
  if (!payload.proposal) throw new ProfileBuilderApiError(502, "profile_transform_failed");
  return payload.proposal;
}

export async function exportProfileSnapshot(
  format: "docx" | "pdf",
  payload: {
    profile: CandidateProfile;
    anonymization: ProfileSnapshotPayload["anonymization"];
    template_id: string;
    template: ProfileTemplate;
  },
  signal?: AbortSignal,
) {
  const response = await profileRequest(`export/${format}`, { ...jsonBody("POST", payload), signal });
  if (!response.ok) {
    const error = await response.json().catch(() => ({})) as { detail?: string; error?: string };
    throw new ProfileBuilderApiError(
      response.status,
      error.detail ?? error.error ?? `profile_${format}_export_failed`,
    );
  }
  return response.blob();
}
