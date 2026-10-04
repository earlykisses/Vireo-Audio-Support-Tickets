# Screen recording script (target: 2 minutes 40 seconds; no slides)

## 0:00-0:20 — Show the tool and scope

“Here is the local Vireo refund reconciliation tool. It starts from the bundled CSVs, makes no external AI API calls, and separates financial normalization from the text model.”

## 0:20-0:55 — Reconciliation

Open **Overview & reconciliation**. Point out the 12,238 raw rows, 11,600 canonical tickets, 638 repeated IDs, ₹70.71 lakh normalized pre-dedup total and ₹67.10 lakh canonical total. State the key rule: legacy amounts are divided by 100 because 125 duplicated refund pairs exactly match the current-system amounts after conversion, and order-value checks support that scale. Show the source-level reconciliation table.

## 0:55-1:25 — Monthly tables and reason/agent outputs

Open **Monthly board tables**. Filter to one month, then show both reason and resolving-agent summaries. Explain that `created_at` is a proxy because the export has no refund posting timestamp. Show a CSV download. Do not call the largest total “the worst agent”; mention Returns Desk concentration and Tier 2 comparability guardrails.

## 1:25-1:55 — Exceptions

Open **Exceptions & QA**. Show the 166 same-ticket refund-plus-replacement flags and the separate order-level queue (294 matched order IDs; ₹10.19 lakh on 327 refund tickets). Then show the duplicate audit. Explain these are review candidates, not booked loss, until order/fulfillment evidence confirms the case. Mention that GW-OTHER over ₹500 is a review cue, not an automatic cap breach.

## 1:55-2:25 — AI model

Open **AI reason assistant**. Show held-out accuracy and macro-F1 and the weaker per-class results. Paste an anonymized example about a duplicate payment and request a suggestion. Explain that the model is trained on the existing dropdown labels, which can be noisy; it never changes codes automatically.

## 2:25-2:40 — Decisions and what was discarded

“Version one considered direct automatic recoding and fuzzy deletion of migration duplicates. I discarded both: the model has only about 58% held-out accuracy, and fuzzy matching could delete real tickets. I used deterministic rules, an auditable duplicate register and manual-review flags instead. The next step is to validate the flagged double-remedy tickets with Operations.”

## Prompt/change log for honest disclosure

- Initial reasoning prompt: “Start with SRS, SDD, brainstorming and likely failure modes; use the supplied email and policy rather than assumptions.”
- Build prompt: “Implement a local tool that reconciles money, deduplicates tickets, reports monthly by reason and resolving agent, and exposes QA evidence.”
- Iteration 1: Raw sums exposed a large legacy/current scale mismatch; replaced a generic cleaning plan with a configurable legacy divisor and explicit raw/normalized/canonical totals.
- Iteration 2: Duplicate inspection showed cross-system pairs matching after division by 100; prefer the current helpdesk record for the same ticket ID and record all discarded rows.
- Iteration 3: Initial rule-only reason inference was too brittle as a proposed “AI” feature; tested a local TF-IDF/logistic-regression model and exposed its measured holdout performance instead of claiming the model was accurate.
- Discarded: automatic code rewrites, automatic duplicate deletion by fuzzy match, a raw “worst agent” leaderboard, any external paid API call, and claims of confirmed savings from unreviewed flags.
