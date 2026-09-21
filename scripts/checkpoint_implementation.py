"""Refresh the implementation inventory without declaring untested features complete."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATED = {
    "backend/app/config.py", "backend/pyproject.toml", "backend/uv.lock",
    "backend/app/services/revision_analysis.py", "backend/app/services/amendment_drafts.py",
    "backend/app/benchmark/export.py", "backend/tests/unit/test_revision_analysis.py",
    "backend/tests/unit/test_correction_previews.py", "frontend/package.json", "frontend/pnpm-lock.yaml",
    "frontend/app/layout.tsx", "frontend/app/dashboard/page.tsx",
    "frontend/app/cases/[caseId]/page.tsx", "frontend/app/completed/page.tsx",
    "frontend/components/cases/evidence-viewer.tsx", "frontend/components/cases/correction-preview.tsx",
    "frontend/components/cases/next-action-card.tsx", "frontend/components/cases/returned-draft-summary.tsx",
    "frontend/components/cases/amendment-timeline.tsx", "frontend/tests/amendment-regression.spec.ts",
    "frontend/tests/accessibility.spec.ts",
}
EXCLUDE = {".venv", "node_modules", ".next", ".next-test", "__pycache__", ".pytest_cache", ".ruff_cache", "test-results", "playwright-report"}


def main():
    path = ROOT / "repository.manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["delivery_status"] = "implementation_in_progress"
    manifest["application_status"] = "partially_implemented"
    for module in manifest["planned_modules"]:
        exists = (ROOT / module["path"]).is_file()
        module["status"] = "implemented" if exists and module["path"] in VALIDATED else ("partial" if exists else "planned")
    for document in ("docs/LOCAL_SETUP.md", "docs/LOCAL_PIPELINE.md", "docs/IMPLEMENTATION_STATUS.md", "docs/DRAFTWISE_EXPANSION_PLAN.md", "docs/USE_CASE_TRACEABILITY.md", "docs/BRAND_AND_SITE_PLAN.md"):
        if document not in manifest["artifacts"]:
            manifest["artifacts"].append(document)
    known = set(manifest["artifacts"]) | {module["path"] for module in manifest["planned_modules"]}
    files = []
    for folder in ("backend", "frontend", "docker", "database/migrations", "scripts", ".github/workflows"):
        for file in (ROOT / folder).rglob("*"):
            name = file.relative_to(ROOT).as_posix()
            if not file.is_file() or any(part in EXCLUDE for part in file.parts) or name in known:
                continue
            if file.name.startswith(".env") and file.name != ".env.example":
                continue
            if file.suffix in {".pyc", ".tsbuildinfo", ".log"}:
                continue
            files.append(name)
    manifest["implementation_artifacts"] = sorted(files + [".dockerignore", "tools/postgres/package.json", "tools/postgres/package-lock.json", "tools/postgres/run-tests.mjs"])
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    counts = {state: sum(module["status"] == state for module in manifest["planned_modules"]) for state in ("implemented", "partial", "planned")}
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
