"""
PDF text extraction pipeline — stub for Phase 4.

Extracts text from PDF documents (meeting agendas, minutes, ordinance
text, fiscal notes) using pdfplumber for machine-generated PDFs and
Tesseract OCR as a fallback for scanned documents.

@spec INGEST-PDF-001, INGEST-PDF-002
"""

import logging

logger = logging.getLogger(__name__)

# TODO: Implement in Phase 4
# - pdfplumber-based text extraction for well-formed PDFs
# - Tesseract OCR fallback for scanned documents
# - Document type classification (agenda, minutes, ordinance text, fiscal note)
# - Structured extraction of agenda items (item number, description, action)
# - Integration with CivicPlus AgendaCenter scraper (download → extract → Bronze)


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.

    Uses pdfplumber for machine-generated PDFs. Falls back to
    Tesseract OCR if pdfplumber returns insufficient text.

    @spec INGEST-PDF-001
    """
    raise NotImplementedError("PDF extraction not yet implemented — Phase 4")
