"""
Text extraction from uploaded documents.

Supports the formats people actually receive a job offer in: a PDF attachment,
a Word document, or a plain text file. Each extractor is optional at import
time, so a missing library disables one format rather than breaking the whole
service.

Extraction failure is never treated as evidence of fraud. If a file cannot be
read the caller is asked to paste the text instead.
"""

from __future__ import annotations

import io
import logging
import re

log = logging.getLogger(__name__)

# Kept small deliberately. A job listing is a page of text, and anything much
# larger is either the wrong file or an attempt to exhaust the service.
MAX_BYTES = 5 * 1024 * 1024

SUPPORTED = {
    ".pdf": "PDF document",
    ".docx": "Word document",
    ".txt": "Plain text",
}


class ExtractionError(Exception):
    """Raised when a file cannot be turned into usable text."""


def _clean(text: str) -> str:
    """Collapse the ragged whitespace that PDF extraction tends to produce."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionError(
            "PDF support is not installed on the server."
        ) from exc

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError(
            "That PDF could not be opened. It may be corrupted or password "
            "protected."
        ) from exc

    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            # One unreadable page should not lose the rest of the document.
            log.info("Skipped an unreadable PDF page.")

    return _clean("\n\n".join(pages))


def _from_docx(data: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise ExtractionError(
            "Word document support is not installed on the server."
        ) from exc

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("That Word document could not be opened.") from exc

    parts = [p.text for p in document.paragraphs]

    # Listings are often laid out in a table, and the paragraph walk misses
    # those entirely.
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return _clean("\n".join(parts))


def _from_txt(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return _clean(data.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise ExtractionError("That text file could not be decoded.")


_EXTRACTORS = {".pdf": _from_pdf, ".docx": _from_docx, ".txt": _from_txt}


def extension_of(filename: str) -> str:
    """Lowercase extension including the dot, or empty string."""
    _, _, tail = (filename or "").rpartition(".")
    return f".{tail.lower()}" if tail else ""


def extract(filename: str, data: bytes, min_chars: int = 40) -> str:
    """Return the text content of an uploaded file.

    Raises ExtractionError with a message written for the person who uploaded
    the file, not for a developer.
    """
    if not data:
        # Usually a file the operating system had not finished writing when it
        # was selected, rather than a genuinely empty document. Say so, since
        # the fix is simply to try again.
        raise ExtractionError(
            "That file came through empty. If you have just saved it, wait a "
            "moment and try again."
        )

    if len(data) > MAX_BYTES:
        raise ExtractionError(
            f"That file is larger than {MAX_BYTES // (1024 * 1024)} MB. "
            "Please upload just the job listing."
        )

    extension = extension_of(filename)
    extractor = _EXTRACTORS.get(extension)
    if extractor is None:
        supported = ", ".join(sorted(SUPPORTED))
        raise ExtractionError(
            f"Files ending in '{extension or filename}' are not supported. "
            f"Supported formats are {supported}."
        )

    text = extractor(data)

    if len(text) < min_chars:
        raise ExtractionError(
            "Very little text could be read from that file. If it is a scanned "
            "image or a screenshot, please paste the job description instead."
        )

    return text
