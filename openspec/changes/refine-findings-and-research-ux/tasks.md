## 1. Prompt and confidence contracts

- [ ] 1.1 Audit and revise every Docling/Luna base-analysis prompt for evidence discipline, concise reviewer output, and explicit uncertainty.
- [ ] 1.2 Revise company, education, and LinkedIn research prompts with conservative confidence definitions and concrete positive/negative examples; increment prompt/research versions.
- [ ] 1.3 Add deterministic confidence normalization for unsupported high-confidence LinkedIn and research outcomes, with backend tests.

## 2. Recruiter-facing findings and overview

- [ ] 2.1 Remove implementation provenance, unknown, institution-status, and accreditation badges from recruiter-facing report/research UI.
- [ ] 2.2 Remove outside-EU classification from findings and present it as a separate neutral CV-overview row with cautious copy.
- [ ] 2.3 Present supported offline postal-code consistency against locality and country in the CV overview and cover it with adapter tests.

## 3. Search and evidence UX

- [ ] 3.1 Add a tested deterministic LinkedIn people-search URL builder using the admitted discovery keyword.
- [ ] 3.2 Render exactly one accessible LinkedIn search action in the LinkedIn Profiles header and none on individual profiles or overview rows.
- [ ] 3.3 Replace numbered source labels with readable safe titles/hostnames and add rendering/unit coverage.

## 4. Visual consistency and verification

- [ ] 4.1 Normalize typography and compact icon actions in the touched report/research components without expanding the design-system scope.
- [ ] 4.2 Update user-facing documentation and validate the OpenSpec change.
- [ ] 4.3 Run focused backend tests, frontend tests, typecheck, lint, and build; document any unrelated pre-existing failures.

## 5. Delivery

- [ ] 5.1 Split the completed work into logical Conventional Commits with informative bodies.
- [ ] 5.2 Push branch `develop` to `origin` and verify the remote branch tip.
