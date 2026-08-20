## MODIFIED Requirements

### Requirement: Identify the claimed location
The system SHALL identify a candidate's claimed location from explicit location candidates and source position using versioned code rules. The selected value SHALL keep exact source evidence. AI MAY provide a separate semantic interpretation for human review but MUST NOT supply or replace the claimed-location value used by deterministic scoring. When code cannot identify one value without guessing, the scoring claim SHALL be undetermined.

#### Scenario: Claim present in contact block
- **WHEN** versioned code rules find one unambiguous candidate location supported by source evidence
- **THEN** the system records it as the code-owned claimed location with its resolution status

#### Scenario: No identifiable claim
- **WHEN** the document contains several plausible person, employer, office, client, project, or education locations and code cannot distinguish one claimed location
- **THEN** the system marks the scoring claim as undetermined rather than asking AI to choose a verdict input

#### Scenario: AI interprets an ambiguous location
- **WHEN** AI returns a reviewer-facing interpretation for an otherwise ambiguous location
- **THEN** the report identifies it as AI-derived and excludes it from score and band calculation

### Requirement: Resolve locations via gazetteer
The system SHALL resolve explicit location strings to locality, country, and region using versioned offline reference data and deterministic normalization. It SHALL record unresolved and ambiguous results instead of silently choosing. AI and web research MUST NOT replace the code-owned resolution used by deterministic scoring.

#### Scenario: Unambiguous place
- **WHEN** a location string maps to one locality and country in the configured reference data
- **THEN** the system records the resolved location, reference-data version, and source evidence

#### Scenario: Ambiguous place name
- **WHEN** a location string maps to several plausible places
- **THEN** the system records the ambiguity and does not select a country for scoring

#### Scenario: Place absent from reference data
- **WHEN** reference data cannot resolve the attempted value
- **THEN** the system returns an unresolved location-validation observation and does not guess its country

### Requirement: Extract location-bearing evidence signals
The system SHALL extract versioned deterministic candidates and facts when source evidence supports them. Scored location evidence MAY include an explicit international phone country, a code-owned claimed-location resolution, and postal compatibility only when the country interpretation is unambiguous. The system SHALL keep right-to-work or visa text informational and SHALL NOT use spelling locale, currency, date-format locale, email TLD, employer location, education location, client location, project location, or office location as evidence of the candidate's physical location.

#### Scenario: Phone country code resolved offline
- **WHEN** an explicit international phone number is present and libphonenumber resolves it unambiguously
- **THEN** the system records its country, source evidence, and extractor version as a code-owned fact

#### Scenario: Phone lacks an international prefix
- **WHEN** a phone number cannot be assigned a country without a default region or another guessed assumption
- **THEN** its country remains unknown for scoring

#### Scenario: Postal format is shared by several countries
- **WHEN** a postal pattern has several plausible country interpretations
- **THEN** the system does not select the first matching country or score it as independent location evidence

#### Scenario: Weak locale proxy is present
- **WHEN** the CV contains a currency, spelling variant, date convention, email TLD, or organization location
- **THEN** the system does not use that observation as evidence of the candidate's physical location

#### Scenario: Date-format convention detected
- **WHEN** dates use a consistent DD/MM or MM/DD convention
- **THEN** the system may record the literal convention as a non-scoring observation but does not infer the candidate's country or locale from it

#### Scenario: Right-to-work statement surfaced
- **WHEN** the CV contains a right-to-work or visa statement
- **THEN** the system may surface the exact statement for human review without treating it as location or eligibility proof and without scoring it
