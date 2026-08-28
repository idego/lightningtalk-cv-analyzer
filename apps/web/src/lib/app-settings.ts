"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";

export type AppLanguage = "en" | "pl";

export type AppSettings = {
  uiLanguage: AppLanguage;
  reportLanguage: AppLanguage;
  aiEnabled: boolean;
  autoResearchEnabled: boolean;
  autoCompanyResearch: boolean;
  autoEducationResearch: boolean;
  autoLinkedinDiscovery: boolean;
  previewFindingsOnHover: boolean;
  expandSectionsByDefault: boolean;
};

const STORAGE_KEY = "cv-analyzer-settings-v1";
const EVENT_NAME = "cv-analyzer-settings-changed";
const DEFAULT_SETTINGS: AppSettings = {
  uiLanguage: "en", reportLanguage: "en",
  aiEnabled: true,
  autoResearchEnabled: false, autoCompanyResearch: false,
  autoEducationResearch: false, autoLinkedinDiscovery: false,
  previewFindingsOnHover: false,
  expandSectionsByDefault: false,
};

function readSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const value = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}");
    return {
      uiLanguage: value.uiLanguage === "pl" ? "pl" : "en",
      reportLanguage: value.reportLanguage === "pl" ? "pl" : "en",
      aiEnabled: value.aiEnabled !== false,
      autoResearchEnabled: value.autoResearchEnabled === true,
      autoCompanyResearch: value.autoCompanyResearch === true,
      autoEducationResearch: value.autoEducationResearch === true,
      autoLinkedinDiscovery: value.autoLinkedinDiscovery === true,
      previewFindingsOnHover: value.previewFindingsOnHover === true,
      expandSectionsByDefault: value.expandSectionsByDefault === true,
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
    uiLanguage: "UI language", reportLanguage: "AI report language", reportLanguageDescription: "Applied to newly generated AI explanations.",
    analysisSettings: "Analysis settings", analysisSettingsDescription: "Control optional AI analysis and public research.",
    useAiFeatures: "Use AI features", useAiFeaturesDescription: "Runs AI document analysis and enables company, education, and LinkedIn research.", aiUnavailable: "AI features are unavailable on this deployment.",
    previewFindingsOnHover: "Auto-expand finding details on hover", expandSectionsByDefault: "Expand sections by default",
    runResearchAutomatically: "Run research automatically", companyResearch: "Company research", educationResearch: "Education research",
    linkedinDiscovery: "LinkedIn discovery", linkedinDiscoveryDescription: "LinkedIn discovery suggests possible public profiles only.",
    openFeatureListBoard: "Open feature list board", signOut: "Sign out", toggleTheme: "Toggle theme",
    toggleSidebar: "Toggle sidebar", resizeSidebar: "Resize sidebar", dragToResizeSidebar: "Drag to resize sidebar.",
    mobileSidebar: "Sidebar", mobileSidebarDescription: "Displays the mobile sidebar.", close: "Close", allRightsReserved: "All rights reserved.",
    resizeCvPreview: "Resize CV preview", openOriginalFile: "Open original file", hideCvPreview: "Hide CV preview",
    whyItMatters: "Why it matters", whatToCheck: "What to check", evidence: "Evidence",
    contact: "Contact", candidateName: "Candidate name", phoneNumber: "Phone number", location: "Location",
    statedLocation: "Stated location", resolvedLocation: "Resolved location", postalCode: "Postal code", postalCountry: "Postal country", euStatus: "EU status",
    outsideEu: "Outside the EU", insideEu: "Inside the EU", education: "Education", educationEntry: "Education entry", experience: "Experience", employmentEntry: "Employment entry",
    noCvDetails: "No CV details extracted.", checksRun: "Checks run", aiAnalysisInProgress: "AI analysis in progress", retryingAi: "Retrying…", retryAi: "Retry AI analysis",
    fileDetails: "File details", unavailable: "Unavailable", metadataDisclaimer: "Metadata is document context only. It does not establish authenticity, identity, or location.",
    author: "Author", creator: "Creator", producer: "Producer", title: "Title", subject: "Subject", creationTime: "Creation time", modificationTime: "Modification time", created: "Created", modified: "Modified", lastModifier: "Last modifier", revision: "Revision",
    linkInspection: "Link inspection", documentLinkChecksOnly: "Document-level checks only; they do not make a candidate-level finding.", inspected: "{count} inspected", suspiciousDocumentLinks: "{count} suspicious document links", unavailableDocumentLinks: "{count} unavailable document links", reachable: "Reachable", notChecked: "Not checked", embeddedHyperlinkTarget: "Embedded hyperlink target", documentLinkNeedsReview: "Document link needs review.", displayedValue: "Displayed value", sanitizedTarget: "Sanitized target", reasonCode: "Reason code", source: "Source", page: "page", terminalStatus: "Terminal status", terminalDomain: "Terminal domain", sourceEvidence: "Source evidence", reviewDeclaration: "Review the declaration and its source in the CV. This outcome is not proof of a candidate problem.",
    viewSources: "View sources ({count})", sourceNumber: "Source {index}", searchDetails: "Search details", searchesAndLimitations: "Searches and limitations", search: "Search", limit: "Limit",
    start: "Start", researching: "Researching…", discovering: "Discovering…", companyResearchInProgress: "Company research in progress", educationResearchInProgress: "Education research in progress", linkedinDiscoveryInProgress: "LinkedIn discovery in progress", researchTimedOut: "Research timed out. You can safely try again.", researchFailed: "Research failed. Try again or check System health.", automaticResearchFailed: "Automatic research failed. You can try again manually.", automaticResearchAlreadyAttempted: "Automatic research was already attempted. Use the manual action to try again.",
    noCompaniesAvailable: "No companies available to research.", noEducationEntries: "No education entries available to research.", noCandidateDetails: "No candidate details available for LinkedIn research.",
    companyFound: "Company found", conflictingCompanyInformation: "Conflicting company information", companyNotConfirmed: "Company not confirmed", reportedOfficeOrLocation: "Reported office or location", officialWebsite: "Official website", found: "Found", notConfirmed: "Not confirmed", activity: "Activity", operatingDates: "Operating dates", confidenceWithValue: "Confidence: {value}", confidenceHigh: "high", confidenceMedium: "medium", confidenceLow: "low",
    institutionConfirmed: "Institution confirmed", institutionMismatch: "Institution mismatch", institutionNotConfirmed: "Institution not confirmed", accreditationConfirmed: "Accreditation confirmed", accreditationNotConfirmed: "Accreditation not confirmed", accreditationUnknown: "Accreditation unknown", notEnoughPublicInformation: "Not enough public information.", forReview: "For review:", doesNotVerifyCandidateLocation: "This does not verify the candidate's location.",
    linkedinProfiles: "LinkedIn profiles", startDiscovery: "Start discovery", noProfileFound: "No profile found", severalPossibleMatches: "Several possible matches. Review required.", openProfile: "Open profile", profile: "Profile {index}", photoVisible: "Photo visible", noPublicPhoto: "No public photo", photoUnknown: "Photo unknown", lowConnectionCount: "Low connection count", connections: "Connections: {count}", connectionsUnknown: "Connections unknown",
    autoResearch: "Auto research: {kinds}.", analyzing: "Analyzing {current} of {total}", analyzingStatus: "Analyzing", elapsed: "Elapsed {time}", estimatedRemaining: "Estimated remaining about {time}", takingLonger: "Taking longer than usual", completed: "Completed", failed: "Failed", waiting: "Waiting", analyzedCount: "{completed} of {total} analyzed", addFile: "Add at least one PDF or DOCX file.", unexpectedAnalysisError: "Unexpected analysis error.", noResult: "No result was returned", analysisFailed: "Analysis failed. Try again or check System health.", analysisFailedWithStatus: "Analysis failed ({status})", docxPreviewFailed: "This DOCX could not be previewed. You can still open the original file.",
    historyUnavailable: "Analysis history is unavailable.", analysisUnavailable: "This analysis is no longer available.", confirmDeleteAnalysis: "Delete {name}?", analysisCouldNotDelete: "The analysis could not be deleted.",
    retentionUnavailable: "Retention settings are unavailable.", enterWholeNumber: "Enter a whole number from 1 to 3650.", saved: "Saved.", retentionCouldNotSave: "Retention could not be saved.", allAnalysesDeleted: "All saved analyses were deleted.", analysesCouldNotDelete: "Analyses could not be deleted.", apiHealthUnavailable: "The API health check is unavailable.",
    database: "Database", geoNamesResolver: "GeoNames location resolver", aiDocumentAnalysis: "AI document analysis", linkedinResearch: "LinkedIn research", linkChecks: "Link checks",
    welcomeBack: "Welcome back", signInDescription: "Sign in to CV Analyzer with your Idego Google account.", signIn: "Sign in", continueWithGoogle: "Continue with Google", signInWithGoogle: "Sign in with Google", signingIn: "Signing in...", googleSsoOnly: "Google SSO only", googleOAuthNotConfigured: "Google OAuth is not configured.", unableToSignIn: "Unable to sign in.",
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
    uiLanguage: "Język interfejsu", reportLanguage: "Język raportu AI", reportLanguageDescription: "Dotyczy nowo wygenerowanych wyjaśnień AI.",
    analysisSettings: "Ustawienia analizy", analysisSettingsDescription: "Steruj opcjonalną analizą AI i wyszukiwaniem publicznym.",
    useAiFeatures: "Używaj funkcji AI", useAiFeaturesDescription: "Uruchamia analizę dokumentu AI oraz wyszukiwanie firm, edukacji i profili LinkedIn.", aiUnavailable: "Funkcje AI są niedostępne w tym środowisku.",
    previewFindingsOnHover: "Automatycznie rozwijaj szczegóły po najechaniu", expandSectionsByDefault: "Rozwijaj sekcje domyślnie",
    runResearchAutomatically: "Uruchamiaj wyszukiwania automatycznie", companyResearch: "Sprawdzanie firm", educationResearch: "Sprawdzanie edukacji",
    linkedinDiscovery: "Wyszukiwanie profili LinkedIn", linkedinDiscoveryDescription: "Wyszukiwanie LinkedIn pokazuje tylko możliwe profile publiczne.",
    openFeatureListBoard: "Otwórz tablicę listy funkcji", signOut: "Wyloguj się", toggleTheme: "Przełącz motyw",
    toggleSidebar: "Przełącz pasek boczny", resizeSidebar: "Zmień szerokość paska bocznego", dragToResizeSidebar: "Przeciągnij, aby zmienić szerokość paska bocznego.",
    mobileSidebar: "Pasek boczny", mobileSidebarDescription: "Wyświetla mobilny pasek boczny.", close: "Zamknij", allRightsReserved: "Wszelkie prawa zastrzeżone.",
    resizeCvPreview: "Zmień szerokość podglądu CV", openOriginalFile: "Otwórz oryginalny plik", hideCvPreview: "Ukryj podgląd CV",
    whyItMatters: "Dlaczego to ważne", whatToCheck: "Co sprawdzić", evidence: "Dowód",
    contact: "Kontakt", candidateName: "Imię i nazwisko kandydata", phoneNumber: "Numer telefonu", location: "Lokalizacja",
    statedLocation: "Deklarowana lokalizacja", resolvedLocation: "Rozpoznana lokalizacja", postalCode: "Kod pocztowy", postalCountry: "Kraj kodu pocztowego", euStatus: "Status UE",
    outsideEu: "Poza UE", insideEu: "W UE", education: "Edukacja", educationEntry: "Wpis edukacyjny", experience: "Doświadczenie", employmentEntry: "Wpis zatrudnienia",
    noCvDetails: "Nie wyodrębniono danych z CV.", checksRun: "Wykonane sprawdzenia", aiAnalysisInProgress: "Trwa analiza AI", retryingAi: "Ponawianie…", retryAi: "Ponów analizę AI",
    fileDetails: "Szczegóły pliku", unavailable: "Niedostępne", metadataDisclaimer: "Metadane są tylko kontekstem dokumentu. Nie potwierdzają autentyczności, tożsamości ani lokalizacji.",
    author: "Autor", creator: "Twórca", producer: "Producent", title: "Tytuł", subject: "Temat", creationTime: "Czas utworzenia", modificationTime: "Czas modyfikacji", created: "Utworzono", modified: "Zmodyfikowano", lastModifier: "Ostatni modyfikujący", revision: "Wersja",
    linkInspection: "Sprawdzanie linków", documentLinkChecksOnly: "To tylko sprawdzenia na poziomie dokumentu; nie tworzą ustalenia dotyczącego kandydata.", inspected: "Sprawdzono: {count}", suspiciousDocumentLinks: "Podejrzane linki w dokumencie: {count}", unavailableDocumentLinks: "Niedostępne linki w dokumencie: {count}", reachable: "Dostępne", notChecked: "Nie sprawdzono", embeddedHyperlinkTarget: "Docelowy adres osadzonego linku", documentLinkNeedsReview: "Link w dokumencie wymaga sprawdzenia.", displayedValue: "Widoczna wartość", sanitizedTarget: "Oczyszczony adres docelowy", reasonCode: "Kod przyczyny", source: "Źródło", page: "strona", terminalStatus: "Końcowy status", terminalDomain: "Końcowa domena", sourceEvidence: "Dowód ze źródła", reviewDeclaration: "Sprawdź deklarację i jej źródło w CV. Ten wynik nie potwierdza problemu z kandydatem.",
    viewSources: "Pokaż źródła ({count})", sourceNumber: "Źródło {index}", searchDetails: "Szczegóły wyszukiwania", searchesAndLimitations: "Wyszukiwania i ograniczenia", search: "Wyszukiwanie", limit: "Ograniczenie",
    start: "Uruchom", researching: "Wyszukiwanie…", discovering: "Wyszukiwanie…", companyResearchInProgress: "Trwa sprawdzanie firm", educationResearchInProgress: "Trwa sprawdzanie edukacji", linkedinDiscoveryInProgress: "Trwa wyszukiwanie profili LinkedIn", researchTimedOut: "Wyszukiwanie trwało zbyt długo. Możesz bezpiecznie spróbować ponownie.", researchFailed: "Wyszukiwanie nie powiodło się. Spróbuj ponownie lub sprawdź stan systemu.", automaticResearchFailed: "Automatyczne wyszukiwanie nie powiodło się. Możesz spróbować ponownie ręcznie.", automaticResearchAlreadyAttempted: "Automatyczne wyszukiwanie zostało już wykonane. Użyj działania ręcznego, aby spróbować ponownie.",
    noCompaniesAvailable: "Brak firm do sprawdzenia.", noEducationEntries: "Brak wpisów edukacyjnych do sprawdzenia.", noCandidateDetails: "Brak danych kandydata do wyszukania na LinkedIn.",
    companyFound: "Znaleziono firmę", conflictingCompanyInformation: "Sprzeczne informacje o firmie", companyNotConfirmed: "Nie potwierdzono firmy", reportedOfficeOrLocation: "Zgłoszone biuro lub lokalizacja", officialWebsite: "Oficjalna strona", found: "Znaleziono", notConfirmed: "Nie potwierdzono", activity: "Działalność", operatingDates: "Okres działalności", confidenceWithValue: "Pewność: {value}", confidenceHigh: "wysoka", confidenceMedium: "średnia", confidenceLow: "niska",
    institutionConfirmed: "Potwierdzono instytucję", institutionMismatch: "Niezgodność instytucji", institutionNotConfirmed: "Nie potwierdzono instytucji", accreditationConfirmed: "Potwierdzono akredytację", accreditationNotConfirmed: "Nie potwierdzono akredytacji", accreditationUnknown: "Akredytacja nieznana", notEnoughPublicInformation: "Za mało informacji publicznych.", forReview: "Do sprawdzenia:", doesNotVerifyCandidateLocation: "To nie potwierdza lokalizacji kandydata.",
    linkedinProfiles: "Profile LinkedIn", startDiscovery: "Wyszukaj profile", noProfileFound: "Nie znaleziono profilu", severalPossibleMatches: "Znaleziono kilka możliwych dopasowań. Wymagane sprawdzenie.", openProfile: "Otwórz profil", profile: "Profil {index}", photoVisible: "Widoczne zdjęcie", noPublicPhoto: "Brak publicznego zdjęcia", photoUnknown: "Nie wiadomo, czy zdjęcie jest widoczne", lowConnectionCount: "Mała liczba kontaktów", connections: "Kontakty: {count}", connectionsUnknown: "Liczba kontaktów nieznana",
    autoResearch: "Automatyczne wyszukiwania: {kinds}.", analyzing: "Analizowanie {current} z {total}", analyzingStatus: "Analizowanie", elapsed: "Czas: {time}", estimatedRemaining: "Szacowany pozostały czas: około {time}", takingLonger: "To trwa dłużej niż zwykle", completed: "Ukończono", failed: "Niepowodzenie", waiting: "Oczekiwanie", analyzedCount: "Przeanalizowano {completed} z {total}", addFile: "Dodaj co najmniej jeden plik PDF lub DOCX.", unexpectedAnalysisError: "Wystąpił nieoczekiwany błąd analizy.", noResult: "Nie zwrócono wyniku", analysisFailed: "Analiza nie powiodła się. Spróbuj ponownie lub sprawdź stan systemu.", analysisFailedWithStatus: "Analiza nie powiodła się ({status})", docxPreviewFailed: "Nie udało się wyświetlić tego pliku DOCX. Możesz nadal otworzyć oryginalny plik.",
    historyUnavailable: "Historia analiz jest niedostępna.", analysisUnavailable: "Ta analiza nie jest już dostępna.", confirmDeleteAnalysis: "Usunąć {name}?", analysisCouldNotDelete: "Nie udało się usunąć analizy.",
    retentionUnavailable: "Ustawienia retencji są niedostępne.", enterWholeNumber: "Wpisz liczbę całkowitą od 1 do 3650.", saved: "Zapisano.", retentionCouldNotSave: "Nie udało się zapisać retencji.", allAnalysesDeleted: "Usunięto wszystkie zapisane analizy.", analysesCouldNotDelete: "Nie udało się usunąć analiz.", apiHealthUnavailable: "Sprawdzenie stanu API jest niedostępne.",
    database: "Baza danych", geoNamesResolver: "Resolver lokalizacji GeoNames", aiDocumentAnalysis: "Analiza dokumentów AI", linkedinResearch: "Wyszukiwanie LinkedIn", linkChecks: "Sprawdzanie linków",
    welcomeBack: "Witaj ponownie", signInDescription: "Zaloguj się do CV Analyzer za pomocą firmowego konta Google Idego.", signIn: "Zaloguj się", continueWithGoogle: "Kontynuuj przez Google", signInWithGoogle: "Zaloguj się przez Google", signingIn: "Logowanie...", googleSsoOnly: "Tylko Google SSO", googleOAuthNotConfigured: "Google OAuth nie jest skonfigurowany.", unableToSignIn: "Nie udało się zalogować.",
  },
} as const;

export type CopyKey = keyof typeof copy.en;
export function useCopy() {
  const settings = useAppSettings();
  const t = useCallback((key: CopyKey, values?: Record<string, string | number>) => {
    let value = copy[settings.uiLanguage][key] as string;
    for (const [name, replacement] of Object.entries(values ?? {})) {
      value = value.replaceAll(`{${name}}`, String(replacement));
    }
    return value;
  }, [settings.uiLanguage]);
  return { settings, t };
}
