# Data Pipeline Specifications

**Design Doc**: `/docs/llds/data-pipeline.md`
**Arrow**: `/docs/arrows/data-pipeline.md`

## Normalization: Open States → Silver

- [ ] **DATA-PIPE-001**: When normalizing an Open States bill, the system shall set jurisdiction to STATE and body to "Maryland General Assembly".
- [ ] **DATA-PIPE-002**: When normalizing an Open States bill, the system shall derive status from the most recent action's classification list, mapping recognized classifications (introduction, referred-to-committee, signed, became-law, vetoed, failed) to the corresponding LegislativeStatus enum value.
- [ ] **DATA-PIPE-003**: When no recognized action classification is found, the system shall set status to UNKNOWN.
- [ ] **DATA-PIPE-004**: When normalizing an Open States bill, the system shall extract sponsor names from the sponsorships array into the sponsors list.
- [ ] **DATA-PIPE-005**: When normalizing an Open States bill, the system shall use the first abstract's text as the summary field, or null if no abstracts exist.
- [ ] **DATA-PIPE-006**: When normalizing an Open States bill, the system shall classify the item_type as BILL if "bill" appears in the classification array, RESOLUTION if "resolution" appears, and BILL as the default fallback.
- [ ] **DATA-PIPE-007**: When normalizing an Open States bill, the system shall parse introduced_date from first_action_date and last_action_date from the most recent action's date field, returning null for unparseable dates.

## Normalization: Bel Air Legislation → Silver

- [ ] **DATA-PIPE-010**: When normalizing a Bel Air legislation entry, the system shall set jurisdiction to MUNICIPAL and body to "Town of Bel Air Board of Commissioners".
- [ ] **DATA-PIPE-011**: When normalizing a Bel Air legislation entry, the system shall map item_type from the entry's item_type field: "ordinance" to ORDINANCE, "resolution" to RESOLUTION, all others to OTHER.
- [ ] **DATA-PIPE-012**: When normalizing a Bel Air legislation entry, the system shall map status from the entry's status field using direct mapping (APPROVED→APPROVED, PENDING→PENDING, TABLED→TABLED, EXPIRED→EXPIRED, REJECTED→REJECTED), defaulting to UNKNOWN.

## Normalization: eCode360 → Silver

- [ ] **DATA-PIPE-020**: When normalizing an eCode360 section with municipality_code "BE2811", the system shall set jurisdiction to MUNICIPAL and code_source to "Town of Bel Air Code".
- [ ] **DATA-PIPE-021**: When normalizing an eCode360 section with municipality_code "HA0904", the system shall set jurisdiction to COUNTY and code_source to "Harford County Code".
- [ ] **DATA-PIPE-022**: The system shall construct a section_path breadcrumb in the format "{code_source} > {chapter} > {section_title}" for each normalized code section.
- [ ] **DATA-PIPE-023**: The system shall store the full extracted text as the content field of the code_section record.

## Silver Layer Writing

- [ ] **DATA-PIPE-030**: The system shall upsert legislative_items using (source_id, jurisdiction, body) as the conflict key, ensuring idempotent writes across repeated pipeline runs.
- [ ] **DATA-PIPE-031**: The system shall upsert code_sections using (code_source, chapter, section) as the conflict key, ensuring idempotent writes across repeated pipeline runs.
- [ ] **DATA-PIPE-032**: When a Bronze record's source is not recognized by any registered normalizer, the system shall log a warning and skip the record without failing the pipeline run.

## Validation

- [ ] **DATA-PIPE-040**: The system shall reject Silver records where title is empty or exceeds 500 characters, logging the rejected record.
- [ ] **DATA-PIPE-041**: The system shall reject Silver records where source_id is empty, logging the rejected record.
- [ ] **DATA-PIPE-042**: The system shall reject Silver records where body is empty, logging the rejected record.

## Enrichment (Post-Normalization)

- [D] **DATA-PIPE-050**: Where a legislative_item has a null summary, the system shall generate a plain-language summary of 2-3 sentences using Gemini Flash and write it to the summary field.
- [D] **DATA-PIPE-051**: Where a legislative_item has an empty tags array, the system shall classify the item into 1-3 topic tags from a predefined taxonomy using Gemini Flash and write them to the tags field.
- [D] **DATA-PIPE-052**: The predefined topic taxonomy shall include: zoning, taxes, public-safety, education, transportation, environment, housing, business, health, budget, elections, utilities.

## Pipeline Execution

- [ ] **DATA-PIPE-060**: The normalization pipeline shall process all Bronze records when no source filter is specified, or only records matching the specified source.
- [ ] **DATA-PIPE-061**: The normalization pipeline shall be fully idempotent — running it twice on the same Bronze data shall produce identical Silver state.
