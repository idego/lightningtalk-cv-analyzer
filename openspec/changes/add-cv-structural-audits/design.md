## Context

The current pipeline keeps a canonical page/line model, extracts PDF text with `pdfplumber`, extracts DOCX text from paragraphs and tables, redacts national IDs, then runs deterministic location analysis and optional AI analysis. PDF/DOCX presentation attributes are currently discarded after text extraction. The existing frontend date-range helper formats date values already returned by AI; it is not an independent audit of raw CV text. See `proposal.md` for the motivation and `specs/cv-structural-audits/spec.md` for the behavior contract.

The existing `Report` and persistence layers already have backward-compatible nullable extensions for file/link data, while the score and band are deliberately produced by a separate deterministic location-scoring boundary. The structural audit must fit beside that boundary and must also work when AI is disabled.

## Goals / Non-Goals

**Goals:**

- Parse and validate timeline ranges from the redacted canonical source, with stable evidence and precision metadata.
- Inspect format-level PDF/DOCX presentation data in memory and turn defensible hidden-content signals into bounded, neutral observations.
- Return one versioned, optional structural-audit object through the existing report/API/persistence envelope and derive dedicated reviewer-panel items from it without changing the existing checklist contract.
- Keep the score, band, location findings, AI input contract, research subjects, national-ID policy, and legacy report readers compatible.
- Make all rules offline, deterministic, configurable/versioned, and testable with synthetic fixtures.

**Non-Goals:**

- Rendering DOCX to PDF, OCR, image steganography, revision-history reconstruction, digital-signature validation, or a general authenticity assessment.
- Semantic interpretation of job duties, whether two jobs were mutually exclusive, or whether an overlap indicates deception.
- Treating future dates, concurrent employment, white text on an unknown background, or document metadata as proof of a problem.
- Adding structural observations to location score weights, bands, automated hiring actions, AI prompts, or public research queries.

## Decisions

### D1: Use a dedicated, explicit structural-audit contract beside location findings

Add a typed `StructuralAuditResult` to the report rather than encoding timeline pairs and visibility spans as location `Observation` or weighted `Finding` records. The exact public shape is fixed by the new spec and is intentionally small:

```text
structural_audits = {
  contract_version: "structural-audits-v1",
  status: completed | partial | unavailable | not_applicable,
  snapshot_month: YYYY-MM | null,
  coverage: {
    status, source_format, audited_parts: string[], omitted_parts: string[]
  },
  timeline: {
    status, parser_version, entries: TimelineEntry[],
    summaries: TimelineSummary[], observations: TimelineObservation[],
    reported_entry_count, additional_entry_count, truncated
  },
  visibility: {
    status, detector_version, threshold_version,
    observations: VisibilityObservation[],
    reported_observation_count, additional_observation_count, truncated
  }
}
```

`TimelineEntry` has a stable in-report ID, category, valid/invalid/unresolved status, bounded start/end source tokens, nullable normalized months, endpoint precision, one canonical source location, and bounded date evidence. `TimelineObservation` has a stable ID, `invalid_period`/`definite_overlap`/`possible_overlap` kind, review status, one or two entry IDs, nullable exact overlap months, precision, reason code, and bounded evidence. `VisibilityObservation` has a stable ID, trigger kind, confidence, source location, trigger codes, bounded character/word counts, optional redaction presence/type metadata, and threshold/version data; it has no text excerpt field. A source location always carries page identity and an `exact`/`partial`/`unmapped` association plus nullable line/offset/paragraph/bounding-box fields.

Arrays are source ordered and capped at 100 timeline entries, 100 timeline observations, and 50 visibility observations. Timeline evidence excerpts are capped at 256 characters and visibility excerpts are forbidden. Counts, truncation, and coverage make a partial result distinguishable from a completed no-finding result. This keeps structural data auditable without making it look like a location verdict. Reusing `Finding` would make the UI and scoring code more likely to assign an importance or weight accidentally; reusing location observations would also misrepresent the authority and subject.

### D2: Preserve exact provenance while retaining a transient presentation index

