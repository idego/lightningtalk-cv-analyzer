## ADDED Requirements

### Requirement: Identify the claimed location
The system SHALL identify the candidate's claimed location from the CV header/contact block and treat it as the assertion under test. When the claim cannot be confidently identified, the system SHALL mark it as undetermined rather than guessing.

#### Scenario: Claim present in contact block
- **WHEN** the contact/header region contains a resolvable place (e.g. "Berlin, Germany")
- **THEN** the system records it as the claimed location with its resolved country/region

#### Scenario: No identifiable claim
- **WHEN** no location can be confidently identified as the claim
- **THEN** the system marks the claim as undetermined and flags this for the scoring stage

### Requirement: Resolve locations via gazetteer
The system SHALL resolve location strings to country/region using a gazetteer and positional/pattern rules, without ML or LLM components, and SHALL record ambiguity rather than silently choosing.

#### Scenario: Unambiguous place
- **WHEN** a location string maps to a single country/region in the gazetteer
- **THEN** the system resolves it to that country/region

#### Scenario: Ambiguous place name
- **WHEN** a location string matches multiple plausible places (e.g. "Paris, TX" vs "Paris, FR")
- **THEN** the system records the ambiguity as a finding and does not silently pick one

### Requirement: Extract location-bearing evidence signals
The system SHALL extract the following evidence signals when present: phone country code, contact-block address/postal-code format, most-recent-employer location (recency-weighted), date-format convention, spelling locale, education locations, currency, email TLD, right-to-work/visa statements, and national-ID presence.

#### Scenario: Phone country code resolved offline
- **WHEN** a phone number is present
- **THEN** the system resolves its country offline via libphonenumber and records it as a strong signal

#### Scenario: Date-format convention detected
- **WHEN** dates are present in a consistent DD/MM or MM/DD convention
- **THEN** the system records the implied locale as a medium signal

#### Scenario: Right-to-work statement surfaced
- **WHEN** the CV contains a right-to-work or visa statement
- **THEN** the system surfaces it as a finding regardless of its scoring weight

### Requirement: Detect national ID without retaining its value
The system SHALL detect the presence and type of a national-ID/tax number but MUST NOT capture or emit the raw value.

#### Scenario: National ID present
- **WHEN** a national-ID/tax-number pattern is detected
- **THEN** the system records only `present: true` and the detected type, never the raw digits
