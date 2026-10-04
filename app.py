from __future__ import annotations
from pathlib import Path
import io
import pandas as pd
import streamlit as st

from src.analytics import load_inputs, prepare_data, export_reports
from src.modeling import train_reason_model, predict_reason

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data" / "raw"

st.set_page_config(page_title="Vireo Audio | Refund Analytics", page_icon="🎧", layout="wide")
st.title("Vireo Audio — Refund Reconciliation & Review")
st.caption("Local-first analytics · deterministic financial calculations · AI reason suggestions are review-only")

with st.sidebar:
    st.header("Analysis settings")
    data_dir = st.text_input("Folder containing the five CSV files", value=str(DEFAULT_DATA_DIR), help="Default data is bundled with this project.")
    legacy_divisor = st.number_input("Legacy amount divisor", min_value=1.0, max_value=100000.0, value=100.0, step=1.0,
                                     help="Default 100 is supported by 125 duplicate refund pairs that match exactly after conversion, plus order-value plausibility checks.")
    st.caption("Monthly reporting uses created_at as a proxy. There is no refund-event timestamp in this export.")

@st.cache_data(show_spinner="Loading, normalizing and reconciling support data…")
def get_results(path: str, divisor: float):
    inputs = load_inputs(path)
    return prepare_data(inputs, legacy_divisor=divisor)

@st.cache_resource(show_spinner="Training the local reason-code suggestion model…")
def get_model(path: str, divisor: float, source_mtime: float):
    results = get_results(path, divisor)
    return train_reason_model(results["canonical"])

try:
    results = get_results(data_dir, float(legacy_divisor))
except Exception as exc:
    st.error(f"Could not load or process the data: {exc}")
    st.info("Check that the folder contains tickets.csv, agents.csv, orders.csv, customers.csv and products.csv.")
    st.stop()

summary = results["summary"]
canonical = results["canonical"]
refunds = canonical[canonical.refund_amount_positive].copy()
source_path = Path(data_dir) / "tickets.csv"
try:
    mtime = source_path.stat().st_mtime
except OSError:
    mtime = 0.0

st.warning("**Interpretation guardrail:** Agent totals show who resolved the ticket, not who caused the refund. The app flags records for review; it does not allege misconduct or book savings.")
tab_overview, tab_monthly, tab_agents, tab_exceptions, tab_ai, tab_method = st.tabs([
    "Overview & reconciliation", "Monthly board tables", "Agent investigation", "Exceptions & QA", "AI reason assistant", "Methods & limitations"
])

with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Canonical tickets", f"{summary['canonical_rows']:,}", f"{summary['duplicate_rows_removed']:,} duplicate rows removed")
    c2.metric("Refunded tickets", f"{summary['canonical_refund_tickets']:,}")
    c3.metric("Normalized refund total", f"₹{summary['canonical_refund_total_inr']:,.0f}")
    quarter_count = max(1, summary.get("calendar_quarters_with_tickets", 6))
    c4.metric(f"Quarterly average ({quarter_count} quarters)", f"₹{summary['canonical_refund_total_inr']/quarter_count:,.0f}")
    st.subheader("Source-system reconciliation")
    st.dataframe(results["reconciliation"].style.format({
        "raw_amount_sum": "₹{:,.2f}", "normalized_amount_before_dedup_inr": "₹{:,.2f}",
        "normalized_amount_after_dedup_inr": "₹{:,.2f}", "rows": "{:,.0f}",
    }), use_container_width=True, hide_index=True)
    st.caption("Raw sums preserve what each export stored. Normalized sums divide legacy_fd by the selected divisor. Canonical sums keep one row per ticket_id, preferring helpdesk where both sources contain the same ID.")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Repeated ticket IDs", f"{summary['duplicate_ticket_ids']:,}")
    s2.metric("Duplicate refund value removed", f"₹{summary['duplicate_refund_value_removed_inr']:,.0f}")
    s3.metric("Same-ticket refund + replacement flags", f"{summary['refund_replacement_overlap_count']:,}", f"₹{summary['refund_replacement_refund_value_inr']:,.0f} attached refund value")
    s4.metric("Matched order-level overlap candidates", f"{summary['matched_order_refund_replacement_count']:,} orders", f"₹{summary['matched_order_overlap_refund_value_inr']:,.0f} on {summary['matched_order_overlap_refund_tickets']:,} refund tickets")
    st.subheader("Monthly refund trend")
    monthly = refunds.groupby("refund_month", as_index=False).agg(refund_tickets=("ticket_id", "nunique"), refund_amount_inr=("refund_amount_normalized_inr", "sum"))
    monthly = monthly.sort_values("refund_month")
    st.line_chart(monthly.set_index("refund_month")["refund_amount_inr"], y_label="INR (normalized)")
    st.dataframe(monthly.style.format({"refund_amount_inr": "₹{:,.0f}", "refund_tickets": "{:,.0f}"}), use_container_width=True, hide_index=True)

    st.subheader("Separate first-response SLA credit estimate")
    sla_breaches = canonical[canonical["sla_breach"]].copy()
    sla_count = int(canonical["sla_breach"].sum())
    sla_value = float(canonical["sla_credit_estimate_inr"].fillna(0).sum())
    sla_c1, sla_c2 = st.columns(2)
    sla_c1.metric("Estimated first-response breaches", f"{sla_count:,}")
    sla_c2.metric("Associated policy-credit value", f"₹{sla_value:,.0f}")
    st.caption("Estimated from created_at → first_response_at against the policy channel target. This is a separate SLA-credit estimate, not included in the refund total; confirm against issued-credit records before accounting use.")
    st.download_button("Download SLA breach review CSV", sla_breaches[[c for c in ["ticket_id", "created_at", "channel", "first_response_at", "sla_target_minutes", "first_response_minutes", "sla_breach", "sla_credit_estimate_inr", "agent_id"] if c in sla_breaches]].to_csv(index=False).encode("utf-8-sig"), "sla_breach_review.csv", "text/csv")
    st.subheader("All-period refund amount by reason")
    reason = results["total_by_reason"].copy()
    reason["share_of_refund_value_pct"] = reason.refund_amount_inr / max(1, reason.refund_amount_inr.sum()) * 100
    st.dataframe(reason.style.format({"refund_amount_inr": "₹{:,.0f}", "refund_tickets": "{:,.0f}", "share_of_refund_value_pct": "{:.1f}%"}), use_container_width=True, hide_index=True)

