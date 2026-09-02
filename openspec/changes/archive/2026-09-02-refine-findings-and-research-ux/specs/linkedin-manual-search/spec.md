## ADDED Requirements

### Requirement: Single LinkedIn people-search action
The analyze UI SHALL render at most one manual LinkedIn people-search action, located in the LinkedIn Profiles section header beside the title. It MUST NOT render LinkedIn search actions on individual profile cards or in the CV overview.

#### Scenario: LinkedIn section has an eligible keyword
- **WHEN** the report supplies a supported candidate name and optional accepted search hints
- **THEN** the LinkedIn Profiles header shows one accessible search action

#### Scenario: Possible profiles are displayed
- **WHEN** one or more possible profile cards are shown
- **THEN** no profile card contains an additional LinkedIn search action

### Requirement: Deterministic LinkedIn search URL
The action SHALL use the fixed HTTPS LinkedIn people-search origin and encode the admitted discovery keyword as the `keywords` query parameter. It SHALL open in a new tab with a referrer-protecting relationship and MUST NOT mutate analysis or research state.

#### Scenario: Keyword contains spaces or URL-sensitive characters
- **WHEN** the admitted keyword contains whitespace, diacritics, or URL-sensitive characters
- **THEN** the generated URL decodes to the complete intended `keywords` value

#### Scenario: No supported candidate name exists
- **WHEN** LinkedIn discovery is ineligible because the candidate name is missing or unsupported
- **THEN** the header omits the manual search action
