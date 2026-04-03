"""
PDF text extraction with OCR fallback for scanned documents.

Uses pdfplumber as the primary extractor for machine-generated PDFs.
Falls back to pytesseract OCR (via pdf2image) for scanned/image-only pages.

@spec INGEST-PDF-001, INGEST-PDF-002
"""

from __future__ import annotations

import functools
import io
import logging
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

# Minimum text length (characters) to consider a page successfully extracted.
# Pages below this threshold are treated as scanned/image-only and sent to OCR.
MIN_PAGE_TEXT_LENGTH = 20

# Separator between pages in the joined output text.
PAGE_SEPARATOR = "\n\n---\n\n"

# DPI for rendering scanned pages as images for OCR.
# 300 is the standard for government documents; higher = better quality but more RAM.
OCR_DPI = 300

# Tesseract config: PSM 6 = single uniform block of text (best for legislative docs),
# OEM 3 = LSTM engine (best accuracy).
TESSERACT_CONFIG = "--psm 6 --oem 3"


@functools.lru_cache(maxsize=1)
def _check_ocr_available() -> bool:
    """Check if pytesseract and pdf2image are importable and tesseract is installed."""
    try:
        import pytesseract  # noqa: F401
        from pdf2image import convert_from_bytes, convert_from_path  # noqa: F401

        # Verify tesseract binary is reachable
        pytesseract.get_tesseract_version()
        return True
    except ImportError:
        logger.warning(
            "OCR dependencies not installed (pytesseract, pdf2image). "
            "Install with: pip install pytesseract pdf2image Pillow"
        )
        return False
    except Exception as e:
        logger.warning(
            f"Tesseract not available: {e}. "
            "Install with: brew install tesseract (macOS) or apt install tesseract-ocr (Linux)"
        )
        return False


def _ocr_page(source: str | Path | bytes, page_number: int) -> str:
    """OCR a single page from a PDF (file path or in-memory bytes)."""
    from pdf2image import convert_from_bytes, convert_from_path
    import pytesseract

    if isinstance(source, bytes):
        images = convert_from_bytes(
            source, dpi=OCR_DPI, first_page=page_number, last_page=page_number
        )
    else:
        images = convert_from_path(
            str(source), dpi=OCR_DPI, first_page=page_number, last_page=page_number
        )
    if not images:
        return ""
    return pytesseract.image_to_string(images[0], config=TESSERACT_CONFIG).strip()


@dataclass
class ExtractionResult:
    """Result of PDF text extraction."""

    text: str
    page_count: int
    ocr_page_count: int


def extract_text(
    source: str | Path | bytes,
    *,
    ocr_enabled: bool = True,
) -> ExtractionResult:
    """
    Extract text from a PDF, using OCR as fallback for scanned pages.

    Args:
        source: File path (str or Path) or raw PDF bytes.
        ocr_enabled: Whether to attempt OCR on scanned pages. Defaults to True.

    Returns:
        ExtractionResult with extracted text, page count, and count of OCR'd pages.

    Raises:
        RuntimeError: If the PDF cannot be opened or yields no text at all.

    @spec INGEST-PDF-001, INGEST-PDF-002
    """
    ocr_available = ocr_enabled and _check_ocr_available()

    if not ocr_available and ocr_enabled:
        logger.info("OCR requested but not available — extracting text only")

    if isinstance(source, bytes):
        pdf_bytes = source
        pdf_path = None
        source_name = "<bytes>"
    else:
        pdf_path = Path(source)
        pdf_bytes = None
        source_name = pdf_path.name

    pages_text: list[str] = []
    ocr_pages: list[int] = []

    try:
        file_obj = io.BytesIO(pdf_bytes) if pdf_bytes is not None else str(pdf_path)
        with pdfplumber.open(file_obj) as pdf:
            page_count = len(pdf.pages)
            if page_count == 0:
                raise RuntimeError(f"PDF has no pages: {source_name}")

            for i, page in enumerate(pdf.pages, start=1):
                try:
                    text = page.extract_text() or ""
                    text = text.strip()
                except Exception as e:
                    logger.warning(f"Page {i} pdfplumber error in {source_name}: {e}")
                    text = ""

                if len(text) >= MIN_PAGE_TEXT_LENGTH:
                    pages_text.append(text)
                    continue

                if ocr_available:
                    logger.debug(f"Page {i} of {source_name}: insufficient text, attempting OCR")
                    try:
                        ocr_text = _ocr_page(pdf_bytes if pdf_bytes is not None else pdf_path, i)

                        if len(ocr_text) >= MIN_PAGE_TEXT_LENGTH:
                            pages_text.append(ocr_text)
                            ocr_pages.append(i)
                            logger.debug(
                                f"Page {i} OCR success: {len(ocr_text)} chars"
                            )
                        else:
                            pages_text.append(f"[Page {i}: OCR returned insufficient text]")
                            ocr_pages.append(i)
                            logger.warning(
                                f"Page {i} of {source_name}: OCR returned only "
                                f"{len(ocr_text)} chars"
                            )
                    except Exception as e:
                        logger.warning(f"Page {i} OCR failed in {source_name}: {e}")
                        pages_text.append(f"[Page {i}: OCR failed — {e}]")
                else:
                    pages_text.append(f"[Page {i}: image-only or insufficient text]")

    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF {source_name}: {e}") from e

    full_text = PAGE_SEPARATOR.join(pages_text)

    if not full_text.strip():
        raise RuntimeError(
            f"No text extracted from {source_name}. "
            "The PDF may be fully scanned and OCR was unavailable or failed."
        )

    if ocr_pages:
        logger.info(
            f"{source_name}: OCR'd {len(ocr_pages)}/{page_count} pages: {ocr_pages[:10]}"
            + ("..." if len(ocr_pages) > 10 else "")
        )

    logger.info(f"Extracted {len(full_text)} chars from {page_count} pages: {source_name}")
    return ExtractionResult(
        text=full_text,
        page_count=page_count,
        ocr_page_count=len(ocr_pages),
    )
