"""
Tests for the PDF text extraction module with OCR fallback.

@spec INGEST-PDF-001, INGEST-PDF-002
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.extractors.pdf_extractor import (
    ExtractionResult,
    MIN_PAGE_TEXT_LENGTH,
    extract_text,
)


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def text_pdf(tmp_path):
    """Create a simple text-based PDF using pdfplumber-compatible format."""
    # We'll use a real minimal PDF with embedded text
    # This is a minimal valid PDF with one page containing "Hello World"
    pdf_content = (
        b"%PDF-1.0\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 44 >>\nstream\n"
        b"BT /F1 12 Tf 100 700 Td (Hello World Test PDF Content Here) Tj ET\n"
        b"endstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000360 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        b"startxref\n434\n%%EOF\n"
    )
    pdf_path = tmp_path / "text_test.pdf"
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.fixture
def sample_scanned_pdf():
    """Path to the sample scanned PDF from belairmd.org (if available)."""
    path = Path("tmp/sample_scanned.pdf")
    if not path.exists():
        pytest.skip("Sample scanned PDF not available at tmp/sample_scanned.pdf")
    return path


# ─── Tests: text-based PDFs ──────────────────────────────────────────


class TestTextPdfExtraction:
    """Test extraction from machine-generated PDFs with embedded text."""

    def test_extracts_text_from_path(self, text_pdf):
        """pdfplumber successfully extracts text from a text-based PDF."""
        result = extract_text(text_pdf, ocr_enabled=False)
        assert isinstance(result, ExtractionResult)
        assert result.page_count == 1
        assert result.ocr_page_count == 0
        assert "Hello World" in result.text

    def test_extracts_text_from_bytes(self, text_pdf):
        """Extraction works from raw bytes, not just file paths."""
        pdf_bytes = text_pdf.read_bytes()
        result = extract_text(pdf_bytes, ocr_enabled=False)
        assert isinstance(result, ExtractionResult)
        assert result.page_count == 1
        assert "Hello World" in result.text

    def test_no_ocr_when_text_sufficient(self, text_pdf):
        """OCR is not invoked when pdfplumber extracts sufficient text."""
        with patch(
            "src.ingestion.extractors.pdf_extractor._ocr_page"
        ) as mock_ocr:
            result = extract_text(text_pdf, ocr_enabled=True)
            mock_ocr.assert_not_called()
            assert result.ocr_page_count == 0


# ─── Tests: OCR fallback ────────────────────────────────────────────


class TestOcrFallback:
    """Test OCR fallback behavior for scanned pages."""

    def test_ocr_triggers_on_insufficient_text(self):
        """OCR is attempted when pdfplumber returns insufficient text."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""  # No text = scanned page

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf), \
             patch(
                 "src.ingestion.extractors.pdf_extractor._check_ocr_available",
                 return_value=True,
             ), \
             patch(
                 "src.ingestion.extractors.pdf_extractor._ocr_page",
                 return_value="OCR extracted text from scanned page successfully",
             ) as mock_ocr:
            result = extract_text("/fake/path.pdf")
            mock_ocr.assert_called_once_with(Path("/fake/path.pdf"), 1)
            assert result.ocr_page_count == 1
            assert "OCR extracted text" in result.text

    def test_graceful_when_ocr_unavailable(self):
        """Falls back to placeholder text when OCR deps not installed."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = ""

        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
        mock_pdf.__exit__ = MagicMock(return_value=False)

        with patch("pdfplumber.open", return_value=mock_pdf), \
             patch(
                 "src.ingestion.extractors.pdf_extractor._check_ocr_available",
                 return_value=False,
             ):
            result = extract_text("/fake/path.pdf")
            assert result.ocr_page_count == 0
            assert "[Page 1:" in result.text

    def test_ocr_disabled_flag(self, text_pdf):
        """OCR is skipped entirely when ocr_enabled=False."""
        with patch(
            "src.ingestion.extractors.pdf_extractor._check_ocr_available"
        ) as mock_check:
            extract_text(text_pdf, ocr_enabled=False)
            mock_check.assert_not_called()


# ─── Tests: end-to-end with real scanned PDF ────────────────────────


class TestScannedPdfEndToEnd:
    """End-to-end test with actual scanned PDF from belairmd.org."""

    def test_ocr_extracts_text_from_scanned_pdf(self, sample_scanned_pdf):
        """OCR successfully extracts readable text from a scanned government PDF."""
        result = extract_text(sample_scanned_pdf)
        assert result.page_count == 10
        assert result.ocr_page_count == 10  # All pages are scanned
        assert len(result.text) > 1000  # Should get substantial text
        # The document is about an annexation petition
        assert "annex" in result.text.lower() or "petition" in result.text.lower()

    def test_ocr_from_bytes(self, sample_scanned_pdf):
        """OCR works when PDF is provided as bytes (simulating download)."""
        pdf_bytes = sample_scanned_pdf.read_bytes()
        result = extract_text(pdf_bytes)
        assert result.page_count == 10
        assert result.ocr_page_count == 10
        assert len(result.text) > 1000


# ─── Tests: error handling ───────────────────────────────────────────


class TestErrorHandling:
    """Test error handling for invalid/corrupt PDFs."""

    def test_raises_on_empty_pdf(self, tmp_path):
        """Raises RuntimeError for files that aren't valid PDFs."""
        bad_pdf = tmp_path / "empty.pdf"
        bad_pdf.write_bytes(b"not a pdf")
        with pytest.raises(RuntimeError):
            extract_text(bad_pdf)

    def test_raises_on_nonexistent_file(self):
        """Raises RuntimeError for missing files."""
        with pytest.raises(RuntimeError):
            extract_text("/nonexistent/path.pdf")
