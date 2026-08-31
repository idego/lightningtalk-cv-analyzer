# location-signal-extraction Specification

## Purpose
Defines deterministic extraction and provenance for person-owned location,
phone, postal, and zero-weight review observations without guessing from
ambiguous evidence.

## Requirements

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
- **THEN** the system records a possible header-location observation that asks for human confirmation
- **AND** it never creates a `Fact` or `ScoringSignal` from that match

#### Scenario: Location ownership is unclear
- **WHEN** the document contains plausible person, employer, office, client, project, or education locations and code cannot distinguish one explicitly person-owned location
- **THEN** the system keeps those concepts separate and marks the scoring claim as undetermined

#### Scenario: Month-year employment range is present
- **WHEN** the source contains a range such as `04/2024 - 12/2024`
- **THEN** code retains the date candidates but does not classify the range as
  a phone candidate or use it as phone evidence

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
- **THEN** the system records the resolved location, available reference population, code authority, source evidence, extractor version, and reference-data version

#### Scenario: Country disambiguates a repeated locality name
- **WHEN** the same locality name exists in several countries and an explicit country resolves it to one record
- **THEN** the system preserves that record's population with the resolved claimed-location fact

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

#### Scenario: Email domain resembles a well-known provider typo
- **WHEN** a syntactically extracted email domain closely resembles, but does not equal, an official-source-backed domain or legitimate alias in the versioned common-provider reference catalog
- **THEN** the system may emit a code-owned `possible_email_domain_typo` observation with exact redacted source evidence and the reference-set version
- **AND** the observation has zero scoring weight and asks for confirmation without claiming that the address, domain, person, or CV is fake, invalid, or nonexistent

#### Scenario: Exact or custom email domain is present
- **WHEN** the extracted domain exactly matches a catalog entry or is an arbitrary company, organization, or custom domain
- **THEN** the common-provider typo rule emits no observation
- **AND** the system does not infer provider validity from absence in the bounded catalog

#### Scenario: Common-provider catalog is updated
- **WHEN** maintainers add or change a public-provider domain or legitimate alias
- **THEN** they record its provider family and official source, bump the catalog version, and review regression fixtures before release

#### Scenario: Date-format convention detected
- **WHEN** dates use a consistent DD/MM or MM/DD convention
- **THEN** the system may record the literal convention as a non-scoring observation but does not infer the candidate's country or locale from it

#### Scenario: Digits occur inside an email address
- **WHEN** a source span is part of a syntactically extracted email address
- **THEN** digits in that span do not create a phone candidate, phone fact, observation, or scoring signal

#### Scenario: Right-to-work statement surfaced
- **WHEN** the CV contains a right-to-work or visa statement
- **THEN** the system may surface the exact statement for human review without treating it as location or eligibility proof and without scoring it

### Requirement: Detect national ID without retaining its value
The system SHALL detect the presence and type of a national-ID/tax number but MUST NOT capture or emit the raw value.

#### Scenario: National ID present
- **WHEN** a national-ID/tax-number pattern is detected
- **THEN** the system records only `present: true` and the detected type, never the raw digits

### Requirement: Version and update the offline GeoNames index
Each V1 GeoNames index SHALL have a manifest containing the source file names and URLs, snapshot date, SHA-256 of every input file and the built index, index schema version, filtering rules, and record counts. The project SHALL refresh the snapshot quarterly through a manually started, reviewed, and approved process. CV analysis MUST NOT download or update GeoNames data.

The full development and production analyzer SHALL require a valid approved
GeoNames index and manifest at application startup. It MUST NOT silently start
the complete analyzer with location resolution disabled. An intentionally
reduced diagnostic mode MAY omit the resolver only when enabled by an explicit
configuration flag and exposed as degraded by health status.

#### Scenario: Index built for release
- **WHEN** the approved GeoNames inputs are transformed into the offline index
- **THEN** the build emits the required manifest and filters alternate names to identifiers retained in the city and country index

#### Scenario: Quarterly refresh prepared
- **WHEN** a new quarterly snapshot is proposed
- **THEN** a human starts and reviews the update before the new index becomes the configured reference-data version

#### Scenario: CV analyzed
- **WHEN** deterministic location resolution runs for a CV
- **THEN** it reads only the configured local versioned index and makes no reference-data network request

#### Scenario: Full analyzer starts without reference data
- **WHEN** the complete analyzer is started without a readable valid GeoNames pair
- **THEN** startup fails with a configuration error before accepting CVs

#### Scenario: Diagnostic degraded mode is explicitly enabled
- **WHEN** an operator explicitly starts the diagnostic mode without GeoNames
- **THEN** health status reports location resolution as unavailable and the UI does not present the analyzer as fully ready

### Requirement: Separate deterministic result types
The deterministic core SHALL represent mechanically detected source values as `Candidate`, validated code-owned values as `Fact`, unresolved or non-scoring outcomes as `Observation`, and weighted rule outputs as `ScoringSignal`. It SHALL return these values through one `DeterministicAnalysisResult`.

#### Scenario: Candidate is detected but not validated
- **WHEN** code recognizes a phone, email, URL, date, national-ID, postal, or location-shaped source value without enough evidence to validate the required interpretation
- **THEN** the value remains a candidate or observation and cannot enter scoring

#### Scenario: Scoring input is created
- **WHEN** a fixed deterministic rule receives the validated code-owned facts it requires
- **THEN** it creates a `ScoringSignal` that references those facts and the configured ruleset rather than assigning weight during candidate extraction

### Requirement: Exclude exact quarantined evidence before signal materialization

Deterministic candidate extraction SHALL consume the shared versioned visibility-exclusion index. Any evidence span intersecting an exact quarantined interval SHALL be inadmissible for candidate ownership, facts, observations that expose the source value, and scoring signals. A normalized literal with both hidden and independently visible evidence MAY remain supported only by its visible evidence. Partial or unmapped presentation evidence SHALL not remove canonical text but SHALL produce honest partial coverage.

The exclusion policy SHALL apply to phone, location, postal, date, email, URL, right-to-work, national-ID presence disclosure, and any new structured candidate category before aggregation or deduplication. Mandatory national-ID redaction remains authoritative and excluded national-ID characters MUST NOT be exposed through quarantine diagnostics.

#### Scenario: Hidden phone and visible phone disagree
- **WHEN** one valid person phone occurs only in an exact quarantined span and another occurs visibly
- **THEN** only the visible phone may contribute facts and aggregate signals

#### Scenario: Equivalent literal is hidden and visible
- **WHEN** the same normalized candidate occurs in hidden and visible source locations
- **THEN** deduplication retains only independently visible evidence on the admitted candidate

#### Scenario: Exclusion association is partial
- **WHEN** a presentation signal cannot be exactly mapped to the candidate span
- **THEN** code does not remove the candidate solely from that uncertain mapping and reports partial visibility coverage