Extend the raw/redacted document flow with an in-memory, format-specific presentation index and character/run provenance. The canonical text builder and the presentation index must share the same source atoms: every canonical character is associated with an originating PDF character or DOCX text node/run, or explicitly marked as a synthetic separator. This avoids the unsafe combination of independently generated text and style spans.

For PDF, source atoms retain page coordinates, rendered size, opacity/color attributes when exposed, and paint-order/background references when available. For DOCX, source atoms retain the package part, paragraph/table path, text-node/run range, logical page, and relevant OOXML presentation properties. The current V1 audited DOCX surface is body paragraphs and table cells; headers, footers, textboxes, footnotes/endnotes, comments, drawings, and embedded files are not silently folded into that surface.

Each presentation span receives one of three association states:

- `exact`: every non-synthetic character maps to one canonical source range;
- `partial`: some characters map, but the span cannot safely produce a complete excerpt;
- `unmapped`: no canonical character mapping is proven, although a format-level page/paragraph location may still be reported.

Timeline evidence and excerpts require `exact` or `partial` canonical mapping. Visibility findings may use `unmapped` locations but must omit text. If a compatibility fixture cannot preserve existing canonical text while adding provenance, the implementation keeps the existing text and marks the presentation span partial/unmapped instead of guessing. This is verified with canonical-text invariance tests.

The presentation index is carried through national-ID redaction using the same-length canonical offsets, and redaction records remain attached to overlapping presentation spans. Structural audits run against the redacted source and redacted presentation map; an ID-only hidden span is therefore still identifiable by safe metadata without retaining its value.

### D3: Make the backend timeline parser authoritative and line-bounded

Implement one backend parser over `SourcePage.lines`; the browser-side date-summary helper remains a display compatibility helper and is not used as an analysis authority. Use a two-stage lexer/validator. The lexer recognizes date-like ranges with one- or two-digit numeric month tokens, four-digit year tokens, supported English and Polish month names/abbreviations, bounded separators (`-`, en dash, `to`, `do`), and `present`/`current`/`now`. It retains malformed month tokens such as `00/2024` and `13/2024` for validation. The validator then produces valid, invalid, or unresolved entries.

V1 entry association is deliberately line-bounded. A recognized employment or education heading is a standalone heading from a reviewed English/Polish lexicon; its category persists until the next recognized top-level heading. Contact, birth-details, certifications, projects, publications, awards, and other headings reset the state to `other`. A date range must occur on the same canonical line as non-date entry text under an employment or education state. The parser does not join lines, infer visual columns, use font weight as a heading, or create separate entries when a line contains multiple ambiguous ranges; such a line is retained as unresolved. Birth/DOB and similar exclusion labels win even if a malformed document places them under a timeline heading.

Without an unambiguous category, an entry is retained as `unknown` for disclosure but is not paired with known employment/education entries for anomaly reporting. Normalization uses an integer month index. Month-precise intervals include both endpoint months. Year-only endpoints cover the referenced calendar years but retain year precision; `present` resolves to the injected run snapshot. Valid intervals are merged per category for non-overlapping duration totals. Invalid and unresolved entries never contribute to totals.

### D4: Separate definite overlap from precision-limited possibility

Compare only valid entries in the same known category, excluding the same entry and duplicate source spans. Use half-open arithmetic internally so adjacent periods do not overlap. When both endpoints are month-precise, an intersection of one or more complete months becomes `definite_overlap` with an exact month count. When either interval is year- or mixed-precision, an intersecting coarse interval becomes `possible_overlap` with no exact month count.

Emit each unordered pair once in stable source order. Keep the observation neutral and attach a reviewer explanation that concurrent work, part-time work, contracting, internships, and study arrangements can be legitimate. No semantic mutual-exclusivity check is introduced.

The pipeline supplies one immutable `snapshot_month`/clock value for the entire analysis. It is persisted in the structural result and reused when an AI retry replaces only the AI section or when a persisted report is reopened. A browser clock is never used to recompute backend timeline values.

### D5: Use explicit, conservative visibility rules with pre-materialization limits

The first detector version combines independent format signals instead of trying to infer intent:

