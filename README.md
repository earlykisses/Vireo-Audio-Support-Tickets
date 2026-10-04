# Vireo Audio — Refund Reconciliation & Review

A small, local-first Streamlit application for reconciling the Set C support-ticket export, producing monthly refund summaries by reason code and resolving agent, and surfacing review candidates. It includes the original CSV pack, policy PDF, source code, tests, analysis notes, a finance memo and a short demo script.

## Quick start

**Requirements:** Python 3.11 recommended (Python 3.10+ should work with compatible dependency releases), a terminal, and internet access once to install Python packages. After installation, the app and model run locally; no API key is required.

### Windows PowerShell

```powershell
cd vireo-refund-analytics
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks virtual-environment activation, run the venv executables directly:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### macOS / Linux

```bash
cd vireo-refund-analytics
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit will print a local URL, normally `http://localhost:8501`. Open it in a browser.

## What is in the app?

- **Overview & reconciliation:** raw source amounts, normalized amounts, deduplication impact, canonical refund total, monthly trend and totals by reason.
- **Monthly board tables:** monthly refund amount and ticket count by dropdown reason and resolving agent; CSV downloads.
- **Agent investigation:** counts, amounts, refund incidence, CSAT and exception context, with team/tier filters. It does not label an agent as “worst”; Tier 2 is not compared with Tier 1 on raw volume.
- **Exceptions & QA:** refund-plus-replacement flags, GW-OTHER over ₹500 review cues, order-join issues, reason-text mismatch candidates, duplicate audit and validation checks.
- **AI reason assistant:** local TF-IDF + logistic-regression classification trained on existing dropdown labels, stratified 75/25 holdout evaluation, per-class metrics and a manual text suggestion form. It does not use an external API and never changes ticket reason codes automatically.
- **Methods & limitations:** important assumptions, CSV downloads and reporting caveats.

## Included data

`data/raw/` contains the five CSVs, `support-policy.pdf`, `README.txt`, and `email-thread.txt` from the supplied pack. The raw customer messages, notes and customer reference data may contain personal information. Keep this package local and do not upload it to public repositories or external AI services without authorization.

## Important analysis decisions

1. **Legacy money:** `legacy_fd` refund values are divided by 100 by default. In 125 repeated ticket groups where both rows contain a refund amount, the normalized legacy value equals the helpdesk value. Order-value comparisons support that scale. You can change the divisor in the left sidebar; raw amounts remain retained in analysis outputs.
2. **Duplicate ticket IDs:** 12,238 exported rows collapse to 11,600 unique `ticket_id` values. For repeated IDs, the current `helpdesk` row is preferred. The duplicate register records the discarded source row, amount impact and any non-amount field conflicts. No fuzzy-match auto-deletion is used.
3. **Monthly attribution:** the export has no explicit refund-event timestamp, so monthly views use `created_at` as a proxy. These are ticket-creation-month totals, not verified finance-ledger posting months.
4. **Reason codes:** the original agent-selected dropdown code remains the finance aggregation field. Model suggestions are review-only. The training labels are the same selected codes and may be noisy.
5. **Policy candidates:** `GW-OTHER` combines “Goodwill / Other”; amounts above ₹500 are review cues, not automatic breaches. Same-ticket and order-level refund-plus-replacement flags require confirmation against order and fulfilment records before classifying a case as leakage.
6. **Agent context:** `agent_id` refers to the resolving agent. Returns Desk processes most refunds by design, and Tier 2 work must not be compared with Tier 1 on ticket volume.

## Run tests

```bash
python -m pytest -q
```

Tests cover the real-data reconciliation, duplicate handling, legacy normalization evidence, monthly-total tie-out, and reproducible text-model evaluation.

## Export board-pack tables without opening the UI

```bash
python scripts/export_reports.py --data-dir data/raw --output-dir outputs/latest --legacy-divisor 100
```

The command exports monthly by-reason and by-agent tables, all-period reason totals, duplicate audit, exception register, source reconciliation, validation checks, baseline metrics, quarterly trends, SLA breach review and (unless `--skip-model` is used) local-model holdout metrics/audit. It also exports `canonical_refund_detail.csv`, a row-level positive-refund audit with raw/normalized amounts, source system, reason, agent context, and review flags. It intentionally excludes customer messages and agent notes. These rows reproduce the canonical summary total. Files under `outputs/latest/` can be regenerated at any time.

## Project files

```text
app.py                         Streamlit application
src/analytics.py               reconciliation, joins, exception flags and exports
src/modeling.py                local TF-IDF/logistic-regression model and evaluation
scripts/export_reports.py      command-line report exporter
data/raw/                      supplied data pack
outputs/latest/                reproducible summary, audit and detail CSVs
tests/                         pytest checks
docs/SRS.md                    requirements specification
docs/SDD.md                    design description
docs/brainstorm.md             discovery hypotheses and scope decisions
docs/verification-status.md     checks run and limitations of this environment
docs/memo-to-arjun.md          one-page business memo
docs/demo-recording-script.md  no-slides screen recording plan (script only; record video separately)
submission-form.md             best-effort form reconstructed from the brief
docs/submission-form.md        copy of the submission form
```

## Open-source references

- Streamlit install and quickstart: https://docs.streamlit.io/get-started/installation
- pandas user guide: https://pandas.pydata.org/docs/user_guide/
- scikit-learn TF-IDF documentation: https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html
- scikit-learn LogisticRegression documentation: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
- pytest getting started: https://pytest.org/en/latest/getting-started.html

## Verification status and limits

See `docs/verification-status.md` for the checks actually completed and the one incomplete check. The analytics pipeline and report exporter were run against the supplied files, the row-level detail reconciles to both monthly summaries, and the automated test suite passes. The Streamlit browser UI was not launched in the authoring environment because the package index was unreachable; run the setup steps above on a machine that can install dependencies before treating the UI smoke test as complete.

This is not a live integration with Vireo's finance ledger or fulfilment system. It cannot establish that a refund/replacement flag is a confirmed financial loss, verify Team Lead approvals that are not in the pack, or infer that an agent acted improperly. Do not use provisional exception amounts as booked savings before Operations and Finance validate them.
