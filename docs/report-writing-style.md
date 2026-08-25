# Recruiter report writing style

This project writes reviewer text for an English B2 audience. The style is
informed by Google's global-audience and accessibility guidance and by
ASD-STE100 principles. The project does not claim formal ASD-STE100 compliance.
That would require an approved dictionary and a dedicated conformance check.

For code-owned reviewer notes:

- put the result first;
- use one idea per sentence and aim for no more than 20 words;
- use active voice, common words, and one term for one concept;
- use `What we found`, `Why it matters`, and `What to check`;
- explain uncertainty and state what the evidence cannot prove;
- never show rule IDs, extractor names, reference-data versions, authority, or
  internal category names as the main explanation;
- keep names neutral and never infer origin, nationality, residence, or work
  permission from a name.

Known deterministic categories use templates in
`apps/web/src/lib/review-findings.ts`. The template function accepts the report
language so another code-owned language map can be added without changing the
API facts or evidence. AI text stays in the selected AI report language.

References:

- Google developer documentation, Write for a global audience:
  <https://developers.google.com/style/translation>
- Google developer documentation, Write accessible documentation:
  <https://developers.google.com/style/accessibility>
- ASD-STE100 FAQ: <https://www.asd-ste100.org/STE_faq.html>