1. explicit DOCX hidden/vanished text is high-confidence;
2. zero/near-zero rendered text size is low-visibility when the format exposes a reliable size;
3. zero/near-zero opacity is low-visibility when the format exposes it;
4. white/near-white text is low-contrast only when a light background is deterministically established for the same span.

The versioned configuration has these V1 defaults: `near_zero_font_points = 1.0`, `near_zero_opacity = 0.05`, `near_white_luminance = 0.95`, `known_light_background_luminance = 0.95`, `max_low_contrast_luminance_delta = 0.05`, and `minimum_meaningful_alphanumeric = 3`. PDF sizes are points; DOCX half-points are divided by two. This catches a roughly `0.5px` span after unit conversion without treating CSS pixels as universal document units. Colors are converted to normalized relative luminance; an explicit background is light when its luminance is at least `0.95`, and low contrast requires both the foreground/background rule and the configured luminance delta.

DOCX style resolution follows run properties, character style, paragraph style, and document defaults in that order. An unresolved inherited value does not create a positive finding and marks the affected coverage partial/unavailable. PDF background evidence requires an explicit light-filled page object/paint region covering the span with a safe paint order; the default page canvas, an unknown image background, and an unproven white backdrop are not treated as known light backgrounds. White text over a known dark background is excluded.

Only spans with at least three Unicode letters/digits or one token of at least three such characters are materialized. A span overlapping a redaction record bypasses that filter only for safe sensitive-presence metadata. Adjacent characters with the same trigger and source association are grouped before report creation. Hard caps apply while collecting atoms/runs, not only after the full file is materialized: `max_pdf_atoms = 100000`, `max_docx_runs = 20000`, `max_timeline_entries = 100`, `max_timeline_observations = 100`, `max_visibility_observations = 50`, and `max_evidence_excerpt_chars = 256`. Hitting a cap stops that inspection path, sets partial/truncated coverage, and never fails the base analysis.

### D6: Run audits after redaction and outside the verdict path

The pipeline order becomes:

1. ingest canonical pages, file details, links, and transient presentation/provenance data;
2. redact national IDs and retain redaction-span metadata;
3. obtain one injected analysis snapshot month;
4. run timeline and visibility audits on the redacted document/presentation map;
5. run the existing deterministic location extraction and scoring unchanged;
6. attach the structural result to the report;
7. serialize the dedicated structural panel data and optionally run the existing AI/research flows.

The audit result is never passed as AI facts, prompt instructions, research input, or score signals. The AI input builder accepts only its existing redacted document/deterministic observation contract, and the current prompt/version remain unchanged. Existing AI semantic `timeline_overlap` findings remain a separate AI-authority result; structural `definite_overlap`/`possible_overlap` codes are not converted into AI findings or deduplicated by authority-blind matching. Existing AI behavior concerning the redacted canonical document is not silently rewritten in this change; excluding low-visibility text from AI input would require a separate contract decision. Structural observations therefore cannot alter the score, band, location signal count, research subjects, or automated action.

### D7: Keep persistence bounded and backward-compatible

Serialize the new object at the top level of the existing report payload. The audit log already stores the complete payload, so no new SQLite table is required for V1. Existing `reports.findings_json` remains compatible for history/listing; the full structural object is restored from the audit-log payload. Old payloads deserialize with `structural_audits = null`.

Create one `sanitize_structural_audits` boundary and call it for both initial report persistence and `replace_ai_analysis`. It validates the exact contract version/status enums, allowlists every structural key and reason/trigger code, enforces the array/count/geometry/excerpt limits, rejects unknown visibility text fields, and preserves only safe redaction presence/type metadata. Invalid structural input fails closed by omitting the structural object or returning a neutral unavailable state while retaining the base report; it is never stored verbatim. The same sanitized structural object is copied through an AI retry, so retry cannot recompute or erase the original snapshot/audit. The existing national-ID sanitizer remains authoritative for every evidence field before audit-log and report storage.

