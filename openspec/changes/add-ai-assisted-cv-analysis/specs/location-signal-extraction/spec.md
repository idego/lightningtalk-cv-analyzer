## MODIFIED Requirements

### Requirement: Identify the claimed location
The system SHALL identify a candidate's claimed location only from an explicit person-location description using versioned code rules. The selected value SHALL keep exact source evidence. An unlabeled place name in the document header SHALL remain an observation and MUST NOT become the claimed-location value used by deterministic scoring. AI MAY provide a separate semantic interpretation for human review but MUST NOT supply or replace the scoring claim. When code cannot identify one explicitly person-owned value without guessing, the scoring claim SHALL be undetermined.

#### Scenario: Explicit person location present
- **WHEN** versioned code rules find one unambiguous location explicitly described as the person's location
- **THEN** the system records it as the code-owned claimed location with its resolution status, authority, evidence, extractor version, and reference-data version

#### Scenario: Claim present in contact block
- **WHEN** the contact or header region contains one resolvable place explicitly described as the person's location
- **THEN** the system records it as the code-owned claimed location with its resolved country or region

#### Scenario: Unlabeled header place present
- **WHEN** an otherwise recognizable place name appears in the document header without an explicit person-location description
- **THEN** the system records a location observation and does not use it as the scoring claim

#### Scenario: Location ownership is unclear
- **WHEN** the document contains plausible person, employer, office, client, project, or education locations and code cannot distinguish one explicitly person-owned location
- **THEN** the system keeps those concepts separate and marks the scoring claim as undetermined

#### Scenario: No identifiable claim
- **WHEN** no location can be mechanically identified as an explicit person-location claim
- **THEN** the system marks the scoring claim as undetermined and preserves any location-shaped candidates as non-scoring observations

#### Scenario: AI interprets an ambiguous location
- **WHEN** AI returns a reviewer-facing interpretation for an otherwise ambiguous location
- **THEN** the report identifies it as AI-derived and excludes it from score and band calculation

### Requirement: Resolve locations via gazetteer
The system SHALL resolve explicit location strings through a `LocationResolver` interface using versioned offline reference data and deterministic normalization. The V1 resolver SHALL use a project-built index from GeoNames `cities500`, `countryInfo`, and only the `alternateNamesV2` records whose GeoNames identifiers occur in that index. It SHALL record unresolved and ambiguous results instead of silently choosing. AI and web research MUST NOT replace the code-owned resolution used by deterministic scoring.

#### Scenario: Unambiguous place
- **WHEN** a location string maps to one locality and country in the configured reference data
- **THEN** the system records the resolved location, code authority, source evidence, extractor version, and reference-data version

#### Scenario: Ambiguous place name
- **WHEN** a location string maps to several plausible country interpretations
- **THEN** the system records an ambiguous observation and does not select a country for scoring

#### Scenario: Place absent from the bounded index
- **WHEN** the V1 GeoNames index does not contain the attempted locality
- **THEN** the system returns an `unresolved` location observation
- **AND** does not describe the locality as nonexistent, invalid, or disproved

#### Scenario: Resolver implementation changes
- **WHEN** a different index or resolver implementation is configured
- **THEN** deterministic extraction continues to depend on the `LocationResolver` contract rather than a dataset-specific API

### Requirement: Extract location-bearing evidence signals
The system SHALL extract versioned deterministic candidates, facts, and observations when source evidence supports them. Every result SHALL record authority, exact evidence, extractor version, and any applicable reference-data version. A `ScoringSignal` MAY be created only from validated code-owned facts. Scored location evidence MAY include an explicitly person-owned claimed-location resolution and one aggregate valid international phone-country result. Postal compatibility SHALL remain an unweighted observation until separate anonymous calibration and project-owner approval authorize a scoring change. The system SHALL keep right-to-work or visa text informational and SHALL NOT use spelling locale, currency, date-format locale, email TLD, employer location, education location, client location, project location, or office location as evidence of the candidate's physical location.

