# analyze-settings Specification

## Purpose
Defines the browser-side settings that shape the analyze experience and the
automatic research orchestrator they control.

## Requirements

### Requirement: Versioned local settings
Settings SHALL persist in `localStorage` under a versioned schema (currently v2) with a migration from v1. Settings are `uiLanguage` and `reportLanguage` (`en`/`pl`), `aiEnabled`, `autoResearchEnabled` with per-category `autoCompanyResearch`, `autoEducationResearch`, `autoLinkedinDiscovery`, `previewFindingsOnHover`, and `expandSectionsByDefault`.

#### Scenario: v1 settings present
- **WHEN** a browser holds v1 settings
- **THEN** they are migrated to v2 with new keys at their defaults

### Requirement: Localized copy
All analyze UI strings SHALL come from a single copy table keyed by `uiLanguage`, with `{placeholder}` substitution for dynamic values such as counts and search subjects.

#### Scenario: Language switched
- **WHEN** the user switches `uiLanguage`
- **THEN** visible and accessible copy change without reload

### Requirement: Automatic research orchestrator
A single client-side orchestrator SHALL start each enabled, eligible research category once per analysis after base analysis completes, tracking `pending`, `running`, `succeeded`, `failed`, and `manual-action` states. A 504 SHALL be surfaced as a timeout distinct from other failures. A failed automatic attempt SHALL leave the manual `Start` action available, and a second automatic attempt MUST NOT be made for the same analysis and category.

#### Scenario: Category disabled
- **WHEN** `autoCompanyResearch` is off
- **THEN** company research is not started automatically but remains startable manually
