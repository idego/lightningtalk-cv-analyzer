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