#### Scenario: Possible phone candidate
- **WHEN** libphonenumber considers a detected phone-shaped value possible but not valid
- **THEN** the system records a non-scoring observation and does not create a phone-country fact

#### Scenario: Valid phone country resolved
- **WHEN** a valid international phone number maps to one region without a default-region assumption
- **THEN** the system records its country, code authority, source evidence, extractor version, and reference-data version as a fact

#### Scenario: Phone country code resolved offline
- **WHEN** a valid international phone number maps to one region without a default-region assumption
- **THEN** the system resolves its country offline via libphonenumber and records a code-owned fact rather than directly assigning scoring weight

#### Scenario: Phone lacks an international prefix
- **WHEN** a phone number cannot be assigned a country without a default region or another guessed assumption
- **THEN** its country remains unknown for scoring

#### Scenario: Several phones agree
- **WHEN** all deterministically person-owned, country-resolved phone facts identify the same country
- **THEN** the scoring rules may create one aggregate phone-country `ScoringSignal` using all supporting phone facts

#### Scenario: Several phones conflict
- **WHEN** deterministically person-owned phone facts resolve to different countries
- **THEN** the system retains every phone fact, records an ambiguous aggregate observation, and creates no phone-country scoring signal

#### Scenario: Postal compatibility observed
- **WHEN** a postal value or format is detected, whether unique or shared by several countries
- **THEN** the system may record its literal compatibility as an observation with zero scoring weight
- **AND** does not use it as independent evidence of the candidate's physical location

#### Scenario: Weak locale proxy is present
- **WHEN** the CV contains a currency, spelling variant, date convention, email TLD, or organization location
- **THEN** the system does not use that observation as evidence of the candidate's physical location

#### Scenario: Date-format convention detected
- **WHEN** dates use a consistent DD/MM or MM/DD convention
- **THEN** the system may record the literal convention as a non-scoring observation but does not infer the candidate's country or locale from it

#### Scenario: Right-to-work statement surfaced
- **WHEN** the CV contains a right-to-work or visa statement
- **THEN** the system may surface the exact statement for human review without treating it as location or eligibility proof and without scoring it

## ADDED Requirements

### Requirement: Version and update the offline GeoNames index
Each V1 GeoNames index SHALL have a manifest containing the source file names and URLs, snapshot date, SHA-256 of every input file and the built index, index schema version, filtering rules, and record counts. The project SHALL refresh the snapshot quarterly through a manually started, reviewed, and approved process. CV analysis MUST NOT download or update GeoNames data.

#### Scenario: Index built for release
- **WHEN** the approved GeoNames inputs are transformed into the offline index
- **THEN** the build emits the required manifest and filters alternate names to identifiers retained in the city and country index

#### Scenario: Quarterly refresh prepared
- **WHEN** a new quarterly snapshot is proposed
- **THEN** a human starts and reviews the update before the new index becomes the configured reference-data version

#### Scenario: CV analyzed
- **WHEN** deterministic location resolution runs for a CV
- **THEN** it reads only the configured local versioned index and makes no reference-data network request

### Requirement: Separate deterministic result types
The deterministic core SHALL represent mechanically detected source values as `Candidate`, validated code-owned values as `Fact`, unresolved or non-scoring outcomes as `Observation`, and weighted rule outputs as `ScoringSignal`. It SHALL return these values through one `DeterministicAnalysisResult`.

#### Scenario: Candidate is detected but not validated
- **WHEN** code recognizes a phone, email, URL, date, national-ID, postal, or location-shaped source value without enough evidence to validate the required interpretation
- **THEN** the value remains a candidate or observation and cannot enter scoring

#### Scenario: Scoring input is created
- **WHEN** a fixed deterministic rule receives the validated code-owned facts it requires
- **THEN** it creates a `ScoringSignal` that references those facts and the configured ruleset rather than assigning weight during candidate extraction
