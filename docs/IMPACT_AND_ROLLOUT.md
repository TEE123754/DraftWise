# Impact, Success Measures and Rollout

This page says who DraftWise is for, what "it worked" would mean in numbers, how each number is collected, and how a real team would adopt it. It separates **measured results** (with their source and caveats) from **targets** and **hypotheses**, so nothing here should be read as a claim of proven time savings.

## Who it is for

Documentation and operations teams at freight forwarders, NVOCCs and exporters who receive Shipping Instructions (SI) and carrier draft Bills of Lading (BL) by email and must confirm the two agree **before the BL is finalised**. Each disagreement caught early avoids an amendment, a demurrage or vessel-cut-off risk, and a customer conversation. The buyer is the documentation manager; the daily user is the documentation officer.

## What is measured today, and what is not

| Measure | Result | Source | Caveat |
|---|---|---|---|
| Comparison defects caught | 46 of 46, exact field | Organizer scorer, 520-email sample, offline | Sample only; classifier phrase lists were written from this dataset's wording |
| Review escalation precision | 20 sent, 20 needed | Same run | Same caveat |
| Unsupported "all clear" | None: an exhaustive invariant test forbids a green result unless all seven fields matched | Backend unit tests | Covers the seven fields only |
| Email classification without a model | 48 % on 60 independent emails, 0 confidently wrong (abstains) | Held-out set | Small set; fixes were later derived from its failures |
| Email classification with the model | 95 % on the same 60 | Held-out set | Small set; live provider quality run still open |
| Processing cost | 520 emails in 6.7 s, zero provider calls, on rules alone | `scripts/benchmark.py` | Local run, no network model calls |
| Reviewer time saved | **Not measured** | | A hypothesis; see the pilot below |

## Success measures for a pilot

Each measure has a definition, where the number comes from, and a target that a pilot must beat for the product to be worth adopting. Targets are set by us as go / no-go thresholds; they are not results.

| # | Measure | Definition | Data source | Pilot target |
|---|---|---|---|---|
| 1 | **Defect recall** | Real discrepancies flagged, divided by real discrepancies present, on drafts the team has already reviewed by hand | Reviewer-labelled shadow-mode drafts | at least 95 % |
| 2 | **False-alarm rate** | Clean drafts flagged `MISMATCH`, divided by clean drafts | Same set | at most 2 % |
| 3 | **Honest escalation** | Of drafts sent to `NEEDS_REVIEW`, the share where a person really was needed | Reviewer's confirm / correct / dismiss action, already recorded with actor and reason | at least 80 % |
| 4 | **Time to first decision** | Median and 95th-percentile time from an email arriving to it holding a state (`Checked`, `Mismatch found`, `Needs review`, …) | `emails.created_at` to the first report or review row | median under 2 min, p95 under 10 min |
| 5 | **Reviewer minutes per draft** | Time-and-motion study: the same reviewers on comparable drafts, manual versus DraftWise | Timed pilot sessions | at least 50 % lower (the central hypothesis) |
| 6 | **Regression catch** | Fields that were right in draft *n* and wrong in draft *n+1*, flagged as `regressed` | Amendment-round analysis, already stored | 100 % of seeded regressions |
| 7 | **AI cost per 100 emails** | Provider calls times unit cost, divided by emails | The per-workspace AI call counter (`AI usage`) | under a stated ceiling agreed with the customer |
| 8 | **Adoption** | Weekly active reviewers, and the share of checked emails opened through the next-action card | Audit log for reviewer activity; click-through on the next-action card needs a small event added | rising for three consecutive weeks |

Measures 1–3 and 6 use data DraftWise already stores. Measure 4 needs a small reporting query and measure 8 a small event. Measure 5 needs a pilot.

## Rollout path

1. **Shadow mode (2 weeks).** Point DraftWise at a copy of a real mailbox and let reviewers work as usual. Compare its result with theirs. Gate: measures 1–3 meet target and no false "all clear" appears. No workflow change, no risk.
2. **Assisted mode (one team, 4 weeks).** Reviewers start from DraftWise's evidence view and correction preview. Collect measures 4–5 against the shadow-mode baseline. Gate: measure 5 shows a clear reduction.
3. **Connected mailbox.** Finish Gmail incremental sync (the OAuth connection and encrypted tokens exist; the mail fetch does not), then add Microsoft 365. Nothing is ever sent for the user: exports say *Copied*, not *Sent*.
4. **Team knowledge.** Customer-scoped, human-approved equivalence rules let a team teach DraftWise its own aliases with an impact preview and one-click revocation, without retraining a model.

## Growth beyond this pair of documents

The evidence-grounded seven-field pattern generalises: commercial invoice against packing list, packing list against BL, letter-of-credit terms against documents. Each is a new field set plus label aliases on the same parser, grounding, comparison and review machinery.

## Commercial shape (hypothesis)

Per-workspace subscription with a monthly allowance of AI-assisted reviews, because rules do most of the work and AI is the metered part. The public pricing page states the plan structure; the numbers are placeholders until the pilot yields measure 5 and measure 7.

## Risks and how they are handled

| Risk | Mitigation |
|---|---|
| Customer documents are confidential | Private storage, per-workspace row-level security, no anonymous paid AI, demo data kept apart from real workspaces |
| Carriers use formats the rules do not know | Rules abstain instead of guessing; abstentions go to the model, then to a person; every correction becomes a candidate rule a supervisor can approve |
| A wrong "all clear" | Invariant-tested: green appears only when all seven fields are supported matches; "Checked" is stated to cover the seven fields only |
| Model cost or outage | Content-hash cache, per-workspace budget, fallback to rules, visible retry states |
| Over-trusting a small benchmark | The sample score and the weaker held-out score are published together, with the limits |

## Next 30 / 60 / 90 days

- **30:** shadow-mode pilot with one design partner; time-to-decision report; fresh held-out set with new wording; live provider quality run.
- **60:** Gmail sync and per-visitor demo limits; sign-in, upload and AI endpoint rate limits; assisted-mode pilot.
- **90:** Microsoft 365 intake; second document pair; decision on pricing from measures 5 and 7.
