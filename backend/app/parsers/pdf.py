import logging
from io import BytesIO

import pdfplumber
import pypdfium2

from app.domain.errors import DomainError
from app.domain.models import SourceBlock
from app.parsers.ocr import ocr_page

logger = logging.getLogger(__name__)

# A page is treated as text-extractable only when its readable text lines
# contain at least this fraction of the total characters on the page.
# Below this threshold, text is sparse enough that OCR provides better coverage.
_HYBRID_TEXT_RATIO = 0.30


def _untangle_overprint(line: dict) -> dict:
    """Rebuild a line whose label and value were printed over each other in different fonts.

    A long bold label such as "Notify Party/Intermediate Consignee" can run into its regular-font
    value, so sorting the characters by position interleaves them. Characters of different fonts
    that overlap horizontally are regrouped by font, in left-to-right order of each group.
    """
    chars = sorted(line.get("chars") or [], key=lambda c: c["x0"])
    fonts = {c["fontname"] for c in chars}
    overlapped = any(
        a["fontname"] != b["fontname"] and b["x0"] < a["x1"] - 0.5
        for a, b in zip(chars, chars[1:])
    )
    if len(fonts) < 2 or not overlapped:
        return line
    groups: dict[str, list] = {}
    for char in chars:
        groups.setdefault(char["fontname"], []).append(char)
    ordered = sorted(groups.values(), key=lambda group: group[0]["x0"])
    return {**line, "text": " ".join(_run_text(group) for group in ordered)}


def _run_text(run: list) -> str:
    """Join one font's characters, adding a space at each real gap (words are placed by position)."""
    parts = []
    for previous, char in zip([None, *run], run):
        if previous is not None and char["x0"] - previous["x1"] > 1.0:
            parts.append(" ")
        parts.append(char["text"])
    return " ".join("".join(parts).split())


def _has_sufficient_text(lines: list) -> bool:
    """Return True if extracted text lines look substantially readable (not mostly replacement chars)."""
    if not lines:
        return False
    all_chars = sum(len(line["text"]) for line in lines)
    bad_chars = sum(
        line["text"].count("\ufffd") + line["text"].count("(cid:")
        for line in lines
    )
    readable_fraction = (all_chars - bad_chars) / max(all_chars, 1)
    return readable_fraction >= _HYBRID_TEXT_RATIO


def _raster_page_ocr(raster_document, page_number: int, source_id: str, settings) -> list[SourceBlock]:
    """Rasterize a single page and run OCR; returns blocks (may be empty on error)."""
    raster_page = raster_document[page_number - 1]
    width, height = raster_page.get_size()
    scale = 200 / 72
    if width * height * scale**2 > 20_000_000:
        raise DomainError(
            "FILE_LIMIT_EXCEEDED",
            "Rendered PDF page exceeds the pixel limit",
            status=413,
        )
    bitmap = raster_page.render(scale=scale)
    image = bitmap.to_pil()
    try:
        return ocr_page(
            image, source_id, page_number,
            languages=settings.ocr_languages,
            timeout=settings.parse_timeout_seconds,
        )
    finally:
        image.close()
        bitmap.close()
        raster_page.close()


def parse_pdf(
    data: bytes, source_id: str, *, max_pages: int, languages: str, timeout: int, settings=None
) -> tuple[list[SourceBlock], list[str]]:
    """Parse a PDF, falling back to OCR for pages with insufficient text.

    Hybrid pages (some text + some image content) get both text blocks and
    OCR blocks merged together so no field evidence is lost.
    """
    # Build a minimal settings shim when called from legacy paths without settings.
    if settings is None:
        class _S:
            ocr_languages = languages
            parse_timeout_seconds = timeout
        settings = _S()

    blocks, warnings = [], []

    # Primary parse attempt with pdfplumber + OCR fallback
    try:
        _parse_with_pdfplumber(data, source_id, max_pages, settings, blocks, warnings)
    except DomainError:
        raise
    except Exception as exc:
        # pdfplumber failed entirely — try pypdfium2-only OCR path
        logger.warning("pdfplumber failed for %s, attempting OCR-only path: %s", source_id, exc)
        blocks.clear()
        warnings.clear()
        try:
            _parse_ocr_only(data, source_id, max_pages, settings, blocks, warnings)
        except DomainError:
            raise
        except Exception as ocr_exc:
            raise DomainError("FILE_CORRUPT", "PDF could not be parsed by any available method") from ocr_exc

    return blocks, warnings


def _parse_with_pdfplumber(data, source_id, max_pages, settings, blocks, warnings):
    with pdfplumber.open(BytesIO(data)) as document:
        if len(document.pages) > max_pages:
            raise DomainError("FILE_LIMIT_EXCEEDED", "PDF exceeds the page limit", status=413)
        with pypdfium2.PdfDocument(data) as raster_document:
            for number, page in enumerate(document.pages, 1):
                lines = [_untangle_overprint(line) for line in page.extract_text_lines()]
                readable = [line for line in lines if line["text"].strip()]

                if _has_sufficient_text(readable):
                    # Good text-layer page — use pdfplumber text extraction
                    for index, line in enumerate(readable):
                        blocks.append(
                            SourceBlock(
                                id=f"{source_id}:page:{number}:line:{index}",
                                source_id=source_id,
                                text=line["text"],
                                locator={
                                    "type": "pdf_page",
                                    "page": number,
                                    "bbox": [float(line[key]) for key in ("x0", "top", "x1", "bottom")],
                                    "coordinate_space": "points",
                                },
                            )
                        )
                    # Also check for inline images that may contain additional field data
                    page_images = page.images
                    if page_images:
                        # Hybrid page: has text but also images — add OCR blocks for image areas
                        try:
                            ocr_blocks = _raster_page_ocr(raster_document, number, source_id, settings)
                            # Only add OCR blocks whose text doesn't duplicate existing text blocks
                            existing_texts = {b.text.strip() for b in blocks if b.locator.get("page") == number}
                            for ob in ocr_blocks:
                                if ob.text.strip() not in existing_texts:
                                    blocks.append(ob)
                        except Exception as exc:
                            warnings.append(f"Page {number} hybrid OCR skipped: {exc}")
                else:
                    # Sparse/corrupt text layer — fall back to OCR
                    try:
                        ocr_blocks = _raster_page_ocr(raster_document, number, source_id, settings)
                        blocks.extend(ocr_blocks)
                        warnings.append(f"Page {number} used OCR; inspect uncertain characters")
                    except Exception as exc:
                        warnings.append(f"Page {number} OCR failed: {exc}")


def _parse_ocr_only(data, source_id, max_pages, settings, blocks, warnings):
    """Full OCR path when pdfplumber fails entirely."""
    with pypdfium2.PdfDocument(data) as raster_document:
        page_count = len(raster_document)
        if page_count > max_pages:
            raise DomainError("FILE_LIMIT_EXCEEDED", "PDF exceeds the page limit", status=413)
        for number in range(1, page_count + 1):
            try:
                ocr_blocks = _raster_page_ocr(raster_document, number, source_id, settings)
                blocks.extend(ocr_blocks)
                warnings.append(f"Page {number} used OCR (full-raster path); inspect uncertain characters")
            except DomainError:
                raise
            except Exception as exc:
                warnings.append(f"Page {number} OCR failed in full-raster path: {exc}")
