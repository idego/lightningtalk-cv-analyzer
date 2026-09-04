type FeedbackContextInput = {
  kind?: unknown;
  source_category?: unknown;
  source_key?: unknown;
};

export function feedbackContext(item: FeedbackContextInput) {
  const category = String(item.source_category ?? "");
  const key = String(item.source_key ?? "");
  const section = {
    report: "CV overview",
    attention: "Needs attention",
    worth_knowing: "Worth knowing",
    company_research: "Company research",
    education_research: "Education research",
    linkedin_discovery: "LinkedIn Profile Research",
  }[category] ?? category.replaceAll("_", " ");

  let subject = key;
  if (category === "report") subject = "CV overview";
  else if (key.startsWith("location-resolved")) subject = "GeoNames resolved the declared city and country";
  else if (key.startsWith("location-ambiguous")) subject = "GeoNames location is ambiguous";
  else if (key.startsWith("location-unresolved")) subject = "GeoNames did not resolve the declared location";
  else if (key.startsWith("location-mismatch")) subject = "Declared city and country mismatch";
  else if (key.startsWith("comparison-different")) subject = "Declared country and phone country differ";
  else if (key.startsWith("email-")) subject = "Possible email-domain typo";
  else if (key.startsWith("gap-")) subject = "Missing CV information";
  else if (key === "linkedin-not-found") subject = "No matching LinkedIn profile found";
  else if (category.endsWith("_research")) subject = `Result ${Number(key) + 1}`;
  else if (category === "linkedin_discovery" && /^\d+$/.test(key)) subject = `Profile ${Number(key) + 1}`;

  return { section, subject };
}
