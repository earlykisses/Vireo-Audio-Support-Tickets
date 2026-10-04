# Vireo Audio Support Analytics --- Brainstorming Notes

**Version:** 0.1\
**Status:** Discovery hypotheses; not final findings

## 1. Problem framing

Arjun needs monthly refund totals by reason code and resolving agent
that reconcile to a defensible total. The tool should explain
data-quality issues before presenting agent comparisons.

The brief and email thread point to four concrete investigation
paths: 1. Legacy Freshdesk monetary values may use a different native
unit from current helpdesk rupees. 2. A subset of legacy tickets may
have been re-imported and appear under both source systems. 3. GW-OTHER
is the first dropdown option and may be over-selected. 4. Refunds and
replacements may both have been issued for the same order.

The operating policy adds constraints: goodwill credits are capped at
₹500 per ticket and require Team Lead approval; refunds and replacements
must not both be issued for the same order; Returns Desk handles most
refunds by design; Tier 2 agents must not be compared with Tier 1 on
volume metrics.

## 2. Initial data observations

A first pass over the provided CSVs found: - `tickets.csv`: 12,238 rows
and 21 columns. - `agents.csv`: 44 roster assignments, not necessarily
44 unique people/records by design. - `orders.csv`: 15,000 rows;
`products.csv`: 14 rows; `customers.csv`: 9,500 rows. - 638 repeated
`ticket_id` values in the raw ticket export. - 2,465 rows with a
nonblank refund amount. - Current helpdesk refund-field sum:
₹4,817,881. - Legacy Freshdesk refund-field sum as exported:
₹225,306,200, with a median value of ₹224,900 versus ₹2,499 in current
helpdesk rows.

**Interpretation:** The magnitude difference is a strong signal of a
legacy-unit issue, but it is not enough by itself to authorize a
conversion factor. Validate against policy language, order values,
amount distributions and duplicate handling before finalizing the
normalization rule. These raw sums are not a reconciled financial
result.

## 3. Hypotheses to test

  -----------------------------------------------------------------------
  Hypothesis              Test                    Guardrail
  ----------------------- ----------------------- -----------------------
  Legacy amounts are      Compare amounts and     Do not apply a
  stored in paise or      distributions against   conversion silently;
  another minor unit      order values and        record rule and
                          current rows; inspect   evidence
                          policy §9               

  Re-import duplicates    Detect same ticket ID   Preserve raw rows;
  inflate counts/sums     across source systems   create an auditable
                          and compare key fields  canonical row decision

  GW-OTHER is overused    Compare code with       Text classification is
                          message/note signals    a review aid, not a
                          and human-labelled      final adjudication
                          sample                  

  Refunds overlap with    Flag ticket/order       A flag is an exception,
  replacement issuance    overlaps and validate   not proof of misconduct
                          flags/order joins       

  Some refunds breach     Check amount caps,      Missing approval data
  policy                  eligible                means "cannot verify",
                          reason/date/order       not "violation
                          facts, and approval     confirmed"
                          evidence if present     

  Refund growth reflects  Monthly totals, volume, Correlation is not
  a service-policy change contact mix, CSAT and   causation; account for
                          survey response rates   Q4 policy change
                                                  mentioned by CX

  Certain agents are      Normalize by comparable Do not rank agents on
  outliers                role, team, channel,    raw refund total alone
                          workload and active     
                          roster dates            
  -----------------------------------------------------------------------

## 4. Open-source stack shortlist

-   **Python + pandas:** straightforward CSV cleaning, joins,
    aggregation and testable transformations.
-   **Streamlit (Apache-2.0):** small interactive local web app;
    suitable for filters, tables and CSV downloads.
-   **DuckDB (MIT):** optional SQL analytics layer; can query CSV
    directly. For this small dataset, pandas alone may be sufficient and
    simpler.
-   **RapidFuzz (MIT):** optional candidate matching for migration
    duplicates when IDs differ; fuzzy matches must be review candidates,
    not auto-deletes.
-   **scikit-learn TF-IDF:** optional interpretable baseline for text
    signals. Prefer explicit rules + human review under the time cap
    over an unvalidated black-box model.

References: - Streamlit GitHub: https://github.com/streamlit/streamlit -
DuckDB Python docs:
https://duckdb.org/docs/stable/clients/python/overview - RapidFuzz
GitHub: https://github.com/rapidfuzz/RapidFuzz - scikit-learn TF-IDF
docs:
https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html

## 5. Scope decision

Build a local, deterministic analytics app first. Keep money
normalization, duplicate rules, and text-derived reason suggestions
transparent and configurable. Do not send customer text to external APIs
by default. Do not attempt a production deployment, automated agent
discipline recommendations, or a fully autonomous refund adjudicator in
this time-boxed exercise.

## 6. Decisions to document

1.  Canonical ticket definition and duplicate resolution.
2.  Legacy money conversion and confidence/evidence.
3.  Treatment of blank amounts, zero values, open tickets and
    auto-closed tickets.
4.  Which date drives monthly reporting (proposed: refund/ticket event
    date if available; otherwise explicitly label use of created_at as a
    proxy).
5.  Agent attribution (resolving `agent_id`, not first assigned team).
6.  Human review and sampling method for text classification.
7.  Financial goal only after baseline and preventable leakage are
    validated.
