"""PDF text and table extraction using pdfplumber with PyMuPDF OCR fallback.

Strategy:
- Primary: pdfplumber for text + table extraction (best for structured autopsy reports)
- Fallback: PyMuPDF renders scanned pages to images, then pytesseract performs OCR
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pdfplumber
from pdfplumber.page import Page

from aiventra.core.config import Config

logger = logging.getLogger(__name__)


class PDFExtractionError(Exception):
    pass


def _extract_tables_from_page(page: Page) -> List[dict]:
    tables = []
    for table in page.extract_tables():
        if not table or len(table) < 2:
            continue
        headers = [str(cell).strip() if cell else "" for cell in table[0]]
        for row in table[1:]:
            row_data = {}
            for i, cell in enumerate(row):
                key = headers[i] if i < len(headers) else f"col_{i}"
                row_data[key] = str(cell).strip() if cell else ""
            tables.append(row_data)
    return tables


def _page_has_text(page: Page, min_chars: int = 50) -> bool:
    text = page.extract_text() or ""
    return len(text.strip()) >= min_chars


def _ocr_page_with_pymupdf(pdf_path: Path, page_number: int) -> str:
    try:
        import fitz
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise PDFExtractionError(
            "OCR fallback requires PyMuPDF, pytesseract, and Pillow. "
            "Install them or set AIVENTRA_OCR_FALLBACK=false."
        ) from exc

    if Config.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = Config.TESSERACT_CMD

    try:
        doc = fitz.open(str(pdf_path))
        page = doc[page_number]
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        text = pytesseract.image_to_string(img)
        doc.close()
        return text
    except Exception as exc:
        raise PDFExtractionError(f"OCR failed for page {page_number}: {exc}") from exc


def extract_text(pdf_path: Path) -> Tuple[str, List[dict], int]:
    """Extract text, tables, and page count from a PDF file.

    Returns:
        Tuple of (full_text, tables, page_count)
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if not pdf_path.suffix.lower() == ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    all_text: List[str] = []
    all_tables: List[dict] = []
    page_count = 0

    with pdfplumber.open(str(pdf_path)) as pdf:
        page_count = len(pdf.pages)

        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""

            if _page_has_text(page):
                all_text.append(f"--- Page {i + 1} ---\n{page_text}")
                all_tables.extend(_extract_tables_from_page(page))
            elif Config.OCR_FALLBACK:
                logger.info("Page %d has insufficient text, attempting OCR fallback", i + 1)
                try:
                    ocr_text = _ocr_page_with_pymupdf(pdf_path, i)
                    if ocr_text.strip():
                        all_text.append(f"--- Page {i + 1} (OCR) ---\n{ocr_text}")
                    else:
                        all_text.append(f"--- Page {i + 1} (OCR - no text found) ---\n")
                except PDFExtractionError:
                    logger.warning("OCR fallback failed for page %d", i + 1)
                    all_text.append(f"--- Page {i + 1} (empty) ---\n")
            else:
                all_text.append(f"--- Page {i + 1} (empty) ---\n")

    full_text = "\n\n".join(all_text)
    logger.info(
        "Extracted %d pages, %d tables, %d characters",
        page_count, len(all_tables), len(full_text),
    )
    return full_text, all_tables, page_count


def extract_page_texts(pdf_path: Path) -> Dict[int, str]:
    """Extract text per page, keyed by 1-indexed page number."""
    result: Dict[int, str] = {}

    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text() or ""

            if _page_has_text(page):
                result[i + 1] = page_text
            elif Config.OCR_FALLBACK:
                try:
                    ocr_text = _ocr_page_with_pymupdf(pdf_path, i)
                    result[i + 1] = ocr_text
                except PDFExtractionError:
                    result[i + 1] = ""
            else:
                result[i + 1] = ""

    return result