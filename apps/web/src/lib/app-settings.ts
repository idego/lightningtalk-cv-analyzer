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
    queued: "Selected files", valid: "valid", analyzeFiles: "Analyze files", reset: "Reset", cancel: "Cancel", removeFile: "Remove {name}", analysisCancelled: "Analysis cancelled.",
    results: "Analysis results", back: "Back",
    showCv: "Show CV", hideCv: "Hide CV", copyAnalysisLink: "Copy link", copyingAnalysisLink: "Copying...", analysisLinkCopied: "Link copied", analysisLinkCopyFailed: "Copy failed", loadingAnalysis: "Loading analysis...", unsupportedFiles: "Unsupported files: {names}. Use PDF or DOCX.",
    searchAnalyses: "Search candidates or filenames", clearSearch: "Clear search", analysisMatchCount: "{count} of {total} analyses", noAnalysisMatches: "No matching analyses. Try another name or filename.",
    recentAnalyses: "Recent analyses", noHistory: "No analyses yet.", noHistoryDescription: "Completed CV analyses will appear here.", loadingHistory: "Loading recent analyses…", partialAnalysis: "Partial", showMoreAnalyses: "Show more ({count})", showFewerAnalyses: "Show fewer",
    originalNotRetained: "The original CV was not retained.", documentFetchFailed: "The stored CV could not be loaded.", deleteAnalysis: "Delete analysis",
    dataRetention: "Data retention", keepFor: "Keep completed analyses for", days: "days", save: "Save",
    deleteAll: "Delete all analyses", confirmDeleteAll: "Delete all", deleteAllDescription: "This permanently deletes every saved analysis and stored CV. This action cannot be undone.", deleting: "Deleting...",
    health: "System health", refresh: "Refresh status", refreshing: "Refreshing...", updated: "Updated", ready: "Ready", degraded: "Needs attention", checkingSystem: "Checking system status…", technicalDetails: "Technical details", feedbackInbox: "Feedback inbox",
    needsAttention: "Needs attention", worthKnowing: "Worth knowing",
    extracted: "CV overview", whyItMatters: "Why it matters", whatToCheck: "What to check", evidence: "Evidence",
    contact: "Contact", candidateName: "Candidate name", phoneNumber: "Phone number", location: "Location",
    statedLocation: "Stated location", resolvedLocation: "Resolved location", postalCode: "Postal code", postalCountry: "Postal country", euStatus: "EU status",
    outsideEu: "Outside the EU", insideEu: "Inside the EU", education: "Education", educationEntry: "Education entry", experience: "Experience", employmentEntry: "Employment entry",
    noCvDetails: "No CV details extracted.",
    closeFeedback: "Close feedback", reportProblem: "Report a problem", rateResult: "Rate result", giveFeedback: "Give feedback", resultFeedback: "Result feedback", helpful: "Helpful", needsImprovement: "Needs improvement", whatToImprove: "What should be improved?", writeFeedback: "Write feedback…", feedbackComment: "Comment", sendFeedback: "Send feedback", feedbackSelectionRequired: "Choose a rating or add a comment", feedbackSaveFailed: "Could not save feedback", feedbackSent: "Sent!",
    feedbackFilters: "Filters", feedbackStatusFilters: "Status filters", all: "All", statusNew: "New", statusReviewing: "Reviewing", statusPlanned: "Planned", statusResolved: "Resolved", statusWontFix: "Won't fix", manageAccess: "Manage access", loadingFeedback: "Loading feedback…", feedbackLoadFailed: "Could not load feedback. Try again.", retry: "Retry", current: "Current", deleteFeedback: "Delete feedback", confirmDeleteFeedback: "Click again to delete feedback", clickAgainToConfirm: "Click again to confirm", commentFrom: "Comment from: {author}", unknownAuthor: "unknown author", showCvExcerpt: "Show CV excerpt", showReportModule: "Show report section", errorDetails: "Error details", teamNote: "Team note", teamNotePlaceholder: "Add context, a decision, or the next step…", saveNote: "Save note", noFeedbackForFilter: "No feedback matches this filter.", noFeedbackYet: "No feedback yet.", noFeedbackYetDescription: "Ratings and comments submitted from CV analyses will appear here.", unsavedFeedbackNote: "You have an unsaved feedback note. Leave this page?", feedbackUpdateFailed: "Could not save changes.", feedbackDeleteFailed: "Could not delete feedback.", feedbackAccess: "Feedback access", feedbackAccessDescription: "Manage who can view and handle feedback.", feedbackDomainNotAllowed: "Use an email address from an allowed company domain.", lastOwnerProtected: "At least one feedback owner must remain.", feedbackAccessForbidden: "You do not have permission to manage feedback access.", feedbackAccessUpdateFailed: "Could not update feedback access.", feedbackAccessLoadFailed: "Could not load feedback access. Reload the page to try again.", loadingFeedbackAccess: "Loading feedback access…", feedbackCollection: "Feedback collection", feedbackCollectionDescription: "Allow users to rate and comment on analysis results.", enabled: "Enabled", disabled: "Disabled", companyEmail: "Company email", reviewer: "Reviewer", owner: "Owner", grantAccess: "Grant access", revokeAccess: "Revoke",
    uiLanguage: "UI language", reportLanguage: "Analysis language", reportLanguageDescription: "Used for newly generated analysis and research text.",
    analysisSettings: "Public research", analysisSettingsDescription: "Control optional checks against public sources for companies, education, and LinkedIn profiles.",
    useAiFeatures: "Use public web research", useAiFeaturesDescription: "Check public sources for companies, education, and LinkedIn profiles after CV analysis.", aiUnavailable: "Public research is unavailable on this deployment.",
    previewFindingsOnHover: "Preview finding details on hover", expandSectionsByDefault: "Expand sections by default",
    runResearchAutomatically: "Run research automatically", companyResearch: "Company research", educationResearch: "Education research",
    linkedinDiscovery: "LinkedIn profile search", linkedinDiscoveryDescription: "LinkedIn search only suggests possible public profiles; it does not verify identity.",
    openFeatureListBoard: "Open feature list board", signOut: "Sign out", toggleTheme: "Toggle theme",
    toggleSidebar: "Toggle sidebar", resizeSidebar: "Resize sidebar", dragToResizeSidebar: "Drag to resize sidebar.",
    mobileSidebar: "Sidebar", mobileSidebarDescription: "Displays the mobile sidebar.", close: "Close", allRightsReserved: "All rights reserved.",
    resizeCvPreview: "Resize CV preview", fitCvPreview: "Fit document to preview", loadingCvPreview: "Loading CV preview…", openOriginalFile: "Open original file", hideCvPreview: "Hide CV preview",
    viewSources: "View sources ({count})", searchDetails: "Search details", searchesAndLimitations: "Search details", search: "Search", limit: "Limit", searchWithGoogle: "Search with Google", searchSubjectWithGoogle: "Search {subject} with Google", searchLinkedIn: "Search on LinkedIn", searchLinkedInFor: "Search LinkedIn for {subject}", postalConsistency: "Postal consistency", postalConsistent: "Consistent with the stated locality and country", postalMismatch: "Does not match the stated locality and country",
    start: "Run research", researching: "Researching…", discovering: "Searching…", companyResearchInProgress: "Company research in progress", educationResearchInProgress: "Education research in progress", linkedinDiscoveryInProgress: "LinkedIn profile search in progress", researchTimedOut: "Research timed out. You can safely try again.", researchFailed: "Research failed. Try again or check System health.", automaticResearchFailed: "Automatic research failed. You can try again manually.", automaticResearchAlreadyAttempted: "Automatic research was already attempted. Use the manual action to try again.",
    noCompaniesAvailable: "No companies available to research.", noEducationEntries: "No education entries available to research.", noCandidateDetails: "No candidate details available for LinkedIn research.",
    companyFound: "Public company footprint found", conflictingCompanyInformation: "Public sources conflict", companyNotConfirmed: "Not confirmed in public sources", reportedOfficeOrLocation: "Reported offices", officialWebsite: "Official website", found: "Found", notConfirmed: "Not confirmed", activity: "Activity", operatingDates: "Operating dates", present: "present", until: "Until", confidenceWithValue: "Confidence: {value}", confidenceHigh: "high", confidenceMedium: "medium", confidenceLow: "low",
    notEnoughPublicInformation: "Not enough public information.", forReview: "For review:", doesNotVerifyCandidateLocation: "This does not verify the candidate's location.",
    linkedinProfiles: "LinkedIn profile search", startDiscovery: "Search", noProfileFound: "No possible profile found", openProfile: "Open profile", profile: "Possible profile {index}", photoVisible: "Photo visible", noPublicPhoto: "No public photo", photoUnknown: "Photo unknown", lowConnectionCount: "Low connection count", connections: "Connections: {count}", connectionsUnknown: "Connections unknown",
    autoResearch: "Auto research: {kinds}.", analyzing: "Analyzing {current} of {total}", analyzingStatus: "Analyzing", analysisComplete: "Analysis complete", reportReady: "Your report is ready.", elapsed: "Elapsed {time}", estimatedRemaining: "Estimated remaining about {time}", takingLonger: "Taking longer than usual", completed: "Completed", failed: "Failed", waiting: "Waiting", batchResultsInHistory: "Finished reports are listed under Recent analyses.", newAnalysis: "New", addFile: "Add at least one PDF or DOCX file.", unexpectedAnalysisError: "Unexpected analysis error.", noResult: "No result was returned", analysisFailed: "Analysis failed. Try again or check System health.", analysisFailedWithStatus: "Analysis failed ({status})", cvNeedsTextLayer: "This CV has no readable text layer. Upload a text-based PDF or DOCX.", cvCouldNotRead: "This file could not be read. Try exporting it again as PDF or DOCX.", cvTooLarge: "This file is too large to analyze.", cvEmptyFile: "This file is empty.", cvUnsupportedType: "Use a PDF or DOCX file.", analysisTemporarilyUnavailable: "CV analysis is temporarily unavailable. Check System health and try again.", uploadCouldNotRead: "The uploaded file could not be read. Try selecting it again.", docxPreviewFailed: "This DOCX could not be previewed. You can still open the original file.",
    historyUnavailable: "Analysis history is unavailable.", analysisUnavailable: "This analysis is no longer available.", analysisCouldNotDelete: "The analysis could not be deleted.",
    retentionUnavailable: "Retention settings are unavailable.", enterWholeNumber: "Enter a whole number from 1 to 3650.", saved: "Saved.", retentionCouldNotSave: "Retention could not be saved.", allAnalysesDeleted: "All saved analyses were deleted.", analysesCouldNotDelete: "Analyses could not be deleted.", apiHealthUnavailable: "The API health check is unavailable.",
    database: "Database", geoNamesResolver: "GeoNames location resolver", postalReferenceData: "Postal reference data", baseAnalysis: "Base analysis strategy", linkedinResearch: "LinkedIn research",
    welcomeBack: "Welcome back", signInDescription: "Sign in to CV Analyzer with your Idego Google account.", signIn: "Sign in", continueWithGoogle: "Continue with Google", signInWithGoogle: "Sign in with Google", signingIn: "Signing in...", googleSsoOnly: "Google SSO only", googleOAuthNotConfigured: "Google OAuth is not configured.", unableToSignIn: "Unable to sign in.",
  },
  pl: {

    analysis: "Analiza", analyze: "Analizuj", dashboard: "Dashboard", settings: "Ustawienia",
    uploadTitle: "Dodaj pliki CV",
    drop: "Przeciągnij pliki tutaj lub kliknij, aby je wybrać", accepted: "Obsługiwane: PDF, DOCX",
    queued: "Wybrane pliki", valid: "poprawnych", analyzeFiles: "Analizuj pliki", reset: "Wyczyść", cancel: "Anuluj", removeFile: "Usuń {name}", analysisCancelled: "Analiza anulowana.",
    results: "Wyniki analizy", back: "Wróć",
    showCv: "Pokaż CV", hideCv: "Ukryj CV", copyAnalysisLink: "Kopiuj link", copyingAnalysisLink: "Kopiowanie...", analysisLinkCopied: "Skopiowano link", analysisLinkCopyFailed: "Nie udało się skopiować", loadingAnalysis: "Ładowanie analizy...", unsupportedFiles: "Nieobsługiwane pliki: {names}. Użyj PDF lub DOCX.",
    searchAnalyses: "Szukaj kandydata lub pliku", clearSearch: "Wyczyść wyszukiwanie", analysisMatchCount: "{count} z {total} analiz", noAnalysisMatches: "Brak pasujących analiz. Wpisz inne nazwisko lub nazwę pliku.",
    recentAnalyses: "Ostatnie analizy", noHistory: "Brak analiz.", noHistoryDescription: "Ukończone analizy CV pojawią się tutaj.", loadingHistory: "Ładowanie ostatnich analiz…", partialAnalysis: "Częściowa", showMoreAnalyses: "Pokaż więcej ({count})", showFewerAnalyses: "Pokaż mniej",
    originalNotRetained: "Oryginalny plik CV nie został zachowany.", documentFetchFailed: "Nie udało się wczytać zapisanego CV.", deleteAnalysis: "Usuń analizę",
    dataRetention: "Retencja danych", keepFor: "Przechowuj ukończone analizy przez", days: "dni", save: "Zapisz",
    deleteAll: "Usuń wszystkie analizy", confirmDeleteAll: "Usuń wszystkie", deleteAllDescription: "To trwale usunie wszystkie zapisane analizy i przechowywane pliki CV. Tej operacji nie można cofnąć.", deleting: "Usuwanie...",
    health: "Stan systemu", refresh: "Odśwież status", refreshing: "Odświeżanie...", updated: "Zaktualizowano", ready: "Gotowe", degraded: "Wymaga uwagi", checkingSystem: "Sprawdzanie stanu systemu…", technicalDetails: "Szczegóły techniczne", feedbackInbox: "Skrzynka feedbacku",
    needsAttention: "Wymaga uwagi", worthKnowing: "Warto wiedzieć",
    extracted: "Podsumowanie CV", whyItMatters: "Dlaczego to ważne", whatToCheck: "Co sprawdzić", evidence: "Dowód",
    contact: "Kontakt", candidateName: "Imię i nazwisko kandydata", phoneNumber: "Numer telefonu", location: "Lokalizacja",
    statedLocation: "Deklarowana lokalizacja", resolvedLocation: "Rozpoznana lokalizacja", postalCode: "Kod pocztowy", postalCountry: "Kraj kodu pocztowego", euStatus: "Status UE",
    outsideEu: "Poza UE", insideEu: "W UE", education: "Edukacja", educationEntry: "Wpis edukacyjny", experience: "Doświadczenie", employmentEntry: "Wpis zatrudnienia",
    noCvDetails: "Nie wyodrębniono danych z CV.",
    closeFeedback: "Zamknij feedback", reportProblem: "Zgłoś problem", rateResult: "Oceń wynik", giveFeedback: "Przekaż opinię", resultFeedback: "Feedback do wyniku", helpful: "Pomocny", needsImprovement: "Do poprawy", whatToImprove: "Co poprawić?", writeFeedback: "Napisz…", feedbackComment: "Komentarz", sendFeedback: "Wyślij", feedbackSelectionRequired: "Wybierz ocenę lub dodaj komentarz", feedbackSaveFailed: "Nie udało się zapisać", feedbackSent: "Wysłano!",
    feedbackFilters: "Filtry", feedbackStatusFilters: "Filtry statusu", all: "Wszystkie", statusNew: "Nowy", statusReviewing: "W trakcie", statusPlanned: "Zaplanowany", statusResolved: "Rozwiązany", statusWontFix: "Nie naprawiamy", manageAccess: "Zarządzaj dostępem", loadingFeedback: "Ładowanie feedbacku…", feedbackLoadFailed: "Nie udało się załadować feedbacku. Spróbuj ponownie.", retry: "Spróbuj ponownie", current: "Aktualny", deleteFeedback: "Usuń feedback", confirmDeleteFeedback: "Kliknij ponownie, aby usunąć feedback", clickAgainToConfirm: "Kliknij ponownie, aby potwierdzić", commentFrom: "Komentarz od: {author}", unknownAuthor: "autor nieznany", showCvExcerpt: "Pokaż fragment CV", showReportModule: "Pokaż sekcję raportu", errorDetails: "Szczegóły błędu", teamNote: "Notatka zespołu", teamNotePlaceholder: "Dodaj kontekst, decyzję albo kolejny krok…", saveNote: "Zapisz notatkę", noFeedbackForFilter: "Brak feedbacku pasującego do filtra.", noFeedbackYet: "Brak feedbacku.", noFeedbackYetDescription: "Oceny i komentarze wysłane z analiz CV pojawią się tutaj.", unsavedFeedbackNote: "Masz niezapisaną notatkę do feedbacku. Czy na pewno chcesz opuścić stronę?", feedbackUpdateFailed: "Nie udało się zapisać zmian.", feedbackDeleteFailed: "Nie udało się usunąć feedbacku.", feedbackAccess: "Dostęp do feedbacku", feedbackAccessDescription: "Zarządzaj osobami, które mogą przeglądać i obsługiwać feedback.", feedbackDomainNotAllowed: "Użyj adresu e-mail z dozwolonej domeny firmowej.", lastOwnerProtected: "Musi pozostać co najmniej jeden właściciel feedbacku.", feedbackAccessForbidden: "Nie masz uprawnień do zarządzania dostępem do feedbacku.", feedbackAccessUpdateFailed: "Nie udało się zaktualizować dostępu do feedbacku.", feedbackAccessLoadFailed: "Nie udało się załadować dostępu do feedbacku. Odśwież stronę, aby spróbować ponownie.", loadingFeedbackAccess: "Ładowanie dostępu do feedbacku…", feedbackCollection: "Zbieranie feedbacku", feedbackCollectionDescription: "Pozwól użytkownikom oceniać wyniki analiz i dodawać komentarze.", enabled: "Włączone", disabled: "Wyłączone", companyEmail: "Firmowy adres e-mail", reviewer: "Recenzent", owner: "Właściciel", grantAccess: "Nadaj dostęp", revokeAccess: "Cofnij",
    uiLanguage: "Język interfejsu", reportLanguage: "Język analizy", reportLanguageDescription: "Używany w nowo generowanych treściach analizy i researchu.",
    analysisSettings: "Publiczny research", analysisSettingsDescription: "Steruj opcjonalnym sprawdzaniem publicznych źródeł dla firm, edukacji i profili LinkedIn.",
    useAiFeatures: "Używaj publicznego researchu WWW", useAiFeaturesDescription: "Sprawdzaj publiczne źródła dla firm, edukacji i profili LinkedIn po analizie CV.", aiUnavailable: "Publiczny research jest niedostępny w tym środowisku.",
    previewFindingsOnHover: "Podglądaj szczegóły po najechaniu", expandSectionsByDefault: "Rozwijaj sekcje domyślnie",
    runResearchAutomatically: "Uruchamiaj wyszukiwania automatycznie", companyResearch: "Sprawdzanie firm", educationResearch: "Sprawdzanie edukacji",
    linkedinDiscovery: "Wyszukiwanie profilu LinkedIn", linkedinDiscoveryDescription: "Wyszukiwanie LinkedIn tylko sugeruje możliwe profile publiczne; nie potwierdza tożsamości.",
    openFeatureListBoard: "Otwórz tablicę listy funkcji", signOut: "Wyloguj się", toggleTheme: "Przełącz motyw",
    toggleSidebar: "Przełącz pasek boczny", resizeSidebar: "Zmień szerokość paska bocznego", dragToResizeSidebar: "Przeciągnij, aby zmienić szerokość paska bocznego.",
    mobileSidebar: "Pasek boczny", mobileSidebarDescription: "Wyświetla mobilny pasek boczny.", close: "Zamknij", allRightsReserved: "Wszelkie prawa zastrzeżone.",
    resizeCvPreview: "Zmień szerokość podglądu CV", fitCvPreview: "Dopasuj dokument do podglądu", loadingCvPreview: "Ładowanie podglądu CV…", openOriginalFile: "Otwórz oryginalny plik", hideCvPreview: "Ukryj podgląd CV",
    viewSources: "Pokaż źródła ({count})", searchDetails: "Szczegóły wyszukiwania", searchesAndLimitations: "Szczegóły wyszukiwania", search: "Wyszukiwanie", limit: "Ograniczenie", searchWithGoogle: "Wyszukaj w Google", searchSubjectWithGoogle: "Wyszukaj {subject} w Google", searchLinkedIn: "Wyszukaj na LinkedIn", searchLinkedInFor: "Wyszukaj {subject} na LinkedIn", postalConsistency: "Zgodność kodu pocztowego", postalConsistent: "Zgodny z deklarowaną miejscowością i krajem", postalMismatch: "Niezgodny z deklarowaną miejscowością i krajem",
    start: "Uruchom research", researching: "Wyszukiwanie…", discovering: "Wyszukiwanie…", companyResearchInProgress: "Trwa sprawdzanie firm", educationResearchInProgress: "Trwa sprawdzanie edukacji", linkedinDiscoveryInProgress: "Trwa wyszukiwanie profilu LinkedIn", researchTimedOut: "Wyszukiwanie trwało zbyt długo. Możesz bezpiecznie spróbować ponownie.", researchFailed: "Wyszukiwanie nie powiodło się. Spróbuj ponownie lub sprawdź stan systemu.", automaticResearchFailed: "Automatyczne wyszukiwanie nie powiodło się. Możesz spróbować ponownie ręcznie.", automaticResearchAlreadyAttempted: "Automatyczne wyszukiwanie zostało już wykonane. Użyj działania ręcznego, aby spróbować ponownie.",
    noCompaniesAvailable: "Brak firm do sprawdzenia.", noEducationEntries: "Brak wpisów edukacyjnych do sprawdzenia.", noCandidateDetails: "Brak danych kandydata do wyszukania na LinkedIn.",
    companyFound: "Znaleziono publiczne informacje o firmie", conflictingCompanyInformation: "Publiczne źródła są sprzeczne", companyNotConfirmed: "Nie potwierdzono w publicznych źródłach", reportedOfficeOrLocation: "Zgłoszone biura", officialWebsite: "Oficjalna strona", found: "Znaleziono", notConfirmed: "Nie potwierdzono", activity: "Działalność", operatingDates: "Okres działalności", present: "obecnie", until: "Do", confidenceWithValue: "Pewność: {value}", confidenceHigh: "wysoka", confidenceMedium: "średnia", confidenceLow: "niska",
    notEnoughPublicInformation: "Za mało informacji publicznych.", forReview: "Do sprawdzenia:", doesNotVerifyCandidateLocation: "To nie potwierdza lokalizacji kandydata.",
    linkedinProfiles: "Wyszukiwanie profilu LinkedIn", startDiscovery: "Wyszukaj", noProfileFound: "Nie znaleziono możliwego profilu", openProfile: "Otwórz profil", profile: "Możliwy profil {index}", photoVisible: "Widoczne zdjęcie", noPublicPhoto: "Brak publicznego zdjęcia", photoUnknown: "Nie wiadomo, czy zdjęcie jest widoczne", lowConnectionCount: "Mała liczba kontaktów", connections: "Kontakty: {count}", connectionsUnknown: "Liczba kontaktów nieznana",
    autoResearch: "Automatyczne wyszukiwania: {kinds}.", analyzing: "Analizowanie {current} z {total}", analyzingStatus: "Analizowanie", analysisComplete: "Analiza zakończona", reportReady: "Raport jest gotowy.", elapsed: "Czas: {time}", estimatedRemaining: "Szacowany pozostały czas: około {time}", takingLonger: "To trwa dłużej niż zwykle", completed: "Ukończono", failed: "Niepowodzenie", waiting: "Oczekiwanie", batchResultsInHistory: "Gotowe raporty znajdziesz w Ostatnich analizach.", newAnalysis: "Nowa", addFile: "Dodaj co najmniej jeden plik PDF lub DOCX.", unexpectedAnalysisError: "Wystąpił nieoczekiwany błąd analizy.", noResult: "Nie zwrócono wyniku", analysisFailed: "Analiza nie powiodła się. Spróbuj ponownie lub sprawdź stan systemu.", analysisFailedWithStatus: "Analiza nie powiodła się ({status})", cvNeedsTextLayer: "To CV nie ma czytelnej warstwy tekstowej. Dodaj tekstowy plik PDF lub DOCX.", cvCouldNotRead: "Nie udało się odczytać pliku. Wyeksportuj go ponownie jako PDF lub DOCX.", cvTooLarge: "Ten plik jest za duży do analizy.", cvEmptyFile: "Ten plik jest pusty.", cvUnsupportedType: "Użyj pliku PDF lub DOCX.", analysisTemporarilyUnavailable: "Analiza CV jest chwilowo niedostępna. Sprawdź stan systemu i spróbuj ponownie.", uploadCouldNotRead: "Nie udało się odczytać przesłanego pliku. Wybierz go ponownie.", docxPreviewFailed: "Nie udało się wyświetlić tego pliku DOCX. Możesz nadal otworzyć oryginalny plik.",
    historyUnavailable: "Historia analiz jest niedostępna.", analysisUnavailable: "Ta analiza nie jest już dostępna.", analysisCouldNotDelete: "Nie udało się usunąć analizy.",
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
