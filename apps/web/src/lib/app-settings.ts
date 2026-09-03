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

export const SETTINGS_SCHEMA_VERSION = 2;
export const SETTINGS_STORAGE_KEY = "cv-analyzer-settings-v2";
export const LEGACY_SETTINGS_STORAGE_KEY = "cv-analyzer-settings-v1";
const EVENT_NAME = "cv-analyzer-settings-changed";
export const DEFAULT_SETTINGS: AppSettings = {
  uiLanguage: "en", reportLanguage: "en",
  aiEnabled: true,
  autoResearchEnabled: true, autoCompanyResearch: true,
  autoEducationResearch: true, autoLinkedinDiscovery: true,
  previewFindingsOnHover: false,
  expandSectionsByDefault: false,
};

function parseObject(raw: string | null): Record<string, unknown> | null {
  try {
    const value = JSON.parse(raw ?? "null");
    return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

function normalizeSettings(value: Record<string, unknown>, researchDefault: boolean): AppSettings {
  return {
    uiLanguage: value.uiLanguage === "pl" ? "pl" : "en",
    reportLanguage: value.reportLanguage === "pl" ? "pl" : "en",
    aiEnabled: value.aiEnabled !== false,
    autoResearchEnabled: typeof value.autoResearchEnabled === "boolean" ? value.autoResearchEnabled : researchDefault,
    autoCompanyResearch: typeof value.autoCompanyResearch === "boolean" ? value.autoCompanyResearch : researchDefault,
    autoEducationResearch: typeof value.autoEducationResearch === "boolean" ? value.autoEducationResearch : researchDefault,
    autoLinkedinDiscovery: typeof value.autoLinkedinDiscovery === "boolean" ? value.autoLinkedinDiscovery : researchDefault,
    previewFindingsOnHover: value.previewFindingsOnHover === true,
    expandSectionsByDefault: value.expandSectionsByDefault === true,
  };
}

export function resolveStoredAppSettings(v2Raw: string | null, v1Raw: string | null): AppSettings {
  const current = parseObject(v2Raw);
  if (current?.version === SETTINGS_SCHEMA_VERSION) return normalizeSettings(current, true);
  const legacy = parseObject(v1Raw);
  if (legacy) return normalizeSettings(legacy, true);
  return DEFAULT_SETTINGS;
}

function serializeSettings(settings: AppSettings) {
  return JSON.stringify({ version: SETTINGS_SCHEMA_VERSION, ...settings });
}

type SettingsStorage = Pick<Storage, "getItem" | "setItem">;
function safeGet(storage: SettingsStorage, key: string) {
  try { return storage.getItem(key); } catch { return null; }
}

export function loadStoredAppSettings(storage: SettingsStorage): AppSettings {
  return resolveStoredAppSettings(safeGet(storage, SETTINGS_STORAGE_KEY), safeGet(storage, LEGACY_SETTINGS_STORAGE_KEY));
}

export function persistMigratedAppSettings(storage: SettingsStorage): void {
  const current = safeGet(storage, SETTINGS_STORAGE_KEY);
  const legacy = safeGet(storage, LEGACY_SETTINGS_STORAGE_KEY);
  if (current !== null || legacy === null) return;
  try { storage.setItem(SETTINGS_STORAGE_KEY, serializeSettings(resolveStoredAppSettings(null, legacy))); } catch { /* Persistence is optional; rendering must remain available. */ }
}

function readSettings(): AppSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  return loadStoredAppSettings(window.localStorage);
}

let cachedRaw = "";
let cachedSettings = DEFAULT_SETTINGS;
function snapshot() {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  const raw = `${safeGet(window.localStorage, SETTINGS_STORAGE_KEY) ?? ""}\u0000${safeGet(window.localStorage, LEGACY_SETTINGS_STORAGE_KEY) ?? ""}`;
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
  try { window.localStorage.setItem(SETTINGS_STORAGE_KEY, serializeSettings(next)); } catch { return; }
  window.dispatchEvent(new Event(EVENT_NAME));
}

export function useAppSettings() {
  const settings = useSyncExternalStore(subscribe, snapshot, () => DEFAULT_SETTINGS);
  useEffect(() => {
    persistMigratedAppSettings(window.localStorage);
    document.documentElement.lang = settings.uiLanguage;
  }, [settings.uiLanguage]);
  return settings;
}

const copy = {
  en: {
    analysis: "Analysis", analyze: "Analyze", dashboard: "Dashboard", settings: "Settings",
    uploadTitle: "Upload CV files",
    drop: "Drag and drop files here, or click to select", accepted: "Accepted: PDF, DOCX",
    queued: "Queued files", valid: "valid", analyzeFiles: "Analyze files", reset: "Reset",
    results: "Analysis results", back: "Back",
    showCv: "Show CV", hideCv: "Hide CV",
    recentAnalyses: "Recent analyses", noHistory: "No saved analyses yet.", showMoreAnalyses: "Show more ({count})", showFewerAnalyses: "Show fewer",
    originalNotRetained: "The original CV was not retained.", documentFetchFailed: "The stored CV could not be loaded.", deleteAnalysis: "Delete analysis",
    dataRetention: "Data retention", keepFor: "Keep completed analyses for", days: "days", save: "Save",
    deleteAll: "Delete all analyses", confirmDeleteAll: "Confirm delete all", deleting: "Deleting...",
    health: "System health", refresh: "Refresh status", refreshing: "Refreshing...", updated: "Updated", ready: "Ready", degraded: "Needs attention",
    needsAttention: "Needs attention", worthKnowing: "Worth knowing", remaining: "Remaining signals",
    extracted: "CV overview", whyItMatters: "Why it matters", whatToCheck: "What to check", evidence: "Evidence",
    contact: "Contact", candidateName: "Candidate name", phoneNumber: "Phone number", location: "Location",
    statedLocation: "Stated location", resolvedLocation: "Resolved location", postalCode: "Postal code", postalCountry: "Postal country", euStatus: "EU status",
    outsideEu: "Outside the EU", insideEu: "Inside the EU", education: "Education", educationEntry: "Education entry", experience: "Experience", employmentEntry: "Employment entry",
    noCvDetails: "No CV details extracted.",
    closeFeedback: "Close feedback", reportProblem: "Report a problem", rateResult: "Rate result", giveFeedback: "Give feedback", resultFeedback: "Result feedback", helpful: "Helpful", needsImprovement: "Needs improvement", whatToImprove: "What should be improved?", writeFeedback: "Write feedback…", feedbackComment: "Comment", sendFeedback: "Send feedback", feedbackSelectionRequired: "Choose a rating or add a comment", feedbackCommentTooShort: "Comment needs 12 characters", feedbackSaveFailed: "Could not save feedback", feedbackSent: "Sent!",
    feedbackFilters: "Filters", feedbackStatusFilters: "Status filters", all: "All", statusNew: "New", statusReviewing: "Reviewing", statusPlanned: "Planned", statusResolved: "Resolved", statusWontFix: "Won't fix", manageAccess: "Manage access", loadingFeedback: "Loading feedback…", current: "Current", deleteFeedback: "Delete feedback", confirmDeleteFeedback: "Click again to delete feedback", clickAgainToConfirm: "Click again to confirm", commentFrom: "Comment from: {author}", unknownAuthor: "unknown author", showCvExcerpt: "Show CV excerpt", errorDetails: "Error details", teamNote: "Team note", teamNotePlaceholder: "Add context, a decision, or the next step…", saveNote: "Save note", noFeedbackForFilter: "No feedback for this filter.", unsavedFeedbackNote: "You have an unsaved feedback note. Leave this page?", feedbackUpdateFailed: "Could not save changes.", feedbackDeleteFailed: "Could not delete feedback.", feedbackAccess: "Feedback access", feedbackAccessDescription: "Manage who can view and handle feedback.", feedbackCollection: "Feedback collection", feedbackCollectionDescription: "Controls feedback buttons and new responses. The inbox remains available.", enabled: "Enabled", disabled: "Disabled", companyEmail: "Company email", reviewer: "Reviewer", owner: "Owner", grantAccess: "Grant access", revokeAccess: "Revoke",
    uiLanguage: "UI language", reportLanguage: "AI report language", reportLanguageDescription: "Applied to newly generated AI explanations.",
    analysisSettings: "Research settings", analysisSettingsDescription: "Control optional public company, education, and LinkedIn research.",
    useAiFeatures: "Use public AI research", useAiFeaturesDescription: "Enables company, education, and LinkedIn research after base analysis.", aiUnavailable: "Public research is unavailable on this deployment.",
    previewFindingsOnHover: "Auto-expand finding details on hover", expandSectionsByDefault: "Expand sections by default",
    runResearchAutomatically: "Run research automatically", companyResearch: "Company research", educationResearch: "Education research",
    linkedinDiscovery: "LinkedIn discovery", linkedinDiscoveryDescription: "LinkedIn discovery suggests possible public profiles only.",
    openFeatureListBoard: "Open feature list board", signOut: "Sign out", toggleTheme: "Toggle theme",
    toggleSidebar: "Toggle sidebar", resizeSidebar: "Resize sidebar", dragToResizeSidebar: "Drag to resize sidebar.",
    mobileSidebar: "Sidebar", mobileSidebarDescription: "Displays the mobile sidebar.", close: "Close", allRightsReserved: "All rights reserved.",
    resizeCvPreview: "Resize CV preview", fitCvPreview: "Fit document to preview", openOriginalFile: "Open original file", hideCvPreview: "Hide CV preview",
    viewSources: "View sources ({count})", searchDetails: "Search details", searchesAndLimitations: "Searches and limitations", search: "Search", limit: "Limit", searchWithGoogle: "Search with Google", searchSubjectWithGoogle: "Search {subject} with Google", searchLinkedIn: "Search on LinkedIn", searchLinkedInFor: "Search LinkedIn for {subject}", postalConsistency: "Postal consistency", postalConsistent: "Consistent with the stated locality and country", postalMismatch: "Does not match the stated locality and country", euStatusDisclaimer: "Classifies CV information only; it does not determine residence, nationality, or work eligibility.",
    start: "Start", researching: "Researching…", discovering: "Discovering…", companyResearchInProgress: "Company research in progress", educationResearchInProgress: "Education research in progress", linkedinDiscoveryInProgress: "LinkedIn discovery in progress", researchTimedOut: "Research timed out. You can safely try again.", researchFailed: "Research failed. Try again or check System health.", automaticResearchFailed: "Automatic research failed. You can try again manually.", automaticResearchAlreadyAttempted: "Automatic research was already attempted. Use the manual action to try again.",
    noCompaniesAvailable: "No companies available to research.", noEducationEntries: "No education entries available to research.", noCandidateDetails: "No candidate details available for LinkedIn research.",
    companyFound: "Company found", conflictingCompanyInformation: "Conflicting company information", companyNotConfirmed: "Company not confirmed", reportedOfficeOrLocation: "Reported office or location", officialWebsite: "Official website", found: "Found", notConfirmed: "Not confirmed", activity: "Activity", operatingDates: "Operating dates", confidenceWithValue: "Confidence: {value}", confidenceHigh: "high", confidenceMedium: "medium", confidenceLow: "low",
    notEnoughPublicInformation: "Not enough public information.", forReview: "For review:", doesNotVerifyCandidateLocation: "This does not verify the candidate's location.",
    linkedinProfiles: "LinkedIn profile research", startDiscovery: "Start", noProfileFound: "No profile found", openProfile: "Open profile", profile: "Profile {index}", photoVisible: "Photo visible", noPublicPhoto: "No public photo", photoUnknown: "Photo unknown", lowConnectionCount: "Low connection count", connections: "Connections: {count}", connectionsUnknown: "Connections unknown",
    autoResearch: "Auto research: {kinds}.", analyzing: "Analyzing {current} of {total}", analyzingStatus: "Analyzing", analysisComplete: "Analysis complete", reportReady: "Your report is ready.", elapsed: "Elapsed {time}", estimatedRemaining: "Estimated remaining about {time}", takingLonger: "Taking longer than usual", completed: "Completed", failed: "Failed", waiting: "Waiting", batchResultsInHistory: "Finished reports are listed under Recent analyses.", newAnalysis: "New", addFile: "Add at least one PDF or DOCX file.", unexpectedAnalysisError: "Unexpected analysis error.", noResult: "No result was returned", analysisFailed: "Analysis failed. Try again or check System health.", analysisFailedWithStatus: "Analysis failed ({status})", docxPreviewFailed: "This DOCX could not be previewed. You can still open the original file.",
    historyUnavailable: "Analysis history is unavailable.", analysisUnavailable: "This analysis is no longer available.", confirmDeleteAnalysis: "Delete {name}?", analysisCouldNotDelete: "The analysis could not be deleted.",
    retentionUnavailable: "Retention settings are unavailable.", enterWholeNumber: "Enter a whole number from 1 to 3650.", saved: "Saved.", retentionCouldNotSave: "Retention could not be saved.", allAnalysesDeleted: "All saved analyses were deleted.", analysesCouldNotDelete: "Analyses could not be deleted.", apiHealthUnavailable: "The API health check is unavailable.",
    database: "Database", geoNamesResolver: "GeoNames location resolver", postalReferenceData: "Postal reference data", baseAnalysis: "Base analysis strategy", linkedinResearch: "LinkedIn research",
    welcomeBack: "Welcome back", signInDescription: "Sign in to CV Analyzer with your Idego Google account.", signIn: "Sign in", continueWithGoogle: "Continue with Google", signInWithGoogle: "Sign in with Google", signingIn: "Signing in...", googleSsoOnly: "Google SSO only", googleOAuthNotConfigured: "Google OAuth is not configured.", unableToSignIn: "Unable to sign in.",
  },
  pl: {
    analysis: "Analiza", analyze: "Analizuj", dashboard: "Dashboard", settings: "Ustawienia",
    uploadTitle: "Dodaj pliki CV",
    drop: "Przeciągnij pliki tutaj lub kliknij, aby je wybrać", accepted: "Obsługiwane: PDF, DOCX",
    queued: "Pliki w kolejce", valid: "poprawnych", analyzeFiles: "Analizuj pliki", reset: "Wyczyść",
    results: "Wyniki analizy", back: "Wróć",
    showCv: "Pokaż CV", hideCv: "Ukryj CV",
    recentAnalyses: "Ostatnie analizy", noHistory: "Brak zapisanych analiz.", showMoreAnalyses: "Pokaż więcej ({count})", showFewerAnalyses: "Pokaż mniej",
    originalNotRetained: "Oryginalny plik CV nie został zachowany.", documentFetchFailed: "Nie udało się wczytać zapisanego CV.", deleteAnalysis: "Usuń analizę",
    dataRetention: "Retencja danych", keepFor: "Przechowuj ukończone analizy przez", days: "dni", save: "Zapisz",
    deleteAll: "Usuń wszystkie analizy", confirmDeleteAll: "Potwierdź usunięcie", deleting: "Usuwanie...",
    health: "Stan systemu", refresh: "Odśwież status", refreshing: "Odświeżanie...", updated: "Zaktualizowano", ready: "Gotowe", degraded: "Wymaga uwagi",
    needsAttention: "Wymaga uwagi", worthKnowing: "Warto wiedzieć", remaining: "Pozostałe sygnały",
    extracted: "Podsumowanie CV", whyItMatters: "Dlaczego to ważne", whatToCheck: "Co sprawdzić", evidence: "Dowód",
    contact: "Kontakt", candidateName: "Imię i nazwisko kandydata", phoneNumber: "Numer telefonu", location: "Lokalizacja",
    statedLocation: "Deklarowana lokalizacja", resolvedLocation: "Rozpoznana lokalizacja", postalCode: "Kod pocztowy", postalCountry: "Kraj kodu pocztowego", euStatus: "Status UE",
    outsideEu: "Poza UE", insideEu: "W UE", education: "Edukacja", educationEntry: "Wpis edukacyjny", experience: "Doświadczenie", employmentEntry: "Wpis zatrudnienia",
    noCvDetails: "Nie wyodrębniono danych z CV.",
    closeFeedback: "Zamknij feedback", reportProblem: "Zgłoś problem", rateResult: "Oceń wynik", giveFeedback: "Przekaż opinię", resultFeedback: "Feedback do wyniku", helpful: "Pomocny", needsImprovement: "Do poprawy", whatToImprove: "Co poprawić?", writeFeedback: "Napisz…", feedbackComment: "Komentarz", sendFeedback: "Wyślij", feedbackSelectionRequired: "Wybierz ocenę lub dodaj komentarz", feedbackCommentTooShort: "Komentarz musi mieć 12 znaków", feedbackSaveFailed: "Nie udało się zapisać", feedbackSent: "Wysłano!",
    feedbackFilters: "Filtry", feedbackStatusFilters: "Filtry statusu", all: "Wszystkie", statusNew: "Nowy", statusReviewing: "W trakcie", statusPlanned: "Zaplanowany", statusResolved: "Rozwiązany", statusWontFix: "Nie naprawiamy", manageAccess: "Zarządzaj dostępem", loadingFeedback: "Ładowanie feedbacku…", current: "Aktualny", deleteFeedback: "Usuń feedback", confirmDeleteFeedback: "Kliknij ponownie, aby usunąć feedback", clickAgainToConfirm: "Kliknij ponownie, aby potwierdzić", commentFrom: "Komentarz od: {author}", unknownAuthor: "autor nieznany", showCvExcerpt: "Pokaż fragment CV", errorDetails: "Szczegóły błędu", teamNote: "Notatka zespołu", teamNotePlaceholder: "Dodaj kontekst, decyzję albo kolejny krok…", saveNote: "Zapisz notatkę", noFeedbackForFilter: "Brak feedbacku dla wybranego filtra.", unsavedFeedbackNote: "Masz niezapisaną notatkę do feedbacku. Czy na pewno chcesz opuścić stronę?", feedbackUpdateFailed: "Nie udało się zapisać zmian.", feedbackDeleteFailed: "Nie udało się usunąć feedbacku.", feedbackAccess: "Dostęp do feedbacku", feedbackAccessDescription: "Zarządzaj osobami, które mogą przeglądać i obsługiwać feedback.", feedbackCollection: "Zbieranie feedbacku", feedbackCollectionDescription: "Steruje przyciskami i nowymi odpowiedziami. Inbox pozostaje dostępny.", enabled: "Włączone", disabled: "Wyłączone", companyEmail: "Firmowy adres e-mail", reviewer: "Recenzent", owner: "Właściciel", grantAccess: "Nadaj dostęp", revokeAccess: "Cofnij",
    uiLanguage: "Język interfejsu", reportLanguage: "Język raportu AI", reportLanguageDescription: "Dotyczy nowo wygenerowanych wyjaśnień AI.",
    analysisSettings: "Ustawienia researchu", analysisSettingsDescription: "Steruj opcjonalnym researchem firm, edukacji i profili LinkedIn.",
    useAiFeatures: "Używaj publicznego researchu AI", useAiFeaturesDescription: "Włącza research firm, edukacji i LinkedIn po analizie bazowej.", aiUnavailable: "Publiczny research jest niedostępny w tym środowisku.",
    previewFindingsOnHover: "Automatycznie rozwijaj szczegóły po najechaniu", expandSectionsByDefault: "Rozwijaj sekcje domyślnie",
    runResearchAutomatically: "Uruchamiaj wyszukiwania automatycznie", companyResearch: "Sprawdzanie firm", educationResearch: "Sprawdzanie edukacji",
    linkedinDiscovery: "Wyszukiwanie profili LinkedIn", linkedinDiscoveryDescription: "Wyszukiwanie LinkedIn pokazuje tylko możliwe profile publiczne.",
    openFeatureListBoard: "Otwórz tablicę listy funkcji", signOut: "Wyloguj się", toggleTheme: "Przełącz motyw",
    toggleSidebar: "Przełącz pasek boczny", resizeSidebar: "Zmień szerokość paska bocznego", dragToResizeSidebar: "Przeciągnij, aby zmienić szerokość paska bocznego.",
    mobileSidebar: "Pasek boczny", mobileSidebarDescription: "Wyświetla mobilny pasek boczny.", close: "Zamknij", allRightsReserved: "Wszelkie prawa zastrzeżone.",
    resizeCvPreview: "Zmień szerokość podglądu CV", fitCvPreview: "Dopasuj dokument do podglądu", openOriginalFile: "Otwórz oryginalny plik", hideCvPreview: "Ukryj podgląd CV",
    viewSources: "Pokaż źródła ({count})", searchDetails: "Szczegóły wyszukiwania", searchesAndLimitations: "Wyszukiwania i ograniczenia", search: "Wyszukiwanie", limit: "Ograniczenie", searchWithGoogle: "Wyszukaj w Google", searchSubjectWithGoogle: "Wyszukaj {subject} w Google", searchLinkedIn: "Wyszukaj na LinkedIn", searchLinkedInFor: "Wyszukaj {subject} na LinkedIn", postalConsistency: "Zgodność kodu pocztowego", postalConsistent: "Zgodny z deklarowaną miejscowością i krajem", postalMismatch: "Niezgodny z deklarowaną miejscowością i krajem", euStatusDisclaimer: "Klasyfikuje wyłącznie dane z CV; nie określa miejsca pobytu, narodowości ani prawa do pracy.",
    start: "Uruchom", researching: "Wyszukiwanie…", discovering: "Wyszukiwanie…", companyResearchInProgress: "Trwa sprawdzanie firm", educationResearchInProgress: "Trwa sprawdzanie edukacji", linkedinDiscoveryInProgress: "Trwa wyszukiwanie profili LinkedIn", researchTimedOut: "Wyszukiwanie trwało zbyt długo. Możesz bezpiecznie spróbować ponownie.", researchFailed: "Wyszukiwanie nie powiodło się. Spróbuj ponownie lub sprawdź stan systemu.", automaticResearchFailed: "Automatyczne wyszukiwanie nie powiodło się. Możesz spróbować ponownie ręcznie.", automaticResearchAlreadyAttempted: "Automatyczne wyszukiwanie zostało już wykonane. Użyj działania ręcznego, aby spróbować ponownie.",
    noCompaniesAvailable: "Brak firm do sprawdzenia.", noEducationEntries: "Brak wpisów edukacyjnych do sprawdzenia.", noCandidateDetails: "Brak danych kandydata do wyszukania na LinkedIn.",
    companyFound: "Znaleziono firmę", conflictingCompanyInformation: "Sprzeczne informacje o firmie", companyNotConfirmed: "Nie potwierdzono firmy", reportedOfficeOrLocation: "Zgłoszone biuro lub lokalizacja", officialWebsite: "Oficjalna strona", found: "Znaleziono", notConfirmed: "Nie potwierdzono", activity: "Działalność", operatingDates: "Okres działalności", confidenceWithValue: "Pewność: {value}", confidenceHigh: "wysoka", confidenceMedium: "średnia", confidenceLow: "niska",
    notEnoughPublicInformation: "Za mało informacji publicznych.", forReview: "Do sprawdzenia:", doesNotVerifyCandidateLocation: "To nie potwierdza lokalizacji kandydata.",
    linkedinProfiles: "Sprawdzanie profilu LinkedIn", startDiscovery: "Uruchom", noProfileFound: "Nie znaleziono profilu", openProfile: "Otwórz profil", profile: "Profil {index}", photoVisible: "Widoczne zdjęcie", noPublicPhoto: "Brak publicznego zdjęcia", photoUnknown: "Nie wiadomo, czy zdjęcie jest widoczne", lowConnectionCount: "Mała liczba kontaktów", connections: "Kontakty: {count}", connectionsUnknown: "Liczba kontaktów nieznana",
    autoResearch: "Automatyczne wyszukiwania: {kinds}.", analyzing: "Analizowanie {current} z {total}", analyzingStatus: "Analizowanie", analysisComplete: "Analiza zakończona", reportReady: "Raport jest gotowy.", elapsed: "Czas: {time}", estimatedRemaining: "Szacowany pozostały czas: około {time}", takingLonger: "To trwa dłużej niż zwykle", completed: "Ukończono", failed: "Niepowodzenie", waiting: "Oczekiwanie", batchResultsInHistory: "Gotowe raporty znajdziesz w Ostatnich analizach.", newAnalysis: "Nowa", addFile: "Dodaj co najmniej jeden plik PDF lub DOCX.", unexpectedAnalysisError: "Wystąpił nieoczekiwany błąd analizy.", noResult: "Nie zwrócono wyniku", analysisFailed: "Analiza nie powiodła się. Spróbuj ponownie lub sprawdź stan systemu.", analysisFailedWithStatus: "Analiza nie powiodła się ({status})", docxPreviewFailed: "Nie udało się wyświetlić tego pliku DOCX. Możesz nadal otworzyć oryginalny plik.",
    historyUnavailable: "Historia analiz jest niedostępna.", analysisUnavailable: "Ta analiza nie jest już dostępna.", confirmDeleteAnalysis: "Usunąć {name}?", analysisCouldNotDelete: "Nie udało się usunąć analizy.",
    retentionUnavailable: "Ustawienia retencji są niedostępne.", enterWholeNumber: "Wpisz liczbę całkowitą od 1 do 3650.", saved: "Zapisano.", retentionCouldNotSave: "Nie udało się zapisać retencji.", allAnalysesDeleted: "Usunięto wszystkie zapisane analizy.", analysesCouldNotDelete: "Nie udało się usunąć analiz.", apiHealthUnavailable: "Sprawdzenie stanu API jest niedostępne.",
    database: "Baza danych", geoNamesResolver: "Resolver lokalizacji GeoNames", postalReferenceData: "Dane referencyjne kodów pocztowych", baseAnalysis: "Strategia analizy bazowej", linkedinResearch: "Wyszukiwanie LinkedIn",
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
