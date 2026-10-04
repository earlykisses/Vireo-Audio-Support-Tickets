# Software Design Description (SDD)

**Project:** Vireo Audio — Refund Reconciliation & Review  
**Version:** 1.0 · **Status:** Working proof of concept

## 1. Architecture

The app is a local Python workflow:

`source CSVs → schema checks → amount normalization → duplicate audit and canonicalization → order/product/customer/roster enrichment → policy and text-review flags → monthly summaries → Streamlit UI / CSV exports`

**Stack:** Python 3.11 recommended, pandas, Streamlit, scikit-learn, pytest. The text model is TF-IDF + logistic regression. There is no paid model API, cloud dependency or database requirement.

## 2. Repository layout

```text
vireo-refund-analytics/
├── README.md
├── requirements.txt
├── app.py
├── data/raw/                 # source data pack
├── src/
│   ├── analytics.py          # transformations, reconciliation and flags
│   └── modeling.py           # local text classifier and holdout evaluation
├── scripts/export_reports.py # reproducible CSV exporter
├── tests/                    # regression and model-evaluation checks
├── outputs/latest/           # generated CSVs
└── docs/                     # SRS, SDD, brainstorm, memo, form, recording script
```

## 3. Canonical data processing

1. **Load and validate:** Read five CSVs and check expected columns.
2. **Normalize money:** Add `refund_amount_raw`, `refund_amount_normalized_inr`, and `normalization_rule`. Current `helpdesk` values are retained as rupees; `legacy_fd` amounts are divided by a configurable factor, default 100. Raw values are not overwritten.
3. **Audit duplicates:** Group repeated `ticket_id` values. Compare non-amount fields using null-safe equality and record source systems, selected row, duplicate amount impact and any field conflicts.
4. **Canonicalize:** Keep one ticket row per `ticket_id`, preferring the current helpdesk row where the ID appears in both systems. The duplicate audit retains the dropped row context. Fuzzy matches are not automatically merged or deleted.
5. **Resolve roster:** Match `agent_id` to the assignment active at `created_at`. Unmatched dates/IDs are surfaced.
6. **Join reference data:** Match by `order_id`; where blank, use customer + SKU only if unique. Ambiguous and post-ticket-date fallback matches are surfaced. Enrich product/customer attributes without multiplying ticket rows.
7. **Build policy flags:** Identify refund + replacement on the same ticket, GW-OTHER values above ₹500, refund values over matched order value, unknown reason codes, text/code mismatch candidates, unmatched agents, and unresolved order joins. Flags are review cues rather than determinations of misconduct or confirmed leakage.
8. **Aggregate:** Calculate monthly refund sums and counts by agent-selected reason and resolving agent.
9. **Export:** The app offers CSV downloads; the CLI writes summary, canonical positive-refund detail (without customer free text), reconciliation, duplicate, exception, quality, quarterly trend, SLA breach and model-evaluation tables under `outputs/latest/`.

## 4. Data fields of interest

Canonical rows retain source identifiers and raw values plus:

- `refund_amount_normalized_inr`, `normalization_rule`, `refund_amount_positive`
- `refund_month` derived from ticket `created_at`
- time-valid `agent_name`, `agent_team`, `agent_tier`, `agent_site`, `agent_shift`, `roster_match_status`
- `matched_order_id`, `matched_order_value_inr`, `matched_order_unit_cost_inr`, `order_match_status`
- `duplicate_status` and exception flags
- `text_rule_suggestion`, `text_rule_evidence`, and flags for candidate mismatches

`created_at` is used as the monthly proxy because the export has no refund-event timestamp. The output must not be described as finance-ledger cash-posting month.

## 5. Local text model

- Input: concatenated customer opening message and agent closing note.
- Target: the agent-selected `refund_reason_code`; this is an imperfect/noisy label, not independently verified truth.
- Pipeline: word unigram/bigram TF-IDF followed by logistic regression (`class_weight=balanced`, fixed `random_state=42`).
- Evaluation: stratified 75/25 train/test split. Show accuracy, macro F1, per-class report and holdout mistakes.
- Observed held-out performance on this pack: 58.3% exact-match accuracy and 0.592 macro F1 on 585 held-out refund tickets.
- Safety control: suggestions do not overwrite selected codes, automate customer decisions or trigger agent discipline. Model scores are not calibrated probabilities.

## 6. UI structure

The Streamlit UI uses six tabs:

- **Overview & reconciliation:** source system bridge, pre/post dedup totals, canonical total, monthly trend and total by reason.
- **Monthly board tables:** filters and CSV downloads for monthly reason and agent summaries.
- **Agent investigation:** per-agent/tier/team context and refund incidence.
- **Exceptions & QA:** flags, duplicate audit, validation checks.
- **AI reason assistant:** model metrics, holdout results, and an anonymized-text prediction form.
- **Methods & limitations:** rule summary, downloadable outputs and caveats.

The app explicitly warns that Returns Desk is expected to handle most refunds and avoids comparing Tier 2 with Tier 1 on raw volume.

## 7. Reconciliation evidence

For the supplied pack and divisor 100:

- Raw rows: 12,238; unique canonical ticket IDs: 11,600.
- Repeated ticket IDs: 638; rows removed by canonical selection: 638.
- Normalized amount before deduplication: ₹70,70,943.
- Canonical positive-refund total: ₹67,09,932 from 2,340 tickets.
- Duplicate refund value removed: ₹3,61,011.
- In 125 duplicate groups where both records contain refund amounts, dividing the legacy amount by 100 makes it equal to the helpdesk value; amount/order-value comparisons support this scale.

These are derived from the supplied ticket export, not from a reconciled finance ledger. Finance should confirm the conversion rule before external reporting.

## 8. Testing

Run `python -m pytest -q`. Tests cover canonical row counts, duplicate audit fields, money normalization and reconciliation, exception counts, monthly totals and repeatable model evaluation. `scripts/export_reports.py` is also smoke-tested against the bundled input folder.

The model's holdout score measures agreement with agent-selected codes only. A human-reviewed sample against the actual reason stated in text is still a recommended next step. Do not present holdout agreement as accuracy against true root cause.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Wrong legacy factor | Make divisor configurable; retain raw values; validate against paired records and order values |
| Duplicate tickets not identical | Save group audit and conflict fields; prefer helpdesk row but require review of conflicts |
| No refund event date | Label monthly figures as `created_at` proxy |
| No approval audit | Mark goodwill cap cases as review candidates; approval is not inferable from supplied files |
| Noisy model labels | Holdout evaluation, per-class performance, human review recommended, suggestions not applied automatically |
| Misleading agent comparisons | Include team, tier, counts, incidence and CSAT; no “worst agent” claim |
| Personal data disclosure | Local processing; do not send customer text to an external model; minimize text in exports |

## 10. Run and export

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
streamlit run app.py
python -m pytest -q
python scripts/export_reports.py --data-dir data/raw --output-dir outputs/latest --legacy-divisor 100
```