with tab_monthly:
    st.subheader("Monthly refunds by reason code")
    month_values = sorted(refunds.refund_month.dropna().astype(str).unique())
    if month_values:
        selected_months = st.multiselect("Months to include", month_values, default=month_values)
    else:
        selected_months = []
    reason_month = results["monthly_reason"].copy()
    agent_month = results["monthly_agent"].copy()
    if selected_months:
        reason_month = reason_month[reason_month.refund_month.astype(str).isin(selected_months)]
        agent_month = agent_month[agent_month.refund_month.astype(str).isin(selected_months)]
    st.dataframe(reason_month.sort_values(["refund_month", "refund_amount_inr"], ascending=[True, False]).style.format({"refund_amount_inr": "₹{:,.0f}", "refund_tickets": "{:,.0f}"}), use_container_width=True, hide_index=True)
    st.download_button("Download monthly-by-reason CSV", reason_month.to_csv(index=False).encode("utf-8-sig"), "monthly_refunds_by_reason.csv", "text/csv")
    st.divider()
    st.subheader("Monthly refunds by resolving agent")
    st.caption("Agent attribution uses agent_id from the ticket and roster details resolved for the ticket creation date. Counts/amounts are not a misconduct ranking; team, tier, channel mix and workload matter.")
    st.dataframe(agent_month.sort_values(["refund_month", "refund_amount_inr"], ascending=[True, False]).style.format({"refund_amount_inr": "₹{:,.0f}", "refund_tickets": "{:,.0f}", "replacement_overlap_tickets": "{:,.0f}", "reason_review_tickets": "{:,.0f}"}), use_container_width=True, hide_index=True)
    st.download_button("Download monthly-by-agent CSV", agent_month.to_csv(index=False).encode("utf-8-sig"), "monthly_refunds_by_agent.csv", "text/csv")

with tab_agents:
    st.subheader("Comparable agent investigation")
    st.caption("This page is for investigating mix-adjusted context. It deliberately separates tiers and does not label anyone as 'worst'. Tier 2 work is not compared to Tier 1 by raw volume per policy.")
    agent_summary = canonical.copy()
    agent_summary["is_refund"] = agent_summary.refund_amount_positive
    agent_summary["refund_value_for_sum"] = agent_summary.refund_amount_normalized_inr.fillna(0).where(agent_summary.refund_amount_positive, 0)
    agent_summary = agent_summary.groupby(["agent_id", "agent_name", "agent_team", "agent_tier", "agent_site", "agent_shift"], dropna=False).agg(
        tickets_resolved_or_attended=("ticket_id", "nunique"), refunded_tickets=("is_refund", "sum"),
        refund_amount_inr=("refund_value_for_sum", "sum"), replacement_overlap=("flag_refund_and_replacement", "sum"),
        text_review_flags=("flag_reason_text_review", "sum"), mean_csat=("csat_score", "mean"),
    ).reset_index()
    agent_summary["refund_incidence_pct"] = agent_summary.refunded_tickets / agent_summary.tickets_resolved_or_attended.replace(0, pd.NA) * 100
    tiers = sorted(agent_summary.agent_tier.dropna().unique().tolist())
    tier_filter = st.selectbox("Tier", ["All tiers"] + [f"Tier {int(t)}" for t in tiers])
    teams = sorted(agent_summary.agent_team.dropna().astype(str).unique())
    team_filter = st.selectbox("Team", ["All teams"] + teams)
    view = agent_summary.copy()
    if tier_filter != "All tiers": view = view[view.agent_tier.eq(int(tier_filter.split()[-1]))]
    if team_filter != "All teams": view = view[view.agent_team.astype(str).eq(team_filter)]
    st.dataframe(view.sort_values("refund_amount_inr", ascending=False).style.format({
        "refund_amount_inr": "₹{:,.0f}", "mean_csat": "{:.2f}", "refund_incidence_pct": "{:.1f}%",
        "tickets_resolved_or_attended": "{:,.0f}", "refunded_tickets": "{:,.0f}", "replacement_overlap": "{:,.0f}", "text_review_flags": "{:,.0f}"
    }), use_container_width=True, hide_index=True)
    st.download_button("Download agent investigation CSV", view.to_csv(index=False).encode("utf-8-sig"), "agent_investigation.csv", "text/csv")

