export const RESEARCH_ERROR_REASONS = new Set([
  "invalid_response", "schema", "subject_mismatch", "search_count", "invalid_json", "json_parse",
  "unsupported_high_confidence", "insufficient_evidence_confidence", "claims_without_findings",
  "empty_operating_period", "contradictory_operating_period", "limited_presence_contradiction",
]);
const RESEARCH_ERROR_CODES = new Set([
  "Unauthorized", "Forbidden", "upstream_unavailable", "upstream_invalid_response",
  "analysis_not_found", "research_persistence_conflict", "network_error", "research_failed",
  ...["company", "education", "linkedin"].flatMap((kind) => [
    `${kind}_research_timeout`, `${kind}_research_invalid_response`, `${kind}_research_client_error`,
    `${kind}_research_disabled`, `no_${kind}_research_candidates`,
  ]),
]);

/**
 * @typedef {object} ResearchErrorDetails
 * @property {string} operation
 * @property {string} analysisId
 * @property {string} occurredAt
 * @property {string} code
 * @property {number} [httpStatus]
 * @property {string} [reason]
 */

/** Copy only known machine codes; an upstream response may contain private text.
 * @param {Record<string, unknown>} payload
 */
export function researchErrorFields(payload) {
  const candidate = payload.detail ?? payload.error;
  return {
    code: typeof candidate === "string" && RESEARCH_ERROR_CODES.has(candidate) ? candidate : "research_failed",
    reason: typeof payload.error_reason === "string" && RESEARCH_ERROR_REASONS.has(payload.error_reason) ? payload.error_reason : undefined,
  };
}

/** @param {ResearchErrorDetails} details @param {"en" | "pl"} language */
export function researchErrorDescription(details, language) {
  const pl = language === "pl";
  if (details.httpStatus === 401) return pl ? "Sesja wygasła. Zaloguj się ponownie." : "Your session expired. Sign in again.";
  if (details.httpStatus === 403) return pl ? "Nie masz dostępu do tego researchu." : "You do not have access to this research.";
  if (details.httpStatus === 404) return pl ? "Analiza nie jest już dostępna. Sprawdź historię analiz." : "This analysis is no longer available. Check your analysis history.";
  if (details.httpStatus === 504 || details.code.endsWith("_timeout")) return pl ? "Research przekroczył limit czasu. Spróbuj ponownie." : "Research exceeded the time limit. Try again.";
  if (details.reason === "subject_mismatch") return pl ? "Wynik dotyczył innej firmy lub uczelni i został odrzucony. Spróbuj ponownie." : "The result did not match the requested company or institution and was rejected. Try again.";
  if (details.code.endsWith("_invalid_response")) return pl ? "Odpowiedź researchu nie przeszła walidacji. Spróbuj ponownie; jeśli błąd wróci, prześlij jego szczegóły." : "The research response did not pass validation. Try again; if it fails again, send the error details.";
  if (details.httpStatus === 409) return pl ? "Nie udało się zapisać wyniku researchu. Odśwież raport i spróbuj ponownie." : "The research result could not be saved. Reload the report and try again.";
  if (details.httpStatus === 429) return pl ? "Osiągnięto limit żądań. Spróbuj ponownie za chwilę." : "The request limit was reached. Try again shortly.";
  if (details.httpStatus === 503) return pl ? "Research jest obecnie niedostępny. Sprawdź stan systemu w ustawieniach." : "Research is currently unavailable. Check system status in Settings.";
  if (details.code === "network_error" || details.code === "upstream_unavailable" || details.code.endsWith("_client_error")) return pl ? "Nie udało się połączyć z usługą researchu. Spróbuj ponownie za chwilę." : "The research service could not be reached. Try again shortly.";
  return pl ? "Research nie został ukończony. Spróbuj ponownie lub prześlij szczegóły błędu." : "Research could not be completed. Try again or send the error details.";
}

/** @param {ResearchErrorDetails} details */
export function formatResearchError(details) {
  return [
    `Operation: ${details.operation}`,
    `Error: ${details.code}`,
    ...(details.reason ? [`Reason: ${details.reason}`] : []),
    `HTTP: ${details.httpStatus ?? "no response"}`,
    `Time: ${details.occurredAt}`,
    `Analysis: ${details.analysisId}`,
  ].join("\n");
}
