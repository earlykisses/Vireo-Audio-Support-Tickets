from pathlib import Path
import pytest

from src.analytics import load_inputs, prepare_data
from src.modeling import train_reason_model

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "raw"


@pytest.fixture(scope="module")
def results():
    # Keep the data prep deterministic and run it only once; the pipeline performs
    # row-level roster/order resolution over the full export.
    return prepare_data(load_inputs(DATA_DIR), legacy_divisor=100)


def test_real_data_canonicalization_and_legacy_evidence(results):
    canonical = results["canonical"]
    assert len(load_inputs(DATA_DIR)["tickets"]) == 12238
    assert len(canonical) == 11600
    assert canonical["ticket_id"].nunique() == len(canonical)
    assert results["summary"]["duplicate_ticket_ids"] == 638
    assert results["summary"]["duplicate_rows_removed"] == 638
    assert results["summary"]["canonical_refund_tickets"] == 2340
    assert results["summary"]["canonical_refund_total_inr"] == 6709932.0
    assert results["summary"]["normalized_before_dedup_inr"] == 7070943.0
    assert results["summary"]["duplicate_refund_value_removed_inr"] == 361011.0
    assert results["duplicates"]["non_amount_conflict_count"].sum() == 0
    assert results["duplicates"]["row_count"].sum() == 1276


def test_monthly_reason_amounts_reconcile_to_canonical_refund_total(results):
    monthly_total = float(results["monthly_reason"]["refund_amount_inr"].sum())
    canonical_total = float(results["summary"]["canonical_refund_total_inr"])
    assert abs(monthly_total - canonical_total) < 0.01
    assert set(results["monthly_reason"]["refund_month"].dropna().astype(str)) == {
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
        "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
        "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
    }


def test_duplicate_audit_and_exception_register_are_reviewable(results):
    duplicates = results["duplicates"]
    exceptions = results["exceptions"]
    assert duplicates["ticket_id"].is_unique
    assert {"kept_source_system", "discarded_source_systems", "duplicate_amount_impact_inr", "review_status"}.issubset(duplicates.columns)
    assert {"exception_type", "ticket_id", "review_guidance"}.issubset(exceptions.columns)
    overlap = results["canonical"]["flag_refund_and_replacement"]
    assert int(overlap.sum()) == 166
    assert results["summary"]["refund_replacement_refund_value_inr"] == 574191.0


def test_text_model_evaluation_is_reproducible_and_not_perfect(results):
    model = train_reason_model(results["canonical"])
    metrics = model["metrics"]
    assert metrics["n_labelled"] == 2340
    assert metrics["n_test"] == 585
    assert metrics["random_state"] == 42
    assert 0.40 <= metrics["accuracy"] <= 0.75
    assert 0.40 <= metrics["macro_f1"] <= 0.75
    assert len(model["holdout"]) == metrics["n_test"]


def test_exported_refund_detail_reconciles(results, tmp_path):
    from src.analytics import export_reports
    import pandas as pd

    export_reports(results, tmp_path)
    detail_path = tmp_path / "canonical_refund_detail.csv"
    assert detail_path.exists()
    detail = pd.read_csv(detail_path)
    assert len(detail) == results["summary"]["canonical_refund_tickets"]
    assert abs(detail["refund_amount_normalized_inr"].sum() - results["summary"]["canonical_refund_total_inr"]) < 0.01
    assert "customer_message" not in detail.columns
    assert "agent_notes" not in detail.columns
