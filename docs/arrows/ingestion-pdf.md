# Arrow: ingestion-pdf

Tier 3 data collection via PDF text extraction: meeting minutes, agendas, fiscal notes, staff reports.

## Status

**DEFERRED** - 2026-03-19. pdf_extractor.py is a stub raising NotImplementedError. All specs are [D]. No action until Phase 8+ AgendaCenter work begins.

## References

### HLD
- docs/high-level-design.md §4.3 Tier 3 table, §6 NG7 (meeting transcription deferred)

### LLD
- docs/llds/ingestion-pdf.md (created 2026-03-14)

### EARS
- docs/specs/ingestion-pdf-specs.md (5 specs: 0 active, 5 deferred)

### Tests
- tests/ingestion/test_pdf_extraction.py

### Code
- src/ingestion/extractors/pdf_extractor.py
- src/ingestion/extractors/agenda_parser.py

## Architecture

**Purpose:** Extract usable text from PDF documents published by county and town governments. PDF quality varies widely — from machine-generated (good) to scanned (requires OCR).

**Key Components:**
1. PDF text extractor — pdfplumber for machine-generated PDFs, Tesseract OCR for scanned docs
2. Agenda/minutes parser — structured extraction of agenda items, motions, votes from meeting documents
3. Document classifier — determine PDF type (agenda, minutes, ordinance text, fiscal note) for routing

## EARS Coverage

See spec file in References above.

## Key Findings

As of 2026-03-19: pdf_extractor.py is a stub that raises `NotImplementedError`. agenda_parser.py is not yet created. All 5 specs are [D] (deferred). No Bronze→Silver path exists for PDF content. Work blocked on CivicPlus AgendaCenter scraper (Phase 8+).

## Work Required

### Must Fix
1. Basic PDF text extraction pipeline (pdfplumber) for well-formed documents
2. Integration with CivicPlus AgendaCenter scraper (download PDFs → extract text → Bronze layer)

### Should Fix
1. OCR fallback for scanned documents (Tesseract)
2. Structured extraction of agenda items (item number, description, action taken)

### Nice to Have
1. LLM-assisted extraction for complex meeting minutes (votes, decisions, discussion summaries)
2. Laserfiche WebLink automation for Harford County historical documents
