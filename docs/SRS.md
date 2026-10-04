# Software Requirements Specification (SRS)

## Vireo Audio Support Refund Analytics

**Version:** 0.1 \| **Status:** Draft for a time-boxed proof of concept

## 1. Purpose

Deliver a small, reproducible tool that reconciles support-ticket refund
data and produces a monthly board-pack-ready summary by refund reason
code and resolving agent, with explicit data-quality controls and
reviewable exceptions.

## 2. Business context

Finance reports refunds above ₹1 crore per quarter while the helpdesk
report is approximately ₹11 lakh per quarter. The email thread indicates
possible legacy monetary-unit differences, migration duplicates, and
potential refund-plus-replacement cases. CX also reports a Q4 policy
change intended to reduce customer arguments and says CSAT increased by
0.4. These statements are context to test, not assumed truths.

## 3. Users and needs

-   **Finance Controller:** monthly reconciled refund totals by reason
    and agent, traceable to source rows.
-   **Support Operations:** exception queues for duplicates, suspicious
    reason codes, goodwill caps, and refund/replacement overlap.
-   **CX leadership:** context on CSAT, channel mix, workload and
    changes over time.
-   **Reviewer/auditor:** reproducible calculations, stated assumptions,
    sample-based quality measurement and exportable evidence.

## 4. In-scope requirements

### Functional

-   **FR-01 Ingest:** Load `tickets.csv`, `agents.csv`, `orders.csv`,
    `customers.csv`, `products.csv`; validate required columns and
    report row counts.
-   **FR-02 Preserve raw data:** Never overwrite source files; retain
    raw amount and source-system columns in the analysis output.
-   **FR-03 Normalize:** Apply a documented, configurable legacy amount
    conversion only after validation. Show raw and normalized totals
    separately.
-   **FR-04 Deduplicate:** Identify exact ticket-ID duplicates and
    cross-system re-import candidates. Record which row is retained and
    why; do not silently delete ambiguous cases.
-   **FR-05 Reconcile:** Report raw totals, normalized totals, duplicate
    impact, unresolved rows and reconciliation checks.
-   **FR-06 Monthly reporting:** Show refund amount and count by month
    and reason code, and by month and resolving `agent_id`; allow CSV
    export.
-   **FR-07 Join references:** Join orders/products/customers and
    time-valid agent roster rows where keys and dates permit; expose
    unmatched joins.
-   **FR-08 Exception detection:** Flag potential refund + replacement,
    goodwill amount over ₹500, missing/unknown reason codes, suspicious
    code/text mismatch, and missing reference joins.
-   **FR-09 Text assistance:** Train and evaluate a local TF-IDF/logistic-regression
    reason-code suggestion model from customer message and agent notes.
    Preserve the original code and show held-out metrics. No automated
    code changes or disciplinary conclusions.
-   **FR-10 Fair comparisons:** Separate Tier 1 and Tier 2; display raw
    amounts alongside counts, rates and context. Avoid raw-total
    rankings as proof of agent misconduct.
-   **FR-11 Quality evidence:** Provide a validation report, rule-level
    test results, and a manually reviewable sample for text
    suggestions/duplicate candidates.
-   **FR-12 Board-pack output:** Export monthly summary tables and an
    exception register; show assumptions and limitations on the report.
-   **FR-13 Reproducibility:** One documented command starts the app on
    a clean Python environment.

### Non-functional

-   **NFR-01 Explainability:** Every adjustment must have a rule name,
    source fields and reason.
-   **NFR-02 Privacy:** Local-first processing; no external LLM/API
    calls or customer-text uploads by default.
-   **NFR-03 Reliability:** Deterministic outputs for the same inputs
    and configuration.
-   **NFR-04 Usability:** A non-technical finance user can select a
    period, inspect totals, drill into rows and export CSV.
-   **NFR-05 Performance:** Process the supplied 12k-row ticket export
    on a normal laptop without external infrastructure.
-   **NFR-06 Safe interpretation:** Flags indicate review needs, not
    fraud or misconduct.

## 5. Proposed business KPI

**Proposed KPI:** reduce confirmed refund-plus-replacement policy exceptions by 25% against an Operations-validated baseline. The supplied 18-month export flags 294 matched order IDs with at least one positive-refund ticket and one replacement-issued ticket across their linked tickets. There are 327 positive-refund tickets on those orders, carrying ₹10,19,405 in associated refund values. Averaged over six quarters, that is about ₹1,69,901 per quarter; a 25% reduction would equal about ₹42,475 per quarter **only if the entire flagged pool is confirmed and preventable**. This is a provisional exposure estimate, not booked savings. Exclude valid customer-choice refunds, expected warranty remedies and SLA credits from preventable leakage. The separate same-ticket flag is 166 tickets and ₹5,74,191 and overlaps with the order-level queue, so the figures must not be added together.

## 6. Acceptance criteria

1.  The app starts using the README instructions on a clean machine.
2.  Every reported total can be reproduced from an exported detail
    table.
3.  Raw, normalized and deduplicated totals are shown distinctly.
4.  Duplicate candidates are not silently discarded.
5.  All summary totals reconcile to the canonical detail table within ₹1
    rounding tolerance.
6.  Monthly summaries are available by reason and resolving agent.
7.  Policy exception flags include the supporting ticket/order IDs and
    rule.
8.  Agent comparisons include role/team context and do not compare Tier
    2 to Tier 1 on volume.
9.  Validation results include deterministic tests, a stratified holdout
    report and a reviewable list of model mistakes. Independent
    human-labeled validation remains a follow-up before production use.
10. Known limitations and assumptions appear in the memo and README.

## 7. Out of scope

-   Production integration with Vireo's helpdesk or finance ledger.
-   Automatic refunds, customer messaging or agent performance
    sanctions.
-   Definitive misconduct/fraud classification.
-   Causal attribution of refund changes to the Q4 CX policy.
-   Full multilingual semantic classification unless the supplied data
    proves it necessary and time remains.

## 8. Assumptions and open decisions

-   Monthly reporting period will be defined explicitly. The ticket
    export does not provide a dedicated refund timestamp; if no better
    event date is available, `created_at` is only a proxy and must be
    labelled.
-   The policy confirms a different legacy native unit but does not state the factor. The implemented default divisor of 100 is supported by 125 cross-system duplicate refund pairs and order-value plausibility; Finance should confirm it before ledger posting.
-   The roster has one row per assignment; agent team/tier must be
    resolved against the ticket date.
-   Team Lead approval evidence may not be included in the supplied
    pack; absent evidence is "not verifiable".
