"""Validate delivered specification artifacts without network access or secrets.

This deliberately validates the JSON Schema subset used in this repository.
It is not a substitute for a full schema validator or running Supabase migrations.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from urllib.parse import unquote
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "shipper", "consignee", "notify_party", "port_of_loading",
    "port_of_discharge", "container_count", "gross_weight_kg",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        require(key not in value, f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def read_json(path: Path):
    def reject_constant(value: str):
        raise ValueError(f"Non-finite JSON constant: {value}")
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=unique_keys, parse_constant=reject_constant)


def validate(value, spec: dict, root: dict, location: str = "$") -> None:
    if "$ref" in spec:
        require(spec["$ref"].startswith("#/"), "Only local schema refs supported")
        target = root
        for part in spec["$ref"][2:].split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        validate(value, target, root, location)
        return
    if "const" in spec:
        require(value == spec["const"], f"{location}: const mismatch")
    if "enum" in spec:
        require(value in spec["enum"], f"{location}: enum mismatch")
    if "type" in spec:
        kinds = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
        matches = {
            "null": value is None,
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "boolean": isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        }
        require(any(matches[kind] for kind in kinds), f"{location}: wrong type")
    if isinstance(value, dict):
        require(set(spec.get("required", [])) <= value.keys(), f"{location}: missing keys")
        properties = spec.get("properties", {})
        for key, item in value.items():
            if key in properties:
                validate(item, properties[key], root, f"{location}.{key}")
            elif spec.get("additionalProperties") is False:
                raise ValueError(f"{location}: unexpected {key}")
            elif isinstance(spec.get("additionalProperties"), dict):
                validate(item, spec["additionalProperties"], root, f"{location}.{key}")
    if isinstance(value, list):
        require(spec.get("minItems", 0) <= len(value) <= spec.get("maxItems", float("inf")),
                f"{location}: array length")
        if spec.get("uniqueItems"):
            require(len({json.dumps(x, sort_keys=True) for x in value}) == len(value),
                    f"{location}: duplicate array items")
        for index, item in enumerate(value):
            validate(item, spec.get("items", {}), root, f"{location}[{index}]")
    if isinstance(value, str):
        require(spec.get("minLength", 0) <= len(value) <= spec.get("maxLength", float("inf")),
                f"{location}: string length")
        if "pattern" in spec:
            require(re.search(spec["pattern"], value) is not None, f"{location}: pattern")
        if spec.get("format") == "uuid":
            UUID(value)
        if spec.get("format") == "date-time":
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            require(parsed.tzinfo is not None, f"{location}: timezone missing")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        require(spec.get("minimum", float("-inf")) <= value <= spec.get("maximum", float("inf")),
                f"{location}: numeric bounds")


def main() -> None:
    manifest = read_json(ROOT / "repository.manifest.json")
    artifacts = manifest["artifacts"]
    require(len(set(artifacts)) == len(artifacts), "Duplicate manifest path")
    for name in artifacts:
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT), f"Path outside repository: {name}")
        require(path.is_file(), f"Missing artifact: {name}")
        require("ground_truth" not in name and not name.startswith("tmp/"), f"Private artifact: {name}")
        if path.suffix == ".json":
            read_json(path)
    planned = [x["path"] for x in manifest["planned_modules"]]
    require(len(set(planned)) == len(planned), "Duplicate planned module")
    require(not (set(planned) & set(artifacts)), "Implemented/planned ambiguity")
    for module in manifest["planned_modules"]:
        require(module["status"] in {"planned", "partial", "implemented"}, "Unknown module status")
        if module["status"] != "planned":
            require((ROOT / module["path"]).is_file(), f"Missing implementation: {module['path']}")
    for name in manifest.get("implementation_artifacts", []):
        path = (ROOT / name).resolve()
        require(path.is_relative_to(ROOT) and path.is_file(), f"Missing implementation artifact: {name}")
        require("ground_truth" not in name and not name.startswith("tmp/"), f"Private artifact: {name}")

    links = 0
    for name in artifacts:
        if not name.endswith(".md"):
            continue
        path = ROOT / name
        text = path.read_text(encoding="utf-8")
        require(len(re.findall(r"^```", text, re.M)) % 2 == 0, f"Unbalanced fences: {name}")
        text = re.sub(r"(?ms)^```.*?^```", "", text)
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            target = target.strip("<>").split("#")[0]
            if not target or re.match(r"^[a-z]+:", target, re.I):
                continue
            require((path.parent / unquote(target)).exists(), f"Broken link {name}: {target}")
            links += 1

    example_count = 0
    for example in sorted((ROOT / "shared/examples").glob("*.json")):
        spec = read_json(ROOT / "shared/schemas" / f"{example.stem}.schema.json")
        validate(read_json(example), spec, spec)
        example_count += 1
    report = read_json(ROOT / "shared/examples/verification.json")
    require({x["field"] for x in report["comparisons"]} == FIELDS, "Report field coverage")
    require(report["status"] == "MISMATCH" and report["complete"], "Report state")
    require(any(x["decision"] == "mismatch" for x in report["comparisons"]), "Missing defect")
    preview = read_json(ROOT / "shared/examples/correction-preview.json")
    require(preview["remaining_blocker_count"] == len(preview["remaining_fields"]), "Preview blocker count")
    require(len({x["field"] for x in preview["changes"]}) == len(preview["changes"]), "Duplicate preview fields")
    summary = read_json(ROOT / "shared/examples/revision-summary.json")
    require({x["field"] for x in summary["fields"]} == FIELDS, "Revision field coverage")
    require(next(x for x in summary["fields"] if x["field"] == "consignee")["change"] == "fixed", "Fix example")
    require(next(x for x in summary["fields"] if x["field"] == "gross_weight_kg")["change"] == "regressed", "Regression example")

    sql = (ROOT / "database/schema.sql").read_text(encoding="utf-8")
    extension = (ROOT / "database/amendment_workspace.sql").read_text(encoding="utf-8").strip()
    require(extension in sql, "Fresh schema is missing upgrade extension")
    tables = re.findall(r"create table public\.(\w+)", sql, re.I)
    require(len(tables) == len(set(tables)), "Duplicate SQL table")
    for table in tables:
        require(f"'{table}'" in sql or f"alter table public.{table} enable row level security" in sql,
                f"Table missing RLS setup: {table}")
    require("needs_decision" in sql and "correction_previews" in tables, "Missing amendment schema")

    print(f"PASS: {len(artifacts)} specification artifacts; {len(planned)} tracked modules; {links} local links.")
    print(f"PASS: {example_count} schema examples and cross-field example invariants.")
    print(f"PASS: {len(tables)} unique SQL tables with tenant-policy inventory and extension parity.")
    print("Scope: specification checks only; PostgreSQL and application runtime not executed.")


if __name__ == "__main__":
    main()
