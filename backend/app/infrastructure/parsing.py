import multiprocessing

from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import ParsedDocument
from app.parsers.registry import parse_document


def _child(connection, data: bytes, source_id: str, settings: dict) -> None:
    try:
        result = parse_document(data, source_id, settings=Settings(**settings))
        connection.send((True, result.model_dump()))
    except DomainError as exc:
        connection.send((False, (exc.code, exc.message, exc.status)))
    except Exception:
        connection.send((False, ("FILE_CORRUPT", "Document could not be parsed", 422)))
    finally:
        connection.close()


# Starting a parser process re-imports the PDF, Office and OCR libraries and costs about a second
# per document, which is what bounds a worker's throughput on plain-text files. A small text file
# has no container format to attack and is parsed in one linear pass, so it is read in-process.
# Everything else, and any text file above this size, keeps the isolated, time-limited process.
IN_PROCESS_TEXT_LIMIT = 64 * 1024


def _is_small_plain_text(data: bytes) -> bool:
    return len(data) <= IN_PROCESS_TEXT_LIMIT and not data.startswith((b"%PDF-", b"PK"))


def parse_bounded(data: bytes, source_id: str, settings: Settings) -> ParsedDocument:
    if _is_small_plain_text(data):
        try:
            return parse_document(data, source_id, settings=settings)
        except DomainError:
            raise
        except Exception as exc:
            raise DomainError("FILE_CORRUPT", "Document could not be parsed") from exc
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    # Do not send provider or database secrets into a document parser.
    limits = settings.model_dump(
        include={
            "max_upload_bytes",
            "max_pdf_pages",
            "max_xlsx_cells",
            "parse_timeout_seconds",
            "ocr_languages",
        }
    )
    process = context.Process(target=_child, args=(child, data, source_id, limits), daemon=True)
    process.start()
    child.close()
    try:
        if not parent.poll(settings.parse_timeout_seconds):
            raise DomainError("FILE_TIMEOUT", "Document parsing exceeded its time limit")
        try:
            success, payload = parent.recv()
        except EOFError as exc:
            raise DomainError("FILE_CORRUPT", "Document parser exited unexpectedly") from exc
        if not success:
            raise DomainError(payload[0], payload[1], status=payload[2])
        return ParsedDocument.model_validate(payload)
    finally:
        parent.close()
        process.join(timeout=0.2)
        if process.is_alive():
            process.terminate()
            process.join(timeout=2)
        process.close()
