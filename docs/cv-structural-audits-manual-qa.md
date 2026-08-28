# CV structural audits manual QA

Use synthetic or approved non-private CVs only. Do not automate browser uploads or clicks for this checklist.

- Analyze one text-extractable PDF with AI disabled. Confirm the structural panel appears, timeline entries point to the correct page/line, visibility coverage names PDF text spans, and the base location score/band match the same document without structural observations.
- Analyze one DOCX containing a normal body paragraph, a table entry, a deliberately hidden run, and a non-empty header. Confirm the hidden run is labeled neutrally as “Needs review”, its raw text is absent from the structural payload/UI, and the header is disclosed as omitted with partial coverage.
- Check an invalid month (`13/2024`) and two overlapping employment ranges. Confirm invalid, definite, and year-only possible overlap labels remain distinct; possible overlap has no exact shared-month count.
- Switch English/Polish UI language. Confirm only prose changes; contract, reason/trigger codes, snapshot month, and source locations remain identical.
- Reopen the saved analysis and retry only AI. Confirm the structural object and snapshot month are unchanged byte-for-byte.
- Verify the original PDF/DOCX at every reported source location. Treat findings as review prompts, never as fraud/authenticity proof or an automated hiring decision.
