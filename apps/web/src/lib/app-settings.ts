"use client";

import { useEffect, useSyncExternalStore } from "react";

export type AppLanguage = "en" | "pl";

export type AppSettings = {
  uiLanguage: AppLanguage;
  reportLanguage: AppLanguage;
  autoResearchEnabled: boolean;
  autoCompanyResearch: boolean;
  autoEducationResearch: boolean;
  autoLinkedinDiscovery: boolean;
  previewFindingsOnHover: boolean;
};

const STORAGE_KEY = "cv-analyzer-settings-v1";
const EVENT_NAME = "cv-analyzer-settings-changed";
const DEFAULT_SETTINGS: AppSettings = {
  uiLanguage: "en", reportLanguage: "en",
  autoResearchEnabled: false, autoCompanyResearch: false,
  autoEducationResearch: false, autoLinkedinDiscovery: false,
  previewFindingsOnHover: false,
};

function readSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    return {
      uiLanguage: value.uiLanguage === "pl" ? "pl" : "en",
      reportLanguage: value.reportLanguage === "pl" ? "pl" : "en",
      autoResearchEnabled: value.autoResearchEnabled === true,
      autoCompanyResearch: value.autoCompanyResearch === true,
      autoEducationResearch: value.autoEducationResearch === true,
      autoLinkedinDiscovery: value.autoLinkedinDiscovery === true,
      previewFindingsOnHover: value.previewFindingsOnHover === true,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

let cachedRaw = "";
let cachedSettings = DEFAULT_SETTINGS;
function snapshot() {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  const raw = window.localStorage.getItem(STORAGE_KEY) ?? "";
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedSettings = readSettings();
  }
  return cachedSettings;
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT_NAME, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(EVENT_NAME, callback);
    window.removeEventListener("storage", callback);
  };
}

export function updateAppSettings(patch: Partial<AppSettings>) {
  const next = { ...readSettings(), ...patch };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function useAppSettings() {
  const settings = useSyncExternalStore(subscribe, snapshot, () => DEFAULT_SETTINGS);
  useEffect(() => {
    document.documentElement.lang = settings.uiLanguage;
  }, [settings.uiLanguage]);
  return settings;
}

const copy = {
  en: {
    analysis: "Analysis", analyze: "Analyze", settings: "Settings",
    uploadTitle: "Upload CV files",
    drop: "Drag and drop files here, or click to select", accepted: "Accepted: PDF, DOCX",
    queued: "Queued files", valid: "valid", analyzeFiles: "Analyze files", reset: "Reset",
    results: "Analysis results", back: "Back",
    needsAttention: "Needs attention", worthKnowing: "Worth knowing", remaining: "Remaining signals",
    extracted: "CV overview", deterministic: "Deterministic assessment",
    showCv: "Show CV", hideCv: "Hide CV",
    recentAnalyses: "Recent analyses", noHistory: "No saved analyses yet.",
    originalNotRetained: "The original CV was not retained.", deleteAnalysis: "Delete analysis",
    dataRetention: "Data retention", keepFor: "Keep completed analyses for", days: "days", save: "Save",
    deleteAll: "Delete all analyses", confirmDeleteAll: "Confirm delete all", deleting: "Deleting...",
    health: "System health", refresh: "Refresh status", refreshing: "Refreshing...", updated: "Updated", ready: "Ready", degraded: "Needs attention",
    uiLanguage: "UI language", reportLanguage: "AI report language",
    previewFindingsOnHover: "Preview finding details on hover",
  },
  pl: {
    analysis: "Analiza", analyze: "Analizuj", settings: "Ustawienia",
    uploadTitle: "Dodaj pliki CV",
    drop: "Przeciągnij pliki tutaj lub kliknij, aby je wybrać", accepted: "Obsługiwane: PDF, DOCX",
    queued: "Pliki w kolejce", valid: "poprawnych", analyzeFiles: "Analizuj pliki", reset: "Wyczyść",
    results: "Wyniki analizy", back: "Wróć",
    needsAttention: "Wymaga uwagi", worthKnowing: "Warto wiedzieć", remaining: "Pozostałe sygnały",
    extracted: "Podsumowanie CV", deterministic: "Ocena deterministyczna",
    showCv: "Pokaż CV", hideCv: "Ukryj CV",
    recentAnalyses: "Ostatnie analizy", noHistory: "Brak zapisanych analiz.",
    originalNotRetained: "Oryginalny plik CV nie został zachowany.", deleteAnalysis: "Usuń analizę",
    dataRetention: "Retencja danych", keepFor: "Przechowuj ukończone analizy przez", days: "dni", save: "Zapisz",
    deleteAll: "Usuń wszystkie analizy", confirmDeleteAll: "Potwierdź usunięcie", deleting: "Usuwanie...",
    health: "Stan systemu", refresh: "Odśwież status", refreshing: "Odświeżanie...", updated: "Zaktualizowano", ready: "Gotowe", degraded: "Wymaga uwagi",
    uiLanguage: "Język interfejsu", reportLanguage: "Język raportu AI",
    previewFindingsOnHover: "Pokazuj szczegóły findingów po najechaniu",
  },
} as const;

export type CopyKey = keyof typeof copy.en;
export function useCopy() {
  const settings = useAppSettings();
  return { settings, t: (key: CopyKey) => copy[settings.uiLanguage][key] };
}
