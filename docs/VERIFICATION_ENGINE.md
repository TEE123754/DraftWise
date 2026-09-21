# Verification engine

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Field normalization rules

| Field | Normalization | Comparison |
|---|---|---|
| Shipper, consignee, notify party | Unicode NFKC, casefold, whitespace/punctuation normalization; separate name/identity clauses from address evidence | Exact identity first; approved aliases second; fuzzy/semantic candidates require safeguards |
| Ports | Normalize names and country tokens; resolve versioned approved alias to UN/LOCODE when unambiguous | Same unambiguous canonical code = match; different confirmed codes = mismatch; missing country/ambiguous aliases = review |
| Container count | Parse explicit count or quantities in `3 x 40HC`, `2x20GP + 1x40HC`; deduplicate IDs only when table scope is complete | Integer equality; size/TEU/packages are never the count |
| Gross weight | Decimal parsing; KG unchanged; metric tonne/MT × 1000; lb × 0.45359237. A bare number takes the unit its own quoted label states (`Gross Weight (KGS)`), then the unit the other document states, then kilograms (the field's defined unit) only if the value is at least 1,000 | Exact normalized Decimal equality by default; ambiguous separators or gross/net scope = review |

Examples: `22,000 KG` equals `22 MT`; `22.000,50 kg` becomes `22000.50` only when separator context establishes that convention. Bare `22.000` is ambiguous without locale/format evidence. A bare `22` is never assumed to be kilograms and stays a review item, because it could be tonnes; a bare `341715` is read as kilograms and the report records the assumption in the rule name `decimal_unit_assumed_kg_v1`.

Unfilled form fields (`____MT`, `TBA`, `N/A`, "to be advised") are missing values, not values that can differ. A port printed as `NAME (UN/LOCODE)` is compared by its recognised name; a trailing code that disagrees with the name cannot hide a changed port. Preserve original scale/precision in normalization metadata. No blanket percentage tolerance: it could hide the dataset's 500–2000 kg changes. A future configurable rounding policy must be explicit, versioned, and displayed; baseline benchmark tolerance is zero after exact unit conversion.

Port aliases are curated, not guessed by an LLM. Seed only verified mappings such as approved local names/codes and record source/version. `PORT KLANG (WESTPORT), MALAYSIA` and `MYPKG` may resolve to the same configured code; `SINGAPORE` and another country-qualified location must not merge on string similarity. Preserve terminals as qualifiers and surface terminal changes separately when material.

`SAME AS CONSIGNEE` for notify party resolves only within that same document when its consignee is supported, and records a dependency edge. Never copy the SI consignee into the BL notify party. `ON BEHALF OF` remains part of party identity. Addresses are shown for review; the seven-field contract focuses on party identity, while contradictory address qualifiers can block automatic equivalence.

## 2 Decision ordering

1. Validate types, presence, source role and scope. If either side is unresolved, return `missing`/`uncertain`; two missing values are not a match.
2. Compare canonical exact values. Numeric/port contradictions are deterministic mismatches when evidence gates pass.
3. Apply an explicitly approved alias with provenance and version.
4. For parties only, compute RapidFuzz `ratio` and `token_sort_ratio` on normalized identity tokens. Set `processor=None` after explicit normalization. Never use token-set subset similarity alone to approve: `ABC Trading` and `ABC Trading Indonesia` can score deceptively well. [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz).
5. Initial score ≥ 97 plus no identity-token conflict is a candidate near-match, not unconditional acceptance. Scores 85–97 become partial matches; <85 with legible distinct names supports mismatch. Thresholds require development validation and do not override numeric identifiers/countries.
6. Use one structured semantic assessment only for unresolved identity aliases. An LLM's `equivalent` answer alone cannot approve an unregistered alias; use review or an independently established mapping. Different clear names do not need an LLM call.
7. Aggregate: any unresolved required field → `NEEDS_REVIEW`; otherwise any confirmed mismatch → `MISMATCH`; otherwise `OK`.

`partial_match` is a field state presented in the UI and resolved by review. It is not a sixth category or a new harness status. Known mismatches can coexist with unresolved fields as internal partial findings; harness export for `NEEDS_REVIEW` remains `has_defect=false`, `defect_fields=[]` because that is its contract.

## 3 Severity and confidence

Severity describes operational impact, not certainty. Default high severity: wrong shipper/consignee, loading/discharge port, container count or gross weight; medium: notify party; low: display-only formatting difference. A missing mandatory field is a high-priority readiness issue, not a proven mismatch. Shipment-specific severity rules may refine this but cannot suppress defect detection.

Field decision confidence is `min(si_evidence_quality, bl_evidence_quality, pairing_quality, rule_reliability)`, with a recorded vector of components. Initial rule reliability settings are exact=1, approved alias=0.98, unresolved fuzzy/semantic ≤0.79; they are policy scores, not calibrated probabilities. Reviewed decisions record reviewer identity and evidence instead of modifying the old score. Report confidence is the minimum over all seven decisions; completeness is reported separately as `resolved_fields/7`.

## 4 Discrepancy report JSON Schema

The `comparisons` array always contains exactly seven unique field names. It drives the complete diff viewer; rows with `mismatch`, `missing`, `partial_match`, or `uncertain` also populate the discrepancy index.

The authoritative JSON Schema is [shared/schemas/verification.schema.json](../shared/schemas/verification.schema.json).

Weights use canonical decimal strings in report JSON to avoid binary floating-point drift. Container counts use integers. Pydantic validators enforce unique field coverage and status/completeness rules; `NOT_APPLICABLE` is returned by the email resource, not instantiated as a seven-field verification report. A missing-source review report still has seven rows with null values and explicit uncertainty.

Explanations are deterministic templates, for example: `Container count differs: SI 3; BL 4. Both values are explicitly labelled.` Include normalization notes separately so formatting changes cannot be confused with business discrepancies.
