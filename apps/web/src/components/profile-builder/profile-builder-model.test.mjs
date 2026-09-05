import assert from "node:assert/strict";
import test from "node:test";
import { DEFAULT_ANONYMIZATION, REVEALED_ANONYMIZATION, PROFILE_TEMPLATE_SAMPLE_PROFILE, derivedPresentation, formatProfessionalSection } from "./profile-builder-model.ts";

test("blind defaults hide all links without altering the saved candidate", () => {
  const profile = structuredClone(PROFILE_TEMPLATE_SAMPLE_PROFILE);
  profile.personal.links.other = [{label: "Personal site", url: "https://example.test/private-name"}];
  const output = derivedPresentation(profile, DEFAULT_ANONYMIZATION);
  assert.equal(output.personal.first_name, null);
  assert.deepEqual(output.personal.links.other, []);
  assert.equal(profile.personal.links.other.length, 1);
  assert.deepEqual(derivedPresentation(profile, REVEALED_ANONYMIZATION).personal.links.other, profile.personal.links.other);
});
test("AI review shows readable employment details rather than record JSON", () => {
  const entry = PROFILE_TEMPLATE_SAMPLE_PROFILE.experience[0];
  const output = formatProfessionalSection("experience", [entry]);
  assert.ok(output.includes(entry.role));
  assert.ok(output.includes(entry.company));
  assert.ok(output.includes(entry.responsibilities[0]));
  assert.ok(output.includes("Technologies:"));
  assert.ok(!output.includes(entry.id));
  assert.ok(!output.includes('"responsibilities"'));
});
test("AI review handles empty and unchanged professional sections", () => {
  assert.equal(formatProfessionalSection("summary", null), "Not provided");
  assert.equal(formatProfessionalSection("skills", ["Python", "SQL"]), "• Python\n• SQL");
  assert.equal(formatProfessionalSection("education", []), "Not provided");
  assert.equal(formatProfessionalSection("headline", "Backend Engineer"), "Backend Engineer");
});
