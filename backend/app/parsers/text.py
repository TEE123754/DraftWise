from app.domain.errors import DomainError
from app.domain.models import SourceBlock


def parse_text(data: bytes, source_id: str) -> tuple[list[SourceBlock], list[str]]:
    if b"\x00" in data:
        raise DomainError(
            "FILE_UNSUPPORTED", "Binary content is not supported as plain text", status=415
        )
    text = data.decode("utf-8-sig", errors="replace")
    replacements = text.count("\ufffd")
    warnings = ["Text contains undecodable bytes; verify the original"] if replacements else []
    quality = 0.49 if replacements else 1.0
    blocks, offset = [], 0
    for index, line in enumerate(text.splitlines(keepends=True), 1):
        if line.strip():
            blocks.append(
                SourceBlock(
                    id=f"{source_id}:line:{index}",
                    source_id=source_id,
                    text=line.rstrip("\r\n"),
                    locator={
                        "type": "text",
                        "line": index,
                        "start": offset,
                        "end": offset + len(line),
                    },
                    quality=quality,
                )
            )
        offset += len(line)
    return blocks, warnings
