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
The upload workflow SHALL expose the current template and a template manager that can select an existing template, create a new template, or navigate to editing one. Custom templates SHALL support explicit Private or Shared visibility; new custom templates default to Private and the built-in IDEGO Default is Shared.

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


### Requirement: Promptable AI Summary
The Profile Builder SHALL allow HR to generate or regenerate the one canonical profile Summary using the current professional profile plus an optional recruiter instruction or pasted job description. Generation SHALL use the pinned GPT-5.6 Luna model with no reasoning and a small output limit, and SHALL NOT send personal/contact fields or the existing Summary as generation input.

#### Scenario: Recruiter generates a role-focused summary
- **WHEN** HR enters an optional instruction or job description and chooses Generate or Regenerate
- **THEN** the generated source-faithful summary replaces `profile.summary` and the same value is immediately used by preview, autosave, and export

### Requirement: Direct-manipulation Template Creator
The Template Creator SHALL fit inside one application viewport without vertical scrolling. HR SHALL reorder blocks by drag-and-drop from either the Blocks list or directly on the A4 canvas, SHALL place body blocks into editable-document `left/full/right` lanes by horizontal drop position, and SHALL toggle block visibility directly from the block eye icon rather than a separate visibility switch.

#### Scenario: Recruiter rearranges profile sections
- **WHEN** a block is dragged directly on the A4 canvas to another vertical position and horizontal lane
- **THEN** the normalized template section order/placement changes and browser preview plus DOCX/PDF export use that same editable-document layout

#### Scenario: Recruiter hides a section
- **WHEN** the eye icon on a block is activated
- **THEN** the block visibility changes immediately and the preview reflects it

### Requirement: Freely positioned template logo
A template MAY contain one uploaded company logo. HR SHALL be able to upload PNG, JPG, WebP, or SVG, resize it, and drag it anywhere within the A4 page bounds. Preview, saved template snapshots, reopened templates, and DOCX export SHALL use the same normalized logo asset and position.

#### Scenario: Recruiter uploads and positions a transparent logo
- **WHEN** HR uploads a supported logo and drags it to a new page position
- **THEN** its normalized PNG data, size, and page-relative coordinates are persisted and the exported DOCX contains a floating image at the corresponding position

### Requirement: Protect unsaved template work
The Template Creator SHALL warn before its explicit Back action or browser unload discards dirty template changes.

#### Scenario: Recruiter presses Back after editing a new template
- **WHEN** unsaved template changes exist
- **THEN** the recruiter must confirm discarding them before leaving the creator


### Requirement: PDF parity export
The system SHALL export PDF from the exact same profile/anonymization/template snapshot as DOCX, using DOCX-to-PDF conversion rather than an independent renderer.

### Requirement: Organization custom fields
The system SHALL let internal users manage an organization-level custom-field schema. New extracted profiles SHALL materialize current definitions and defaults into their canonical profile snapshot; existing snapshots retain their values even if the organization schema later changes.

### Requirement: Reviewable AI profile actions
The system SHALL let HR run a prompt against selected professional profile sections, preview original versus proposed section values, and selectively accept proposed sections. AI actions MUST NOT modify contact/personal data or silently mutate canonical state before acceptance.

### Requirement: Conversion preferences
Each authenticated user SHALL have persisted Profile Builder conversion preferences covering default anonymization, optional automatic Summary generation and prompt, safe technology aggregation, date-format normalization, default template, and output filename convention.

### Requirement: Controlled template sharing
Custom templates SHALL be explicitly Private or Shared. Private templates are owner-scoped. Shared templates are visible and editable inside the internal organization. Saving a new template MUST NOT share it by default.

### Requirement: Batch conversion flow
Profile Builder SHALL accept up to 10 PDF/DOCX files in one batch and expose queued, processing, completed, and failed state per file. Each successful file SHALL create its own saved canonical profile snapshot.

### Requirement: Reviewable AI translation
The system SHALL translate selected professional profile sections to a supported target language with GPT-5.6 Luna, preserve names/URLs/technology identifiers, and require preview plus selective acceptance before changing canonical state.

### Requirement: Profiles catalog
The application SHALL expose a searchable Profiles destination for authenticated users to reopen saved profiles; Recent profiles on the upload page remain a compact shortcut rather than the only profile repository.