with tab_exceptions:
    st.subheader("Exception register")
    st.caption("A flag means 'check this record'. Order-level overlaps can include multiple tickets for one order. GW-OTHER > ₹500 is deliberately a review cue, not an automatic policy breach, because a broad dropdown code may represent product refunds rather than a goodwill credit.")
    exceptions = results["exceptions"].copy()
    if len(exceptions):
        choices = sorted(exceptions.exception_type.unique())
        selected_types = st.multiselect("Exception types", choices, default=choices)
        filtered = exceptions[exceptions.exception_type.isin(selected_types)]
        st.write(f"**{len(filtered):,} exception rows** across **{filtered.ticket_id.nunique():,} unique tickets**. One ticket can have multiple flags.")
        st.dataframe(filtered, use_container_width=True, hide_index=True)
        st.download_button("Download exception register CSV", filtered.to_csv(index=False).encode("utf-8-sig"), "exception_register.csv", "text/csv")
    else:
        st.success("No exception flags under current settings.")
    st.subheader("Order-level refund + replacement overlap")
    order_overlap = canonical[canonical.flag_order_refund_replacement_overlap].copy()
    st.write(f"{summary['matched_order_refund_replacement_count']:,} matched order IDs have at least one refund ticket and at least one replacement-issued ticket. The queue includes {len(order_overlap):,} linked ticket rows; {summary['matched_order_overlap_refund_tickets']:,} carry positive refund amounts totaling ₹{summary['matched_order_overlap_refund_value_inr']:,.0f}. Verify all tickets and fulfillment before calling these confirmed policy exceptions.")
    st.dataframe(order_overlap[["matched_order_id", "ticket_id", "created_at", "agent_id", "agent_name", "refund_reason_code", "refund_amount_normalized_inr", "replacement_issued", "order_match_status"]], use_container_width=True, hide_index=True)
    st.download_button("Download order-level overlap CSV", order_overlap[["matched_order_id", "ticket_id", "created_at", "agent_id", "agent_name", "refund_reason_code", "refund_amount_normalized_inr", "replacement_issued", "order_match_status"]].to_csv(index=False).encode("utf-8-sig"), "order_level_refund_replacement.csv", "text/csv")
    st.subheader("Duplicate audit")
    st.write(f"{len(results['duplicates']):,} repeated ticket IDs. Conflicting non-amount fields require manual review.")
    st.dataframe(results["duplicates"], use_container_width=True, hide_index=True)
    st.download_button("Download duplicate audit CSV", results["duplicates"].to_csv(index=False).encode("utf-8-sig"), "duplicate_audit.csv", "text/csv")
    st.subheader("Validation checks")
    st.dataframe(results["quality"], use_container_width=True, hide_index=True)
    st.download_button("Download validation checks CSV", results["quality"].to_csv(index=False).encode("utf-8-sig"), "validation_checks.csv", "text/csv")

