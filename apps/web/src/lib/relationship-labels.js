const SELF_EMPLOYMENT = new Set([
  "freelance", "freelancer", "self employed", "self employment",
  "self-employed", "self-employment", "samozatrudnienie",
  "samozatrudniony", "wolny strzelec",
]);

/** @param {string | null | undefined} value */
export function isSelfEmploymentLabel(value) {
  return typeof value === "string" && SELF_EMPLOYMENT.has(
    value.normalize("NFKD").replace(/\p{M}/gu, "").toLocaleLowerCase().trim().replace(/\s+/g, " "),
  );
}
