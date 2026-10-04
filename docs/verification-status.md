# Verification status

**Package state:** Proof-of-concept code and report outputs assembled on 4 October 2026.

## Checks completed

- `python -m py_compile app.py src/analytics.py src/modeling.py scripts/export_reports.py tests/test_analytics.py tests/test_model.py` completed successfully.
- `python -m pytest -q`: **6 passed**.
- `python scripts/export_reports.py --data-dir data/raw --output-dir outputs/latest --legacy-divisor 100` completed successfully.
- The canonical positive-refund detail contains 2,340 rows and sums to ₹6,709,932. The monthly-by-reason and monthly-by-agent exported amounts each sum to the same total.
- The local reason-code model has 585 held-out records, 58.3% accuracy and 0.592 macro-F1 against the existing agent-selected reason codes.

## Not completed in this authoring environment

The Streamlit UI was not launched here because Streamlit was not installed and the package index could not be reached to install dependencies. The UI source passed Python syntax compilation, but an actual browser-based run still needs to be performed after following `README.md` on a machine that can install the requirements. Do not represent a browser smoke test as completed until it has actually been run.

## Interpretation cautions

- The ₹100 legacy divisor is a documented inference supported by 125 duplicate refund pairs and order-value plausibility; Finance should confirm it against the ledger before external reporting.
- Monthly totals use `created_at` as a proxy because the export contains no refund-event timestamp.
- Order-level refund-plus-replacement flags are review candidates, not confirmed losses or booked savings.
- Model performance is agreement with the existing dropdown codes, not validated truth about the customer's underlying reason.
