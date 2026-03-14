# Ingestion: PDF Extraction Specifications

**Design Doc**: `/docs/llds/ingestion-pdf.md`
**Arrow**: `/docs/arrows/ingestion-pdf.md`

All specs in this file are deferred to Phase 4. The chat and dashboard are fully functional without PDF extraction.

## Text Extraction

- [D] **INGEST-PDF-001**: The system shall extract text from machine-generated PDFs using pdfplumber, preserving paragraph structure and table layouts.
- [D] **INGEST-PDF-002**: When pdfplumber extracts fewer than 100 characters per page, the system shall fall back to Tesseract OCR for text extraction.
- [D] **INGEST-PDF-003**: The system shall store a quality_score in bronze_documents raw_metadata: "high" for pdfplumber extraction, "medium" for OCR with >80% confidence, "low" for OCR with <80% confidence.

## Meeting Minutes Parsing

- [D] **INGEST-PDF-010**: The system shall detect agenda item boundaries in meeting minutes using numbered item headers, "New Business" / "Old Business" headings, and similar structural patterns.
- [D] **INGEST-PDF-011**: The system shall extract motion text and vote results from meeting minutes using pattern matching for "MOTION:", "MOVED:", and vote tally formats.
