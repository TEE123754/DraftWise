"""Build a private, input-only manifest. Does not read labels or call an AI provider."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.dataset_import import build_manifest, open_source  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="Static archive, extracted dataset folder or loopback Docker URL")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = open_source(args.source)
    try:
        manifest = build_manifest(source)
    finally:
        source.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sha256": manifest["sha256"], **manifest["summary"]}))


if __name__ == "__main__":
    main()