Use a dedicated typed `StructuralAuditPanel`/row model in the web app rather than passing structural objects through `ReviewFlag`, `FlagList`, or the fixed checklist label map. Exact overlaps show the shared-month count; possible overlaps show the precision limitation; invalid periods show both endpoints; visibility items show trigger and technical location data. Visibility rows have no excerpt fallback. Structural status/coverage is visible even when there are no findings. None uses `SUSPICIOUS`, a fraud label, or a candidate-level verdict. English and Polish UI copy share stable machine-readable codes. AI `timeline_overlap` remains visibly separate by authority, even when source locations coincide.

### D8: Test the format boundary with synthetic, offline fixtures

Add unit tests for the exact contract schema, stable ordering/limits, source association states, month-index parsing, localized tokens, malformed months/order, entry-heading boundaries, unrelated-date exclusions, injected snapshot/retry behavior, adjacency, exact overlap, possible overlap, category isolation, duplicate suppression, and merged duration. Add provenance tests proving canonical text remains compatible and that unsafe PDF/DOCX mapping becomes partial/unmapped rather than fabricated evidence.

Add PDF fixtures with tiny/normal text, explicit light/dark paint regions, unknown backgrounds, missing attributes, atom-cap truncation, and color/opacity variants. Add DOCX fixtures with hidden runs, inherited/explicit styles, shading, normal light-on-dark text, small fonts, unsupported headers/footers, and a redacted ID-only hidden span. Add serialization/persistence tests proving the structural sanitizer is shared by initial save and AI retry, hidden text is absent from the structural payload, coverage is honest, audit availability does not fail the base report, the AI prompt contract remains unchanged, and score/band output is invariant when structural observations are added.

Do not use private CV corpus content in fixtures or logs. Exercise the full pipeline with AI disabled and use fake format metadata rather than network services.

## Risks / Trade-offs

- **PDF coordinates and extracted text do not align perfectly** → Build canonical text and presentation spans from shared provenance, retain exact/partial/unmapped association, and never fabricate a sentence excerpt for a span that cannot be mapped safely.
- **White text can be intentional design** → Require deterministically known light background, exclude light-on-dark spans, and use a neutral `Needs review` label rather than a suspicious verdict.
- **Year-only dates create false certainty** → Keep precision on every endpoint and emit `possible_overlap` without an exact month count.
- **Section headings and multi-column extraction can be ambiguous** → Use line-bounded entry association and a small reviewed heading lexicon, retain `unknown`/unresolved entries, and avoid pairing ambiguous entries into anomaly claims.
- **DOCX rendered layout varies by environment** → Inspect OOXML presentation properties only; do not render or infer physical pages in this change.
- **Large or adversarial files may contain many tiny spans** → Enforce atom/run caps before materialization, group identical adjacent triggers, cap observations, and return aggregate truncation metadata.
- **Current-month ranges are time-dependent** → Inject one snapshot month per analysis, persist it, and reuse it during retries and report reloads.
- **Hidden content may contain sensitive values** → Run after national-ID redaction, omit hidden text from new report fields, and sanitize the full payload before persistence/logging.
- **AI and deterministic timeline findings may duplicate each other** → Keep authority/code namespaces separate, assert the AI input builder does not accept structural data, and show provenance separately in the UI.
- **Anomaly findings may be overread by recruiters** → Keep them outside score/band, show neutral reviewer language and source evidence, and retain the decision-support disclaimer.

## Migration Plan

1. Add the exact optional structural-audit domain/serialization shape, status/coverage semantics, and backward-compatible readers without changing existing reports.
2. Extend PDF/DOCX ingestion with shared provenance, bounded presentation records, explicit V1 audited/omitted parts, and redaction-span propagation; verify canonical text, national-ID redaction, location facts, score, band, and existing AI payload invariants.
3. Implement the injected-snapshot timeline parser and visibility detector behind the new result object, with synthetic offline fixtures, honest partial/unavailable states, and pre-materialization limits.
4. Attach the result in the pipeline, preserve it through AI retry, and keep structural data out of score/research paths and the AI input builder.
5. Add the dedicated localized recruiter disclosure and regression-test persisted reports, including reports created before this change and reports reopened after AI retry.
6. Roll back by disabling structural-audit generation or reverting the application build; nullable readers and existing report fields remain usable, and no scoring or database migration rollback is required.
