import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

from app.ai.grounding import ground_extraction
from app.benchmark.export import export_prediction
from app.config import Settings
from app.domain.errors import DomainError
from app.infrastructure.parsing import parse_bounded
from app.services.extraction import extract_labelled
from app.services.verification import verify


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify local shipping instructions against a draft BL"
    )
    parser.add_argument("--si", required=True, type=Path)
    parser.add_argument("--bl", required=True, type=Path)
    parser.add_argument("--email-id", default="local")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        settings = Settings()
        documents = [
            parse_bounded(path.read_bytes(), str(uuid4()), settings) for path in (args.si, args.bl)
        ]
        si, bl = [extract_labelled(document) for document in documents]
        qualities = ground_extraction(si, documents[0]) | ground_extraction(bl, documents[1])
        report = verify(si, bl, email_id=args.email_id, evidence_quality=qualities)
        payload = {
            "report": report.model_dump(mode="json"),
            "submission": {
                args.email_id: export_prediction("BL_COMPARISON", report).model_dump(mode="json")
            },
            "extractions": [item.model_dump(mode="json") for item in (si, bl)],
            "sources": [item.model_dump(mode="json") for item in documents],
        }
        output = json.dumps(payload, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output + "\n", encoding="utf-8")
            print(f"{report.status}: report saved to {args.output}")
        else:
            print(output)
        return 0
    except (DomainError, OSError) as exc:
        print(
            json.dumps({"error": getattr(exc, "code", "FILE_ERROR"), "message": str(exc)}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
