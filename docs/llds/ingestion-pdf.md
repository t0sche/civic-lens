# Ingestion: PDF Extraction

**Created**: 2026-03-14
**Status**: Design Phase (Phase 4 — not yet scheduled)
**HLD Reference**: §4.3 Tier 3

## Context and Design Philosophy

PDF extraction is the highest-effort, lowest-reliability data source in the pipeline. Government PDFs range from machine-generated (clean text extraction) to scanned copies of paper documents (requires OCR). The design philosophy is **best-effort extraction with quality signals**: extract what we can, flag what's uncertain, and never silently serve low-quality data to users.

This is intentionally deferred to Phase 4 because the chat and dashboard are fully functional without it — state bills come from APIs, codified law comes from eCode360 HTML, and legislation status comes from the Bel Air legislation page. PDFs add meeting minutes and historical documents, which are valuable but not essential for MVP.

## Extraction Pipeline

### Tool Selection

**pdfplumber** is the primary extraction tool. It handles machine-generated PDFs well, extracting text with layout awareness (preserving table structure, column order). It's a Python-native library with no system dependencies.

**Tesseract OCR** is the fallback for scanned documents. It requires the `tesseract-ocr` system package (available in GitHub Actions Ubuntu runners). Quality is acceptable for printed government documents but poor for handwritten notes or low-resolution scans.

### Quality Detection

Before choosing an extraction method, the pipeline assesses PDF type:
1. Attempt pdfplumber text extraction
2. If extracted text length / page count > 100 chars/page → machine-generated, use pdfplumber output
3. If < 100 chars/page → likely scanned, fall back to Tesseract OCR
4. Store a `quality_score` in Bronze metadata: "high" (pdfplumber), "medium" (OCR, >80% confidence), "low" (OCR, <80% confidence)

### Structured Extraction (Meeting Minutes)

Meeting minutes follow predictable patterns:
- Agenda items are numbered or bulleted
- Motions have "MOTION:", "MOVED:", or similar prefixes
- Vote results follow patterns like "Approved 4-1" or "Unanimously approved"

A lightweight regex-based parser extracts structured data (agenda items, motions, votes) after raw text extraction. This structured data enriches the Silver `meeting_records` table and improves RAG retrieval quality.

## Open Questions & Future Decisions

### Deferred
1. Whether OCR quality justifies inclusion in the RAG corpus — low-quality OCR text may produce bad retrieval results
2. LLM-assisted extraction for complex meeting minutes — costly but more accurate than regex
3. Laserfiche WebLink automation for Harford County historical documents — requires headless browser + session management

## References

- pdfplumber: https://github.com/jsvine/pdfplumber
- Tesseract OCR: https://github.com/tesseract-ocr/tesseract
