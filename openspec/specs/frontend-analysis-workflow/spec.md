# frontend-analysis-workflow Specification

## Purpose
Defines privacy-safe manual search actions available while reviewing structured
CV facts and completed public-research results.

## Requirements

### Requirement: Contextual manual Google Search actions
The analyze UI SHALL provide manual Google Search actions for each visible company and education entry in the structured CV overview and for each completed Company Research organization and Education Research credential. These actions SHALL remain independent of automatic and user-started research state and SHALL NOT change analysis or research output.

#### Scenario: Search before optional research
- **WHEN** the structured CV overview shows a company or education entry before optional research has completed
- **THEN** that entry provides a compact icon-only Google Search action

#### Scenario: Search a completed research subject
- **WHEN** Company Research shows an organization or Education Research shows a credential
- **THEN** that result provides a labeled Google Search action in its header area

#### Scenario: Repeated subject entries
- **WHEN** the overview shows the same company or institution in more than one entry
- **THEN** each visible entry retains its own contextual Google Search action

### Requirement: Deterministic public-subject search queries
Google Search actions SHALL construct their query only from the visible public subject and the allowed disambiguating fields for that entry. A company query SHALL contain its organization name and SHALL append its available company location. An education query SHALL contain its institution and SHALL append its program when present, otherwise its certificate when present. The query MUST NOT include candidate name, contact details, dates, raw CV evidence, or hidden report context.

#### Scenario: Company has location context
- **WHEN** a company entry contains organization `Edclub` and location `USA`
- **THEN** its action searches Google for `Edclub USA`

#### Scenario: Company has no location context
- **WHEN** a company entry contains an organization name and no usable company location
- **THEN** its action searches Google for the organization name alone

#### Scenario: Education has a program
- **WHEN** an education entry contains an institution and a program
- **THEN** its action searches Google for the institution followed by the program

#### Scenario: Education has no program but has a certificate
- **WHEN** an education entry contains an institution, no program, and a certificate
- **THEN** its action searches Google for the institution followed by the certificate

#### Scenario: Education has only an institution
- **WHEN** an education entry contains an institution without a program or certificate
- **THEN** its action searches Google for the institution alone

### Requirement: Safe and accessible external search navigation
Each Google Search action SHALL use the fixed HTTPS Google Search origin, encode the complete query as the `q` search parameter, and open in a new browser tab with a referrer-protecting relationship. The compact action SHALL use a search icon with a localized accessible name and tooltip. The labeled action SHALL reuse the existing monochrome Google SVG and show `Search with Google` in English or `Wyszukaj w Google` in Polish. Every action MUST remain keyboard accessible and visibly focusable.

#### Scenario: Query contains URL-sensitive characters
- **WHEN** the visible subject contains whitespace, diacritics, an ampersand, or another URL-sensitive character
- **THEN** the action opens a valid Google Search URL whose `q` parameter decodes to the complete intended query

#### Scenario: User activates a search action
- **WHEN** the recruiter activates either search-action variant
- **THEN** Google Search opens in a new tab and the current analysis remains available

#### Scenario: Compact action is used without visible text
- **WHEN** the overview renders an icon-only action for a subject
- **THEN** assistive technology and the tooltip identify that the action searches that subject in Google

#### Scenario: Interface language changes
- **WHEN** the UI language is Polish or English
- **THEN** the search action uses the corresponding localized visible and accessible copy

### Requirement: Search action eligibility
The analyze UI SHALL omit a Google Search action when its required public subject is empty or when a company entry represents a non-organization work mode such as self-employment or freelance work.

#### Scenario: Subject is missing
- **WHEN** a company or education entry has no non-empty organization or institution name
- **THEN** no Google Search action is rendered for that entry

#### Scenario: Work entry is not an organization
- **WHEN** a company value is recognized as self-employment or freelance work
- **THEN** no Google Search action is rendered for that value
