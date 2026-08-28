## ADDED Requirements

### Requirement: Structured profile extraction
The system SHALL accept a text-extractable PDF or DOCX and produce a versioned `CandidateProfile` containing available personal/contact data, headline/summary, skills, technologies, experience, education, languages, certifications, and additional sections. Unknown facts SHALL remain null or empty and extraction MUST NOT anonymize the canonical profile.

#### Scenario: CV contains ordinary candidate data
- **WHEN** HR uploads a supported CV to Profile Builder
- **THEN** the system returns a `candidate-profile-v1` profile and stable IDs for repeated editor sections

#### Scenario: CV contains a national identifier
- **WHEN** ingestion detects a supported national ID
- **THEN** the identifier is redacted before the Profile Builder AI request and is not returned in the profile

#### Scenario: Recruiter disables AI features
- **WHEN** the existing per-user AI setting is disabled for a Profile Builder extraction request
- **THEN** the system does not call the extraction model and tells the recruiter to enable AI before extraction

### Requirement: One canonical editor state
The Profile Builder UI SHALL keep one canonical current profile. Editor controls, local preview, and export SHALL derive from that current state rather than independently authoritative copies.

#### Scenario: Recruiter changes an employer
- **WHEN** the employer changes from `Acme` to `Example Corp`
- **THEN** the preview shows `Example Corp` and a subsequent DOCX export contains `Example Corp` instead of the stale value

### Requirement: Reversible anonymization
Anonymization SHALL be a deterministic output policy and SHALL NOT destructively mutate the canonical profile.

#### Scenario: Recruiter hides email and employer names
- **WHEN** those anonymization controls are enabled
- **THEN** preview and DOCX omit those values while the editor still retains them

### Requirement: Editable DOCX export
The system SHALL generate an IDEGO-style DOCX from the explicit current profile snapshot and anonymization policy. The file SHALL contain normal editable paragraphs/lists rather than a screenshot-only representation.

#### Scenario: Profile is exported
- **WHEN** HR downloads the DOCX
- **THEN** Word/LibreOffice can edit its text and the exported values match the submitted current snapshot

### Requirement: Additive authenticated web workflow
Profile Builder SHALL be available as `/profile-builder` inside the existing authenticated application shell and SHALL NOT change Analyze behavior.

#### Scenario: Authenticated recruiter opens the app
- **WHEN** navigation is rendered
- **THEN** Analyze, Profile Builder, and Settings are available as separate destinations


### Requirement: Recent candidate profiles
The system SHALL persist authenticated owner-scoped Profile Builder snapshots containing the current canonical profile, anonymization policy, selected template snapshot, source filename, and timestamps. It MUST NOT persist the original uploaded CV bytes for this workflow.

#### Scenario: Profile extraction succeeds
- **WHEN** an authenticated recruiter extracts a supported CV
- **THEN** the web workflow creates a saved Profile Builder record and shows it in Recent profiles

#### Scenario: Recruiter edits a saved profile
- **WHEN** canonical profile data, anonymization, or the selected template changes
- **THEN** the browser updates immediately and persists the exact current snapshot after a debounce without blocking editing

#### Scenario: Recruiter opens a recent profile
- **WHEN** a saved Profile Builder record is opened
- **THEN** the editor restores its canonical profile, anonymization, selected template snapshot, and filename

### Requirement: Template management
The upload workflow SHALL expose the current template and a template manager that can select an existing template, create a new template, or navigate to editing one. Templates SHALL be owner-scoped except for the built-in IDEGO Default fallback.

#### Scenario: Recruiter changes the current template
- **WHEN** another template is selected in the manager
- **THEN** the next profile uses that template and an open profile immediately derives preview/export from the new template snapshot

#### Scenario: Recruiter creates or edits a template
- **WHEN** Create template or Edit is activated
- **THEN** the app opens the Template Creator screen for a new or existing normalized template

### Requirement: Constrained visual Template Creator
The Template Creator SHALL let HR visually assemble a template from supported domain blocks, reorder/remove/add blocks, rename section headings, and edit supported brand, typography, header, and simple list-layout settings. It MUST NOT require JSON/Jinja knowledge.

#### Scenario: Template structure changes
- **WHEN** a recruiter reorders or hides a domain block
- **THEN** the sample preview updates immediately and a saved template preserves that order/visibility

#### Scenario: Custom template is exported
- **WHEN** a profile using a custom template is exported
- **THEN** DOCX section order, visible sections, headings, branding, and supported typography derive from the exact submitted template snapshot
