import { isSelfEmploymentLabel } from "./relationship-labels.js";

const GOOGLE_SEARCH_URL = "https://www.google.com/search";

function cleanPart(value: string | null | undefined): string {
  return (value ?? "").trim().replace(/\s+/g, " ");
}

function buildGoogleSearchUrl(parts: Array<string | null | undefined>): string | null {
  const query = parts.map(cleanPart).filter(Boolean).join(" ");
  if (!query) return null;

  const url = new URL(GOOGLE_SEARCH_URL);
  url.searchParams.set("q", query);
  return url.toString();
}

export function companyGoogleSearchUrl({
  organization,
  location,
}: {
  organization: string | null | undefined;
  location?: string | null;
}): string | null {
  const subject = cleanPart(organization);
  if (!subject || isSelfEmploymentLabel(subject)) return null;
  return buildGoogleSearchUrl([subject, location]);
}

export function educationGoogleSearchUrl({
  institution,
  program,
  certificate,
}: {
  institution: string | null | undefined;
  program?: string | null;
  certificate?: string | null;
}): string | null {
  const subject = cleanPart(institution);
  if (!subject) return null;
  return buildGoogleSearchUrl([subject, cleanPart(program) || certificate]);
}
