import type { CopyKey } from "./app-settings.ts";

type FeedbackContextInput = {
  kind?: unknown;
  source_category?: unknown;
  source_key?: unknown;
};

type Translate = (
  key: CopyKey,
  values?: Record<string, string | number>,
) => string;

export function feedbackContext(item: FeedbackContextInput, t: Translate) {
  const category = String(item.source_category ?? "");
  const key = String(item.source_key ?? "");
  const section = ({
    report: t("extracted"),
    attention: t("needsAttention"),
    worth_knowing: t("worthKnowing"),
    company_research: t("companyResearch"),
    education_research: t("educationResearch"),
    linkedin_discovery: t("linkedinProfiles"),
  } as Record<string, string>)[category] ?? category.replaceAll("_", " ");

  let subject = key;
  if (category === "report") subject = t("extracted");
  else if (key.startsWith("location-resolved")) subject = t("feedbackLocationResolved");
  else if (key.startsWith("location-ambiguous")) subject = t("feedbackLocationAmbiguous");
  else if (key.startsWith("location-unresolved")) subject = t("feedbackLocationUnresolved");
  else if (key.startsWith("location-mismatch")) subject = t("feedbackLocationMismatch");
  else if (key.startsWith("comparison-different")) subject = t("feedbackPhoneCountryMismatch");
  else if (key.startsWith("email-")) subject = t("feedbackEmailTypo");
  else if (key.startsWith("gap-")) subject = t("feedbackMissingCvInformation");
  else if (key === "linkedin-not-found") subject = t("feedbackLinkedinNotFound");
  else if (category.endsWith("_research")) subject = t("feedbackResultNumber", { index: Number(key) + 1 });
  else if (category === "linkedin_discovery" && /^\d+$/.test(key)) subject = t("feedbackProfileNumber", { index: Number(key) + 1 });

  return { section, subject };
}
