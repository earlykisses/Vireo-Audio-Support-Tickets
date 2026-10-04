# Memo

**To:** Arjun Mehta, Finance Controller, Vireo Audio  
**From:** Support Analytics Review  
**Date:** 4 October 2026  
**Subject:** Refund reconciliation, reason mix and control opportunity

## Finding

The two exported totals differ mainly because the legacy Freshdesk money field is in a different unit and migrated tickets are repeated across systems. The supplied pack has 12,238 rows and 638 repeated ticket IDs. For all 638 repeated groups, the non-amount fields match. In the 125 repeated groups where both rows contain a refund amount, the helpdesk amount matches the legacy amount divided by 100. The current app therefore normalizes legacy amounts by 100, keeps the raw value for audit, and retains one row per ticket ID, preferring the current helpdesk row where available.

After those steps, **2,340 tickets carry a positive refund amount totalling ₹67,09,932 across the 18-month window**. That is an average of **₹11,18,322 per quarter**, close to IT’s approximate ₹11 lakh estimate. The raw, unnormalized combined export sum is ₹23.01 crore and should not be used as a financial total. Normalization before deduplication yields ₹70,70,943; the duplicate decision removes ₹3,61,011 of repeated refund value.

## What the data says

GW-OTHER is the largest bucket: **991 refund tickets and ₹29,07,036**, about 43% of normalized refund value. It deserves a reason-code quality review, but a high value under this broad code is not itself proof of misuse. Returns and refund processing is concentrated by design, so raw agent totals should not be treated as a misconduct ranking. Calendar-quarter refund incidence was 20.1% in Q1 2025 and 20.2% in Q4 2025, while ticket volume grew from 1,053 to 2,678. This means the higher aggregate amount alone does not demonstrate that an individual ticket was more likely to be refunded.

Refund value rose from **₹12.07 lakh in Q3 2025 (405 refund tickets) to ₹16.28 lakh in Q4 2025 (542 tickets)**, up 34.9%. But refund incidence fell from 22.0% to 20.2% as total ticket volume rose. CSAT averaged 3.478 and 3.507 respectively (about +0.03, not +0.4 for this comparison); Finance/CX should confirm the period and definition behind the email claim.

The clearest policy-control queue is refund plus replacement. **166 tickets** have a positive refund amount and `replacement_issued = Y`, with **₹5,74,191** attached to those same-ticket flags. Because policy is order-level, I also joined tickets using the explicit order ID or a unique customer + SKU fallback. That identifies **294 matched order IDs** where at least one positive-refund ticket and one replacement-issued ticket exist across the order’s tickets; 327 refund tickets on those orders total **₹10,19,405**. These are candidates, not confirmed loss: validate ticket/order identity and fulfillment records before booking a saving or attributing the case to an agent.

## Proposed measurable goal

Use **25% fewer confirmed order-level refund-plus-replacement exceptions** as the first control target, measured against an Operations-validated baseline. In this export, the 294 matched-order candidates average 49 orders per quarter across six quarters. The ₹10,19,405 associated refund value is a six-quarter pool (about ₹1,69,901 per quarter); if the entire pool is confirmed and preventable, a 25% reduction would represent about **₹42,475 per quarter**. This is a provisional opportunity estimate, not booked savings. Establish an audited baseline after Operations reviews the exception queue.

## Reporting and guardrails

Monthly tables use `created_at` because this export has no refund-event timestamp. They are ticket-creation-month views, not finance-ledger cash-posting months. Blank CSATs are excluded; the response rate is about 45%. A local text model predicts the agent-selected reason code with about 58% held-out accuracy and 0.59 macro-F1, so it should only prioritize human review. No code is changed automatically. SLA breach credits are reported separately from refunds.

**Recommended next step:** review the 166 double-remedy flags and a stratified sample of GW-OTHER tickets, validate fulfillment and reason codes, then set a confirmed leakage baseline before committing savings to the board.
