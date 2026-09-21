import hashlib
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import ParsedDocument
from app.parsers.docx import parse_docx
from app.parsers.pdf import parse_pdf
from app.parsers.text import parse_text
from app.parsers.xlsx import parse_xlsx


def parse_document(
    data: bytes, source_id: str, *, settings: Settings | None = None
) -> ParsedDocument:
    settings = settings or Settings()
    if not data:
        raise DomainError("FILE_EMPTY", "The uploaded file is empty")
    if len(data) > settings.max_upload_bytes:
        raise DomainError("FILE_LIMIT_EXCEEDED", "File exceeds the upload limit", status=413)
    try:
        if data.startswith(b"%PDF-"):
            format_name = "pdf"
            blocks, warnings = parse_pdf(
                data,
                source_id,
                max_pages=settings.max_pdf_pages,
                languages=settings.ocr_languages,
                timeout=settings.parse_timeout_seconds,
                settings=settings,
            )
        elif data.startswith(b"PK"):
            with ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                if (
                    len(entries) > 5000
                    or sum(item.file_size for item in entries) > 100 * 1024 * 1024
                ):
                    raise DomainError(
                        "FILE_LIMIT_EXCEEDED", "Expanded Office archive exceeds limits", status=413
                    )
                names = {item.filename for item in entries}
                if any("vbaproject" in name.lower() for name in names):
                    raise DomainError(
                        "FILE_UNSUPPORTED", "Macro-enabled documents are not supported", status=415
                    )
                if "word/document.xml" in names and "xl/workbook.xml" in names:
                    raise DomainError("FILE_UNSUPPORTED", "Ambiguous Office container", status=415)
                if "word/document.xml" in names:
                    format_name = "docx"
                    blocks, warnings = parse_docx(data, source_id, settings=settings)
                elif "xl/workbook.xml" in names:
                    format_name = "xlsx"
                    blocks, warnings = parse_xlsx(data, source_id, settings.max_xlsx_cells)
                else:
                    raise DomainError("FILE_UNSUPPORTED", "Archive is not DOCX or XLSX", status=415)
        else:
            format_name = "txt"
            blocks, warnings = parse_text(data, source_id)
    except DomainError:
        raise
    except (BadZipFile, ValueError, KeyError, OSError) as exc:
        raise DomainError("FILE_CORRUPT", "Document could not be parsed") from exc
    if not blocks:
        raise DomainError("EVIDENCE_INCOMPLETE", "No readable document content was found")
    return ParsedDocument(
        source_id=source_id,
        sha256=hashlib.sha256(data).hexdigest(),
        format=format_name,
        blocks=tuple(blocks),
        warnings=tuple(warnings[:30]),
    )
