import { isSelfEmploymentLabel } from "./relationship-labels.js";

const GOOGLE_SEARCH_URL = "https://www.google.com/search";
const LINKEDIN_PEOPLE_SEARCH_URL = "https://www.linkedin.com/search/results/people/";

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
  const cleanInstitution = cleanPart(institution);
  const cleanCertificate = cleanPart(certificate);
  const subject = cleanInstitution || cleanCertificate;
  if (!subject) return null;
  const context = cleanPart(program) || (cleanInstitution ? cleanCertificate : null);
  return buildGoogleSearchUrl([subject, context]);
}

export function linkedinPeopleSearchUrl(query: string | null | undefined): string | null {
  const keywords = cleanPart(query);
  if (!keywords) return null;
  const url = new URL(LINKEDIN_PEOPLE_SEARCH_URL);
  url.searchParams.set("keywords", keywords);
  return url.toString();
}

export function linkedinPeopleKeyword({
  candidateName,
  organization,
}: {
  candidateName: string | null | undefined;
  organization?: string | null;
}): string | null {
  const name = cleanPart(candidateName);
  if (!name) return null;
  const company = cleanPart(organization).split(",", 1)[0]?.trim();
  return [name, company].filter(Boolean).join(" ");
}
