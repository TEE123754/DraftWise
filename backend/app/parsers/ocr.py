import os

import pytesseract
from PIL import ImageOps
from pytesseract import Output

from app.config import get_settings
from app.domain.errors import DomainError
from app.domain.models import SourceBlock


def _configure_tesseract() -> None:
    """Point pytesseract at the configured binary for hosts where it is not on PATH.

    A process-level TESSERACT_CMD wins; otherwise the value comes from backend/.env via Settings,
    which pydantic-settings does not export to os.environ.
    """
    command = os.environ.get("TESSERACT_CMD") or get_settings().tesseract_cmd
    if command:
        pytesseract.pytesseract.tesseract_cmd = command


def ocr_page(
    image, source_id: str, page: int, *, languages: str, timeout: int
) -> list[SourceBlock]:
    _configure_tesseract()
    if image.width * image.height > 20_000_000:
        raise DomainError("FILE_LIMIT_EXCEEDED", "Raster page exceeds 20 megapixels", status=413)
    grayscale = ImageOps.grayscale(image)
    try:
        data = pytesseract.image_to_data(
            grayscale, lang=languages, timeout=timeout, output_type=Output.DICT
        )
    except pytesseract.TesseractNotFoundError:
        # Fallback gracefully if Tesseract binary is not installed on the system
        return [
            SourceBlock(
                id=f"{source_id}:page:{page}:ocr:0",
                source_id=source_id,
                text="[OCR UNAVAILABLE: Tesseract not installed on host]",
                kind="ocr",
                quality=0.0,
                locator={
                    "type": "pdf_page",
                    "page": page,
                    "bbox": [0.0, 0.0, float(image.width), float(image.height)],
                    "coordinate_space": "pixels",
                    "image_width": image.width,
                    "image_height": image.height,
                },
            )
        ]
    except RuntimeError as exc:
        raise DomainError("OCR_TIMEOUT", "OCR exceeded its time limit", retryable=True) from exc
    finally:
        grayscale.close()
    lines = {}
    for index, word in enumerate(data["text"]):
        if not word.strip():
            continue
        key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        lines.setdefault(key, []).append(index)
    result = []
    for index, indexes in enumerate(lines.values()):
        confidence = min(float(data["conf"][i]) for i in indexes) / 100
        left = min(data["left"][i] for i in indexes)
        top = min(data["top"][i] for i in indexes)
        right = max(data["left"][i] + data["width"][i] for i in indexes)
        bottom = max(data["top"][i] + data["height"][i] for i in indexes)
        result.append(
            SourceBlock(
                id=f"{source_id}:page:{page}:ocr:{index}",
                source_id=source_id,
                text=" ".join(data["text"][i] for i in indexes),
                kind="ocr",
                quality=max(0, min(confidence, 0.95)),
                locator={
                    "type": "pdf_page",
                    "page": page,
                    "bbox": [float(left), float(top), float(right), float(bottom)],
                    "coordinate_space": "pixels",
                    "image_width": image.width,
                    "image_height": image.height,
                },
            )
        )
    return result
