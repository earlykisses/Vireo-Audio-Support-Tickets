from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.analytics import load_inputs, prepare_data, export_reports
from src.modeling import train_reason_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reproducible Vireo refund reconciliation reports.")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "raw", help="Folder with the five source CSVs")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "latest", help="Folder for CSV outputs")
    parser.add_argument("--legacy-divisor", type=float, default=100.0, help="Divide legacy_fd refund values by this factor (default 100)")
    parser.add_argument("--skip-model", action="store_true", help="Skip slower AI model training and export only deterministic reports")
    args = parser.parse_args()
    inputs = load_inputs(args.data_dir)
    results = prepare_data(inputs, legacy_divisor=args.legacy_divisor)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    export_reports(results, args.output_dir)

    # Quarterly trend for business context. Refund incidence is by ticket creation quarter.
    canonical = results["canonical"].copy()
    canonical["quarter"] = canonical.created_at_dt.dt.to_period("Q").astype("string")
    canonical["is_refund"] = canonical.refund_amount_positive
    canonical["amount_for_summary"] = canonical.refund_amount_normalized_inr.fillna(0).where(canonical.refund_amount_positive, 0)
    quarterly = canonical.groupby("quarter", dropna=False).agg(
        tickets=("ticket_id", "nunique"), refund_tickets=("is_refund", "sum"),
        refund_amount_inr=("amount_for_summary", "sum"), csat_responses=("csat_score", "count"),
        mean_csat_responders_only=("csat_score", "mean"),
    ).reset_index()
    quarterly["refund_incidence_pct"] = quarterly.refund_tickets / quarterly.tickets.replace(0, pd.NA) * 100
    quarterly["csat_response_rate_pct"] = quarterly.csat_responses / quarterly.tickets.replace(0, pd.NA) * 100
    quarterly.to_csv(args.output_dir / "quarterly_trend.csv", index=False)

    if not args.skip_model:
        model = train_reason_model(results["canonical"])
        (args.output_dir / "ai_reason_model_metrics.json").write_text(json.dumps(model["metrics"], indent=2), encoding="utf-8")
        model["class_report"].to_csv(args.output_dir / "ai_reason_class_metrics.csv", index=False)
        model["holdout"].drop(columns=["model_text"]).to_csv(args.output_dir / "ai_reason_holdout_audit.csv", index=False)
    (args.output_dir / "validation_report.md").write_text(
        "# Validation report\n\n"
        f"- Raw ticket rows: {results['summary']['raw_rows']:,}\n"
        f"- Canonical ticket rows: {results['summary']['canonical_rows']:,}\n"
        f"- Repeated ticket IDs: {results['summary']['duplicate_ticket_ids']:,}\n"
        f"- Repeated refund pairs matching after normalization: {results['summary']['duplicate_refund_pairs_matching_after_normalization']:,}\n"
        f"- Repeated groups with non-amount conflicts: {results['summary']['duplicate_groups_with_non_amount_conflicts']:,}\n"
        f"- Normalized total before dedup: ₹{results['summary']['normalized_before_dedup_inr']:,.0f}\n"
        f"- Canonical normalized refund total: ₹{results['summary']['canonical_refund_total_inr']:,.0f}\n"
        f"- Duplicate refund value removed: ₹{results['summary']['duplicate_refund_value_removed_inr']:,.0f}\n"
        f"- Same-ticket refund-plus-replacement flags: {results['summary']['refund_replacement_overlap_count']:,} tickets; ₹{results['summary']['refund_replacement_refund_value_inr']:,.0f} associated refund amount\n"
        f"- Matched order-level refund-plus-replacement candidates: {results['summary']['matched_order_refund_replacement_count']:,} order IDs; {results['summary']['matched_order_overlap_refund_tickets']:,} positive-refund tickets; ₹{results['summary']['matched_order_overlap_refund_value_inr']:,.0f} associated refund value\n"
        f"- CSAT response rate: {results['summary']['csat_response_rate']:.1%}; responder-only mean: {results['summary']['average_csat_responders_only']:.2f}\n"
        + (f"- Holdout text model accuracy: {model['metrics']['accuracy']:.1%}; macro-F1: {model['metrics']['macro_f1']:.3f} ({model['metrics']['n_test']:,} test rows)\n\n" if not args.skip_model else "- Text model metrics: skipped by command-line option.\n\n")
        + "**Limitations:** `created_at` is used as a proxy because a refund-event timestamp is absent. Model labels are the existing agent-selected dropdown codes and can be noisy; holdout agreement is not ground-truth accuracy. Exception flags need operational review before being counted as confirmed leakage.\n",
        encoding="utf-8"
    )
    print(f"Canonical tickets: {results['summary']['canonical_rows']:,}")
    print(f"Positive-refund tickets: {results['summary']['canonical_refund_tickets']:,}")
    print(f"Canonical normalized refund total: ₹{results['summary']['canonical_refund_total_inr']:,.2f}")
    print(f"Repeated ticket IDs audited: {results['summary']['duplicate_ticket_ids']:,}")
    if not args.skip_model:
        print(f"AI holdout accuracy: {model['metrics']['accuracy']:.1%}; macro-F1: {model['metrics']['macro_f1']:.3f}")
    print(f"Reports written to: {args.output_dir.resolve()}")

if __name__ == "__main__":
    main()
