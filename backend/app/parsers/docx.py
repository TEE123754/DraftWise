import io
import logging
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.domain.models import SourceBlock

logger = logging.getLogger(__name__)


def parse_docx(data: bytes, source_id: str, *, settings=None) -> tuple[list[SourceBlock], list[str]]:
    document = Document(BytesIO(data))
    blocks, warnings = [], []

    def walk(parent, prefix):
        for index, item in enumerate(parent.iter_inner_content()):
            path = f"{prefix}:{index}"
            if isinstance(item, Paragraph) and item.text.strip():
                blocks.append(
                    SourceBlock(
                        id=f"{source_id}:{path}",
                        source_id=source_id,
                        text=item.text,
                        locator={"type": "docx", "path": path},
                    )
                )
            elif isinstance(item, Table):
                seen = set()
                for r, row in enumerate(item.rows):
                    for c, cell in enumerate(row.cells):
                        if cell._tc in seen:
                            continue
                        seen.add(cell._tc)
                        walk(cell, f"{path}:row:{r}:cell:{c}")

    walk(document, "body")
    for index, section in enumerate(document.sections):
        walk(section.header, f"header:{index}")
        walk(section.footer, f"footer:{index}")

    # Extract and OCR embedded images if settings is provided and OCR is available
    if document.inline_shapes:
        warnings.append("Embedded images require image/OCR review")
        if settings is not None:
            image_blocks = _extract_docx_images(data, source_id, settings, len(blocks))
            if image_blocks:
                blocks.extend(image_blocks)
                warnings.append(f"OCR extracted {len(image_blocks)} blocks from {len(document.inline_shapes)} embedded image(s)")

    return blocks, warnings


def _extract_docx_images(data: bytes, source_id: str, settings, block_offset: int) -> list[SourceBlock]:
    """Extract images from a DOCX zip archive and OCR them."""
    from app.parsers.ocr import ocr_page
    try:
        from PIL import Image
    except ImportError:
        return []

    result = []
    image_index = 0
    try:
        with ZipFile(BytesIO(data)) as archive:
            image_names = [
                name for name in archive.namelist()
                if name.startswith("word/media/") and any(
                    name.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif")
                )
            ]
            for img_name in image_names:
                try:
                    img_data = archive.read(img_name)
                    image = Image.open(io.BytesIO(img_data)).convert("RGB")
                    ocr_blocks = ocr_page(
                        image,
                        source_id,
                        image_index + 1,
                        languages=settings.ocr_languages,
                        timeout=settings.parse_timeout_seconds,
                    )
                    # Remap block IDs to docx-image namespace
                    for block in ocr_blocks:
                        result.append(block.model_copy(update={
                            "id": f"{source_id}:image:{image_index}:ocr:{len(result)}",
                            "locator": {
                                **block.locator,
                                "type": "docx_image",
                                "image_name": img_name,
                                "image_index": image_index,
                            },
                        }))
                    image_index += 1
                    image.close()
                except Exception as exc:
                    logger.debug("DOCX image OCR skipped for %s/%s: %s", source_id, img_name, exc)
    except Exception as exc:
        logger.debug("DOCX image extraction failed for %s: %s", source_id, exc)
    return result