with tab_ai:
    st.subheader("Local AI reason-code assistant")
    st.write("A local TF-IDF + logistic-regression model learns to suggest one of the existing dropdown codes from the opening message and agent note. It does not call a paid API, does not overwrite the selected code and is not an adjudicator.")
    try:
        trained = get_model(str(Path(data_dir).resolve()), float(legacy_divisor), mtime)
    except Exception as exc:
        st.error(f"Model could not be trained: {exc}")
        trained = None
    if trained:
        metrics = trained["metrics"]
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Held-out accuracy", f"{metrics['accuracy']:.1%}", f"{metrics['n_test']:,} test records")
        mc2.metric("Held-out macro F1", f"{metrics['macro_f1']:.3f}")
        mc3.metric("Labelled records", f"{metrics['n_labelled']:,}")
        st.warning("Held-out accuracy is only about 58% and varies by class. Treat every prediction as a suggestion; the existing dropdown labels are themselves noisy. Do not auto-change codes or judge individual agents from this model.")
        with st.expander("Per-class holdout metrics"):
            st.dataframe(trained["class_report"], use_container_width=True, hide_index=True)
        with st.expander("Browse holdout predictions"):
            holdout_view = trained["holdout"].drop(columns=["model_text"]).copy()
            st.dataframe(holdout_view.style.format({"confidence": "{:.1%}", "refund_amount_inr": "₹{:,.0f}"}), use_container_width=True, hide_index=True)
            st.download_button("Download holdout audit CSV", holdout_view.to_csv(index=False).encode("utf-8-sig"), "ai_reason_holdout_audit.csv", "text/csv")
        with st.form("reason_suggestion_form"):
            text = st.text_area("Paste an anonymized customer opening message and/or agent note", height=140, placeholder="Example: Customer reports duplicate payment; payment gateway confirms two debits.")
            submit = st.form_submit_button("Suggest reason codes")
        if submit:
            if not text.strip(): st.warning("Enter some text first.")
            else:
                suggestion = predict_reason(trained["model"], text)
                st.dataframe(suggestion.style.format({"model_score": "{:.1%}"}), use_container_width=True, hide_index=True)
                st.caption("Model scores are not calibrated probabilities or proof that the reason is correct. A human should inspect the evidence and policy.")

with tab_method:
    st.subheader("Key assumptions & controls")
    st.markdown("""
- **Legacy money:** default divisor 100. Exact duplicate refund pairs with both source rows present match after /100; order-value checks provide a second plausibility check. Raw values remain preserved.
- **Deduplication:** one canonical row per ticket_id, preferring `helpdesk` when the same ID appears in both systems. Every duplicate group is listed in the audit. If non-amount fields conflict, review manually.
- **Monthly date:** `created_at` is used as a proxy because no refund-event timestamp exists. These are ticket-creation-month summaries, not confirmed bank/ledger cash-posting months.
- **Reason codes:** the dropdown code remains authoritative for finance aggregation until changed through a review process. Keyword and ML suggestions do not replace it.
- **Agent attribution:** the resolving `agent_id` is used. Raw amount totals are not evidence of poor performance; returns processing is concentrated by design and context matters.
- **Goodwill cap:** a GW-OTHER amount above ₹500 is a review cue only. Approval evidence is not in the provided files, and GW-OTHER can be used for broad cases.
- **Refund + replacement:** `refund_amount > 0` and `replacement_issued = Y` flags a policy exception candidate, because policy says a customer should not receive both for the same order. Missing order IDs still need operational verification.
- **SLA credits:** breaches are estimated from policy target times and listed separately. The ₹350 credit is not added to refund totals.
- **Privacy:** all CSV processing and model inference stay local. Avoid exporting customer text unless needed for a controlled review.
""")
    st.subheader("Download the current analysis outputs")
    for key, fname, label in [
        ("monthly_reason", "monthly_refunds_by_reason.csv", "Monthly refunds by reason"),
        ("monthly_agent", "monthly_refunds_by_agent.csv", "Monthly refunds by agent"),
        ("total_by_reason", "refunds_by_reason_all_period.csv", "All-period totals by reason"),
        ("reconciliation", "source_reconciliation.csv", "Source reconciliation"),
        ("quality", "validation_checks.csv", "Validation checks"),
    ]:
        st.download_button(label, results[key].to_csv(index=False).encode("utf-8-sig"), fname, "text/csv", key=f"download_{fname}")
    detail_cols = [c for c in [
        "ticket_id", "created_at", "refund_month", "status", "channel", "source_system", "duplicate_status",
        "customer_id", "order_id", "matched_order_id", "order_match_status", "product_sku", "product_name",
        "agent_id", "agent_name", "agent_team", "agent_tier", "agent_site", "agent_shift", "roster_match_status",
        "refund_reason_code", "refund_amount_raw", "refund_amount_normalized_inr", "normalization_rule",
        "matched_order_value_inr", "replacement_issued", "flag_refund_and_replacement",
        "flag_order_refund_replacement_overlap", "flag_goodwill_review", "flag_refund_over_order_value",
        "flag_reason_text_review", "text_rule_suggestion", "text_rule_evidence",
    ] if c in refunds.columns]
    st.download_button("Download canonical positive-refund detail CSV", refunds[detail_cols].to_csv(index=False).encode("utf-8-sig"), "canonical_refund_detail.csv", "text/csv", key="download_canonical_refund_detail.csv")
    st.caption("The detail export intentionally excludes customer messages and agent notes. Official Streamlit run instructions: https://docs.streamlit.io/develop/concepts/architecture/run-your-app")
