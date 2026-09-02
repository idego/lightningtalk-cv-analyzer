import assert from "node:assert/strict";
import test from "node:test";

import {
  companyGoogleSearchUrl,
  educationGoogleSearchUrl,
  linkedinPeopleKeyword,
  linkedinPeopleSearchUrl,
} from "./google-search.ts";

function parsed(value) {
  assert.ok(value);
  return new URL(value);
}

test("builds a company query on the fixed Google Search origin", () => {
  const url = parsed(companyGoogleSearchUrl({ organization: "Edclub", location: "USA" }));
  assert.equal(url.origin, "https://www.google.com");
  assert.equal(url.pathname, "/search");
  assert.equal(url.searchParams.get("q"), "Edclub USA");
});

test("builds short LinkedIn keywords from candidate and company", () => {
  assert.equal(
    linkedinPeopleKeyword({ candidateName: "Ahmad Hassan", organization: "Edclub, USA" }),
    "Ahmad Hassan Edclub",
  );
  assert.equal(linkedinPeopleKeyword({ candidateName: "Ahmad Hassan", organization: null }), "Ahmad Hassan");
});

test("builds an encoded LinkedIn people search URL", () => {
  const url = parsed(linkedinPeopleSearchUrl("  Łukasz   Kowalski R&D  "));
  assert.equal(url.origin, "https://www.linkedin.com");
  assert.equal(url.pathname, "/search/results/people/");
  assert.equal(url.searchParams.get("keywords"), "Łukasz Kowalski R&D");
  assert.equal(linkedinPeopleSearchUrl("  "), null);
});

test("normalizes whitespace and preserves diacritics and URL-sensitive characters", () => {
  const url = parsed(companyGoogleSearchUrl({
    organization: "  Żółć   & Synowie  ",
    location: "  Łódź  ",
  }));
  assert.equal(url.searchParams.get("q"), "Żółć & Synowie Łódź");
});

test("omits missing company context and rejects ineligible company values", () => {
  assert.equal(
    parsed(companyGoogleSearchUrl({ organization: "Idego", location: "  " })).searchParams.get("q"),
    "Idego",
  );
  assert.equal(companyGoogleSearchUrl({ organization: "" }), null);
  assert.equal(companyGoogleSearchUrl({ organization: "Freelance" }), null);
  assert.equal(companyGoogleSearchUrl({ organization: "samozatrudnienie" }), null);
});

test("uses education program before certificate", () => {
  assert.equal(
    parsed(educationGoogleSearchUrl({
      institution: "Politechnika Gdańska",
      program: "Informatyka",
      certificate: "AWS Cloud Practitioner",
    })).searchParams.get("q"),
    "Politechnika Gdańska Informatyka",
  );
});

test("falls back from program to certificate and then institution only", () => {
  assert.equal(
    parsed(educationGoogleSearchUrl({
      institution: "Coursera",
      program: " ",
      certificate: "Google Data Analytics & BI",
    })).searchParams.get("q"),
    "Coursera Google Data Analytics & BI",
  );
  assert.equal(
    parsed(educationGoogleSearchUrl({ institution: "MIT" })).searchParams.get("q"),
    "MIT",
  );
  assert.equal(educationGoogleSearchUrl({ institution: null, certificate: "Certificate" }), null);
});
