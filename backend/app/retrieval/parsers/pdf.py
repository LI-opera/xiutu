import logging
from io import BytesIO

from app.domain.documents import IngestError
from pypdf import PdfReader

VERSION = "pypdf-page-v1"
MAX_PAGES = 1000
MAX_TEXT = 10_000_000


def reader(data):
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-4096:]:
        raise IngestError("INVALID_PDF")
    try:
        result = PdfReader(BytesIO(data), strict=True)
        if result.is_encrypted:
            raise IngestError("ENCRYPTED_PDF")
        if not 0 < len(result.pages) <= MAX_PAGES:
            raise IngestError("PDF_PAGE_LIMIT")
        return result
    except IngestError:
        raise
    except Exception:
        raise IngestError("INVALID_PDF") from None


def parse(data, stopped):
    document = reader(data)
    blocks, issues, total = [], [], 0
    for number, page in enumerate(document.pages, 1):
        if stopped.is_set():
            raise IngestError("PARSE_STOPPED")
        try:
            value = page.extract_text() or ""
            has_images = bool(page.images)
        except Exception:
            raise IngestError("PDF_EXTRACTION_FAILED") from None
        if "\x00" in value:
            raise IngestError("PDF_UNSUPPORTED_TEXT")
        total += len(value)
        if total > MAX_TEXT:
            raise IngestError("PDF_TEXT_LIMIT")
        if not value.strip() or has_images:
            issues.append(
                dict(
                    page=number,
                    reason="no_text" if not value.strip() else "image_content_not_extracted",
                )
            )
        if value.strip():
            blocks.append(
                dict(
                    text=value,
                    char_start=0,
                    char_end=len(value),
                    page_start=number,
                    page_end=number,
                    heading_path=[],
                    kind="page",
                    locator={
                        "source": "pdf-page-extracted-text",
                        "page": number,
                        "layout_verified": False,
                    },
                )
            )
    return dict(
        blocks=blocks, page_count=len(document.pages), page_issues=issues, parser_version=VERSION
    )


# Uploaded content is untrusted; expose only our structured, sanitized errors.
_library_log = logging.getLogger("pypdf")
_library_log.addHandler(logging.NullHandler())
_library_log.propagate = False
