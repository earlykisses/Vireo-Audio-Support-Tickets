# Submission form — Vireo Audio Support Tickets (Set C)

> **Template note:** An original `submission-form.md` file was not among the files available in the supplied pack. This is a completed best-effort form reconstructed from the brief. Replace it with the official form if a separate template is later provided.

## Project
**Name:** Vireo Refund Reconciliation & Review  
**Entry point:** `app.py`  
**Setup guide:** `README.md`  
**Architecture and requirements:** `docs/SDD.md`, `docs/SRS.md`

## Business goal
Reduce **confirmed refund-plus-replacement policy exceptions by 25%** versus an Operations-validated baseline. In the supplied 18-month export, 294 matched order IDs have a refund ticket and a replacement-issued ticket; 327 positive-refund tickets on these orders carry ₹10,19,405 in refund values. This averages ₹1,69,901 per quarter over six quarters; a 25% reduction could represent approximately **₹42,475 per quarter** if the full pool is confirmed and preventable. Separately, 166 same-ticket records carry ₹5,74,191. These are provisional exposure calculations, not booked savings; confirmation is required before claiming realization.

## What is delivered
- Local Streamlit app with source-level money reconciliation.
- Documented legacy amount conversion and duplicate-ticket audit.
- Monthly exports by reason code and resolving agent.
- Policy exception register and QA checks.
- Local AI reason-code suggestion model with held-out evaluation and manual-review workflow.
- Tests, raw input pack, setup documentation, business memo and 3-minute demo script.

## Evidence that it works
- 12,238 input rows canonicalize to 11,600 unique ticket IDs.
- 638 repeated ticket IDs are audited; 125 duplicated groups with refund amounts match after legacy `/100` normalization; all duplicate groups agree on non-amount fields.
- Canonical monthly reason totals sum to the same ₹67,09,932 as the canonical refund detail.
- Unit/regression tests run with `python -m pytest -q`.
- Text classifier evaluation uses a stratified 75/25 holdout with random state 42: roughly 58% accuracy and macro-F1 0.59. Per-class metrics are reported; low quality means suggestions stay human-reviewed.

## Key decisions and limitations
- Legacy amounts are divided by 100 based on cross-system duplicate pairs and order-value plausibility. Raw amounts are retained.
- Duplicate ticket IDs prefer the helpdesk row; conflicting fields would be queued for manual review. No fuzzy auto-deletion is used.
- Monthly reporting uses `created_at` as a proxy; the export has no refund-event timestamp.
- `GW-OTHER` amounts above ₹500 are review cues only, as approval evidence and credit-vs-refund semantics are not present in this pack.
- Refund-plus-replacement flags require Operations to verify fulfillment/order identity before treating them as actual loss.
- No agent is labelled as acting improperly. Agent amount totals are context-only; team mix and Returns Desk ownership matter, and Tier 2 is not compared with Tier 1 on raw volume.

## AI tools, costs and discarded work
- **Used:** ChatGPT as a coding/reasoning assistant; local Python, pandas, scikit-learn, Streamlit and pytest. The classifier is local and makes no API calls.
- **API spend:** ₹0 in this implementation because no paid model API was called. A separate ChatGPT subscription/plan cost is not observable from the project and is not claimed here.
- **Discarded:** automatic reason-code rewriting; fuzzy matching that silently deletes tickets; raw “worst agent” rankings; external model/API usage; claims that all flagged value is confirmed leakage.

## Deliverable checklist
- [x] Runnable tool and source code
- [x] Setup guide and dependency list
- [x] SRS, SDD and brainstorming notes
- [x] Monthly reporting and QA exports
- [x] Test suite and validation approach
- [x] One-page memo to Arjun Mehta
- [x] Short screen-recording script
- [x] Completed best-effort submission form (official template was not supplied)
