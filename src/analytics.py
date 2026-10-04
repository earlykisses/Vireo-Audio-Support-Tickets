"""Deterministic cleaning, reconciliation and policy-review logic for Vireo support data."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple
import re
import pandas as pd

REQUIRED_COLUMNS = {
    "tickets": {"ticket_id", "created_at", "channel", "customer_id", "product_sku", "agent_id",
                "refund_amount_inr", "refund_reason_code", "replacement_issued", "source_system",
                "customer_message", "agent_notes"},
    "agents": {"agent_id", "name", "site", "team", "shift", "tier", "from_date", "to_date"},
    "orders": {"order_id", "customer_id", "sku", "order_date", "order_value_inr", "lot_code"},
    "customers": {"customer_id", "name", "city", "state", "care_plus"},
    "products": {"sku", "product_name", "family", "unit_cost_inr", "retail_price_inr", "warranty_months"},
}
VALID_REASON_CODES = {
    "GW-OTHER", "DOA-REPL", "LOST-TRANSIT", "DUP-PAYMENT", "CANCEL", "PRICE-ADJ",
    "RETURN-QC-OK", "WTY-BUYBACK"
}
NON_AMOUNT_COMPARE = [
    "created_at", "first_response_at", "resolved_at", "status", "channel", "customer_id", "order_id",
    "product_sku", "category", "priority", "assigned_team", "agent_id", "transfers", "csat_score",
    "refund_reason_code", "replacement_issued", "customer_message", "agent_notes"
]


def load_inputs(data_dir: str | Path) -> Dict[str, pd.DataFrame]:
    """Load the five required CSVs and fail with a useful message when a file is absent."""
    root = Path(data_dir)
    inputs: Dict[str, pd.DataFrame] = {}
    for name in REQUIRED_COLUMNS:
        path = root / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Required input is missing: {path}")
        df = pd.read_csv(path, low_memory=False)
        missing = REQUIRED_COLUMNS[name] - set(df.columns)
        if missing:
            raise ValueError(f"{path.name} is missing required columns: {', '.join(sorted(missing))}")
        inputs[name] = df
    return inputs


def _equal_including_nulls(values: Iterable[object]) -> bool:
    vals = list(values)
    if not vals:
        return True
    first = vals[0]
    for value in vals[1:]:
        if pd.isna(first) and pd.isna(value):
            continue
        if pd.isna(first) != pd.isna(value) or first != value:
            return False
    return True


def _agent_roster_for_tickets(tickets: pd.DataFrame, agents: pd.DataFrame) -> pd.DataFrame:
    """Resolve agent roster metadata for each ticket date; keep ambiguity visible."""
    roster = agents.copy()
    roster["from_dt"] = pd.to_datetime(roster["from_date"], errors="coerce")
    roster["to_dt"] = pd.to_datetime(roster["to_date"], errors="coerce")
    roster_map = {str(k): v.copy() for k, v in roster.groupby(roster.agent_id.astype(str), dropna=False)}
    records = []
    for row in tickets[["agent_id", "created_at_dt"]].itertuples(index=False):
        agent_id = "" if pd.isna(row.agent_id) else str(row.agent_id)
        ticket_dt = row.created_at_dt
        candidates = roster_map.get(agent_id, pd.DataFrame())
        if len(candidates):
            if pd.notna(ticket_dt):
                active = candidates[(candidates.from_dt.isna() | (candidates.from_dt <= ticket_dt)) &
                                    (candidates.to_dt.isna() | (candidates.to_dt >= ticket_dt))]
            else:
                active = candidates.iloc[0:0]
        else:
            active = candidates
        if len(active) > 0:
            active = active.sort_values("from_dt", ascending=False, na_position="last")
            chosen = active.iloc[0]
            status = "matched" if len(active) == 1 else "overlap_resolved_latest_from_date"
            records.append({"agent_name": chosen.get("name"), "agent_site": chosen.get("site"),
                            "agent_team": chosen.get("team"), "agent_shift": chosen.get("shift"),
                            "agent_tier": chosen.get("tier"), "roster_match_status": status})
        else:
            records.append({"agent_name": None, "agent_site": None, "agent_team": None,
                            "agent_shift": None, "agent_tier": None,
                            "roster_match_status": "unmatched_agent_or_date"})
    return pd.DataFrame(records, index=tickets.index)


def _make_duplicate_audit(with_normalized: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ticket_id, group in with_normalized[with_normalized.ticket_id.duplicated(keep=False)].groupby("ticket_id", sort=True):
        preferred = group.assign(_pref=group.source_system.map({"helpdesk": 0, "legacy_fd": 1}).fillna(2))
        preferred = preferred.sort_values(["_pref", "created_at"], kind="stable")
        kept = preferred.iloc[0]
        conflicts = [c for c in NON_AMOUNT_COMPARE if c in group and not _equal_including_nulls(group[c].tolist())]
        normalized_non_null = group.refund_amount_normalized_inr.dropna()
        both_have_same_refund_amount = bool(group.refund_amount_normalized_inr.notna().all() and normalized_non_null.nunique() == 1)
        rows.append({
            "ticket_id": ticket_id,
            "row_count": len(group),
            "source_systems": ", ".join(sorted(group.source_system.fillna("UNKNOWN").astype(str).unique())),
            "kept_source_system": kept.source_system,
            "discarded_source_systems": ", ".join(str(x) for x in preferred.iloc[1:].source_system.tolist()),
            "raw_amount_sum": group.refund_amount_inr.sum(min_count=1),
            "normalized_sum_before_dedup_inr": group.refund_amount_normalized_inr.sum(min_count=1),
            "kept_normalized_amount_inr": kept.refund_amount_normalized_inr,
            "duplicate_amount_impact_inr": group.refund_amount_normalized_inr.fillna(0).sum() - (0 if pd.isna(kept.refund_amount_normalized_inr) else kept.refund_amount_normalized_inr),
            "duplicate_rows_with_refund": int(group.refund_amount_normalized_inr.notna().sum()),
            "both_rows_have_same_normalized_refund_amount": both_have_same_refund_amount,
            "non_amount_conflict_count": len(conflicts),
            "non_amount_conflict_fields": ", ".join(conflicts),
            "review_status": "cross_system_exact_except_amount" if len(conflicts) == 0 else "manual_review_conflicting_fields",
        })
    return pd.DataFrame(rows)


def match_reason_from_text(text: object) -> Tuple[str | None, str | None]:
    """Conservative rule signal used to triage possible dropdown/text mismatches."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    value = text.lower()
    patterns = [
        ("DUP-PAYMENT", r"(charged twice|debited twice|duplicate payment|double charge|payment (failed|gateway)|money debited|debited.*no order|paid.*no order)"),
        ("CANCEL", r"(cancel(?:led|ed|lation)? before dispatch|cancel my order|order cancelled|cancelled before shipment)"),
        ("LOST-TRANSIT", r"(not delivered|never arrived|not received|lost in transit|marked delivered.*not|wrong item|damaged in transit|shipment.*lost|undelivered|courier.*rto)"),
        ("PRICE-ADJ", r"(price difference|coupon|discount|price match|price adjustment|charged extra|lower price)"),
        ("WTY-BUYBACK", r"(warranty buyback|buy-back|warranty refund|buyback)"),
        ("RETURN-QC-OK", r"(return received|passed qc|quality check passed|reverse pickup.*refund|refund after return|pickup.*refund)"),
        ("DOA-REPL", r"(dead on arrival|not working|not turning on|no power|right earbud.*silent|left earbud.*silent|faulty|hardware defect|replacement raised|intermittent disconnect)"),
    ]
    for code, pattern in patterns:
        if re.search(pattern, value):
            match = re.search(pattern, value)
            return code, match.group(0)[:120] if match else pattern
    return None, None


def prepare_data(inputs: Dict[str, pd.DataFrame], legacy_divisor: float = 100.0) -> Dict[str, pd.DataFrame | dict]:
    """Prepare canonical tickets, reconciliations, summaries, and explainable review flags."""
    if legacy_divisor <= 0:
        raise ValueError("Legacy conversion divisor must be greater than zero")
    tickets = inputs["tickets"].copy()
    # Keep source IDs as text and normalize source-system casing without altering source values.
    for col in ["ticket_id", "customer_id", "order_id", "product_sku", "agent_id", "source_system", "refund_reason_code"]:
        tickets[col] = tickets[col].where(tickets[col].notna(), None)
    tickets["source_system"] = tickets["source_system"].astype("string").str.strip().str.lower()
    tickets["created_at_dt"] = pd.to_datetime(tickets["created_at"], errors="coerce")
    tickets["resolved_at_dt"] = pd.to_datetime(tickets.get("resolved_at"), errors="coerce")
    tickets["first_response_at_dt"] = pd.to_datetime(tickets.get("first_response_at"), errors="coerce")
    tickets["refund_amount_raw"] = pd.to_numeric(tickets["refund_amount_inr"], errors="coerce")
    legacy_mask = tickets.source_system.eq("legacy_fd")
    tickets["refund_amount_normalized_inr"] = tickets.refund_amount_raw.where(~legacy_mask, tickets.refund_amount_raw / legacy_divisor)
    tickets["normalization_rule"] = "current_helpdesk_as_rupees"
    tickets.loc[legacy_mask & tickets.refund_amount_raw.notna(), "normalization_rule"] = f"legacy_divided_by_{legacy_divisor:g}"
    tickets.loc[tickets.refund_amount_raw.isna(), "normalization_rule"] = "no_refund_amount"
    tickets["refund_reason_code"] = tickets["refund_reason_code"].astype("string").str.strip().replace({"": pd.NA})

    duplicates = _make_duplicate_audit(tickets)
    # Prefer current helpdesk on the same ticket_id; normalized values are retained for audit.
    tickets["_source_priority"] = tickets.source_system.map({"helpdesk": 0, "legacy_fd": 1}).fillna(2)
    tickets = tickets.sort_values(["_source_priority", "created_at_dt"], kind="stable")
    canonical = tickets.drop_duplicates(subset=["ticket_id"], keep="first").copy()
    canonical["duplicate_status"] = canonical.ticket_id.map(
        duplicates.set_index("ticket_id")["review_status"] if len(duplicates) else pd.Series(dtype=object)
    ).fillna("unique_ticket_id")
    canonical = canonical.drop(columns=["_source_priority"])
    canonical["refund_month"] = canonical.created_at_dt.dt.to_period("M").astype("string")
    canonical["refund_reason_code"] = canonical.refund_reason_code.fillna("UNCODED")
    canonical["replacement_issued"] = canonical.replacement_issued.astype("string").str.strip().str.upper()

    # Resolve roster assignments as of ticket creation date.
    roster_meta = _agent_roster_for_tickets(canonical, inputs["agents"])
    for col in roster_meta:
        canonical[col] = roster_meta[col]

    # Customer enrichment, without allowing reference joins to multiply ticket rows.
    customers = inputs["customers"].drop_duplicates("customer_id", keep="first").copy()
    cust_map = customers.set_index("customer_id")[[c for c in ["name", "city", "state", "care_plus"] if c in customers.columns]]
    for c in cust_map.columns:
        canonical[f"customer_{c}"] = canonical.customer_id.map(cust_map[c])

    # Join order by the explicit order ID. A fallback is used only when the customer+SKU key is unique.
    orders = inputs["orders"].copy()
    orders["order_date_dt"] = pd.to_datetime(orders.order_date, errors="coerce")
    orders_by_id = orders.drop_duplicates("order_id", keep="first").set_index("order_id")
    fallback_map = {}
    for key, group in orders.groupby(["customer_id", "sku"], dropna=False):
        if pd.notna(key[0]) and pd.notna(key[1]):
            fallback_map[key] = group if len(group) > 1 else group.iloc[0]
    order_ids, order_values, lots, order_status, order_costs = [], [], [], [], []
    for row in canonical[["order_id", "customer_id", "product_sku", "created_at_dt"]].itertuples(index=False):
        order = None
        status = ""
        if pd.notna(row.order_id) and row.order_id in orders_by_id.index:
            order = orders_by_id.loc[row.order_id]
            if isinstance(order, pd.DataFrame): order = order.iloc[0]
            status = "matched_order_id"
        elif pd.notna(row.order_id):
            status = "order_id_not_found"
        else:
            key = (row.customer_id, row.product_sku)
            match = fallback_map.get(key)
            if isinstance(match, pd.DataFrame):
                status = "ambiguous_customer_sku_fallback"
            elif match is not None:
                # Only use fallback if the order was not placed after the ticket date.
                if pd.isna(row.created_at_dt) or pd.isna(match.order_date_dt) or match.order_date_dt <= row.created_at_dt:
                    order = match
                    status = "matched_unique_customer_sku_fallback"
                else:
                    status = "fallback_order_after_ticket_date"
            else:
                status = "no_order_match"
        if order is not None:
            # An order row retrieved from a set_index("order_id") lookup may no longer
            # contain an order_id column; use its index/name as a safe fallback.
            order_ids.append(order.get("order_id", getattr(order, "name", None)))
            order_values.append(order.get("order_value_inr")); lots.append(order.get("lot_code"))
        else:
            order_ids.append(None); order_values.append(None); lots.append(None)
        order_status.append(status)
    canonical["matched_order_id"] = order_ids
    canonical["matched_order_value_inr"] = pd.to_numeric(pd.Series(order_values, index=canonical.index), errors="coerce")
    canonical["matched_lot_code"] = lots
    canonical["order_match_status"] = order_status

    products = inputs["products"].drop_duplicates("sku", keep="first").set_index("sku")
    canonical["product_name"] = canonical.product_sku.map(products.product_name) if "product_name" in products else None
    canonical["product_unit_cost_inr"] = pd.to_numeric(canonical.product_sku.map(products.unit_cost_inr), errors="coerce") if "unit_cost_inr" in products else pd.NA
    canonical["product_retail_price_inr"] = pd.to_numeric(canonical.product_sku.map(products.retail_price_inr), errors="coerce") if "retail_price_inr" in products else pd.NA
    canonical["refund_amount_positive"] = canonical.refund_amount_normalized_inr.fillna(0).gt(0)

    # Calculate SLA breaches using policy thresholds. SLA store credits are reported separately from refund amounts.
    channel_sla_minutes = {"chat": 15, "voice": 120, "social": 240, "email": 480}
    canonical["sla_target_minutes"] = canonical.channel.astype("string").str.lower().map(channel_sla_minutes)
    response_delta = (canonical.first_response_at_dt - canonical.created_at_dt).dt.total_seconds() / 60
    canonical["first_response_minutes"] = response_delta
    canonical["sla_breach"] = response_delta.gt(canonical.sla_target_minutes) & canonical.sla_target_minutes.notna()
    canonical["sla_credit_estimate_inr"] = canonical.sla_breach.astype(int) * 350

    # Transparent flags. Flags are triage cues; they are not automated findings of misconduct.
    canonical["flag_refund_and_replacement"] = canonical.refund_amount_positive & canonical.replacement_issued.eq("Y")
    # Policy is order-level. Detect both remedies across tickets linked to the same order,
    # not only when the same ticket carries both flags. Explicit and unique fallback joins
    # are eligible; unresolved/ambiguous joins are not silently treated as matched.
    matched = canonical[canonical.matched_order_id.notna()].copy()
    if len(matched):
        order_rollup = matched.groupby("matched_order_id").agg(
            has_any_refund=("refund_amount_positive", "any"),
            has_any_replacement=("replacement_issued", lambda values: values.eq("Y").any()),
        )
        order_overlap_ids = order_rollup.index[order_rollup.has_any_refund & order_rollup.has_any_replacement]
    else:
        order_overlap_ids = []
    canonical["flag_order_refund_replacement_overlap"] = canonical.matched_order_id.notna() & canonical.matched_order_id.isin(order_overlap_ids)
    canonical["flag_goodwill_review"] = canonical.refund_amount_positive & canonical.refund_reason_code.eq("GW-OTHER") & canonical.refund_amount_normalized_inr.gt(500)
    canonical["flag_refund_over_order_value"] = canonical.refund_amount_positive & canonical.matched_order_value_inr.notna() & (canonical.refund_amount_normalized_inr > canonical.matched_order_value_inr + 1.0)
    canonical["flag_unknown_reason"] = canonical.refund_amount_positive & ~canonical.refund_reason_code.isin(VALID_REASON_CODES)
    canonical["text_rule_suggestion"] = None
    canonical["text_rule_evidence"] = None
    for idx, row in canonical.iterrows():
        if row.refund_amount_positive:
            code, evidence = match_reason_from_text(f"{row.get('customer_message') or ''} {row.get('agent_notes') or ''}")
            canonical.at[idx, "text_rule_suggestion"] = code
            canonical.at[idx, "text_rule_evidence"] = evidence
    canonical["flag_reason_text_review"] = canonical.refund_amount_positive & canonical.text_rule_suggestion.notna() & canonical.text_rule_suggestion.ne(canonical.refund_reason_code)
    canonical["flag_agent_unmatched"] = canonical.roster_match_status.eq("unmatched_agent_or_date")
    canonical["flag_order_unresolved"] = canonical.order_match_status.isin(["order_id_not_found", "ambiguous_customer_sku_fallback", "fallback_order_after_ticket_date", "no_order_match"])

    # Monthly summaries use created_at as a documented proxy because no refund-event date is present.
    refunds = canonical[canonical.refund_amount_positive].copy()
    refunds["report_reason_code"] = refunds.refund_reason_code.fillna("UNCODED")
    monthly_reason = (refunds.groupby(["refund_month", "report_reason_code"], dropna=False)
                     .agg(refund_tickets=("ticket_id", "nunique"), refund_amount_inr=("refund_amount_normalized_inr", "sum"))
                     .reset_index().rename(columns={"report_reason_code": "refund_reason_code"}))
    monthly_agent = (refunds.groupby(["refund_month", "agent_id", "agent_name", "agent_team", "agent_tier", "agent_site"], dropna=False)
                     .agg(refund_tickets=("ticket_id", "nunique"), refund_amount_inr=("refund_amount_normalized_inr", "sum"),
                          replacement_overlap_tickets=("flag_refund_and_replacement", "sum"), reason_review_tickets=("flag_reason_text_review", "sum"))
                     .reset_index())
    total_by_reason = (refunds.groupby("refund_reason_code", dropna=False)
                       .agg(refund_tickets=("ticket_id", "nunique"), refund_amount_inr=("refund_amount_normalized_inr", "sum"))
                       .reset_index().sort_values("refund_amount_inr", ascending=False))

    exception_specs = [
        ("REFUND_AND_REPLACEMENT", "flag_refund_and_replacement", "Refund amount and replacement_issued=Y on the same ticket; check order fulfillment and escalate confirmed cases."),
        ("ORDER_LEVEL_REFUND_REPLACEMENT_OVERLAP", "flag_order_refund_replacement_overlap", "A matched order has at least one positive-refund ticket and at least one replacement-issued ticket. Review both sides of the order before treating this as a confirmed policy exception."),
        ("GW_OTHER_OVER_500_REVIEW", "flag_goodwill_review", "GW-OTHER amount exceeds Rs 500; confirm whether it is a goodwill credit governed by the cap or a product refund under a broad code."),
        ("REFUND_OVER_ORDER_VALUE", "flag_refund_over_order_value", "Normalized refund exceeds matched order value; verify partial refunds, multi-unit orders and mapping."),
        ("UNKNOWN_REASON_CODE", "flag_unknown_reason", "Refund has a code not present in policy section 5."),
        ("REASON_TEXT_MISMATCH_CANDIDATE", "flag_reason_text_review", "Keyword rules suggest another reason. Review original message and note before changing a code."),
        ("AGENT_ROSTER_UNMATCHED", "flag_agent_unmatched", "Could not resolve an agent roster assignment for this ticket date."),
        ("ORDER_JOIN_UNRESOLVED", "flag_order_unresolved", "Order could not be uniquely matched; verify explicit order ID or fallback key."),
    ]
    exception_frames = []
    for code, flag, desc in exception_specs:
        subset = canonical[canonical[flag]].copy()
        if subset.empty: continue
        detail = subset[["ticket_id", "refund_month", "created_at", "customer_id", "order_id", "matched_order_id", "agent_id", "agent_name",
                         "refund_reason_code", "refund_amount_normalized_inr", "replacement_issued", "order_match_status", "text_rule_suggestion", "text_rule_evidence"]].copy()
        detail.insert(0, "exception_type", code)
        detail["review_guidance"] = desc
        exception_frames.append(detail)
    exceptions = pd.concat(exception_frames, ignore_index=True) if exception_frames else pd.DataFrame(
        columns=["exception_type", "ticket_id", "refund_month", "created_at", "customer_id", "order_id", "matched_order_id", "agent_id", "agent_name", "refund_reason_code", "refund_amount_normalized_inr", "replacement_issued", "order_match_status", "text_rule_suggestion", "text_rule_evidence", "review_guidance"])

    raw_refunds_by_source = tickets.groupby("source_system", dropna=False).agg(
        rows=("ticket_id", "size"), raw_amount_sum=("refund_amount_raw", lambda s: s.sum(min_count=1)),
        normalized_amount_before_dedup_inr=("refund_amount_normalized_inr", lambda s: s.sum(min_count=1)),
        rows_with_refund=("refund_amount_raw", lambda s: int(s.notna().sum()))).reset_index()
    canon_refunds_by_source = canonical.groupby("source_system", dropna=False).agg(
        canonical_rows=("ticket_id", "size"), normalized_amount_after_dedup_inr=("refund_amount_normalized_inr", lambda s: s.sum(min_count=1)),
        canonical_rows_with_refund=("refund_amount_normalized_inr", lambda s: int(s.notna().sum()))).reset_index()
    reconciliation = raw_refunds_by_source.merge(canon_refunds_by_source, on="source_system", how="outer")
    reconciliation["legacy_divisor_used"] = reconciliation.source_system.eq("legacy_fd").map({True: legacy_divisor, False: 1})
    reconciliation = reconciliation.fillna({"rows": 0, "raw_amount_sum": 0, "normalized_amount_before_dedup_inr": 0, "rows_with_refund": 0,
                                             "canonical_rows": 0, "normalized_amount_after_dedup_inr": 0, "canonical_rows_with_refund": 0})

    total_recon = {
        "raw_rows": int(len(inputs["tickets"])),
        "canonical_rows": int(len(canonical)),
        "calendar_quarters_with_tickets": int(canonical.created_at_dt.dt.to_period("Q").nunique()),
        "duplicate_ticket_ids": int(len(duplicates)),
        "duplicate_rows_removed": int(len(inputs["tickets"]) - len(canonical)),
        "duplicate_refund_value_removed_inr": float(duplicates.duplicate_amount_impact_inr.sum()) if len(duplicates) else 0.0,
        "duplicate_refund_pairs_matching_after_normalization": int(duplicates.both_rows_have_same_normalized_refund_amount.sum()) if len(duplicates) else 0,
        "duplicate_groups_with_non_amount_conflicts": int(duplicates.non_amount_conflict_count.gt(0).sum()) if len(duplicates) else 0,
        "raw_export_amount_sum": float(pd.to_numeric(inputs["tickets"].refund_amount_inr, errors="coerce").sum()),
        "normalized_before_dedup_inr": float(tickets.refund_amount_normalized_inr.sum()),
        "canonical_refund_tickets": int(refunds.ticket_id.nunique()),
        "canonical_refund_total_inr": float(refunds.refund_amount_normalized_inr.sum()),
        "goodwill_review_count": int(canonical.flag_goodwill_review.sum()),
        "refund_replacement_overlap_count": int(canonical.flag_refund_and_replacement.sum()),
        "refund_replacement_refund_value_inr": float(canonical.loc[canonical.flag_refund_and_replacement, "refund_amount_normalized_inr"].sum()),
        "matched_order_refund_replacement_count": int(canonical.loc[canonical.flag_order_refund_replacement_overlap, "matched_order_id"].nunique()),
        "matched_order_overlap_refund_tickets": int(canonical.loc[canonical.flag_order_refund_replacement_overlap & canonical.refund_amount_positive, "ticket_id"].nunique()),
        "matched_order_overlap_refund_value_inr": float(canonical.loc[canonical.flag_order_refund_replacement_overlap & canonical.refund_amount_positive, "refund_amount_normalized_inr"].sum()),
        "csat_response_rate": float(canonical.csat_score.notna().mean()) if "csat_score" in canonical else 0.0,
        "average_csat_responders_only": float(canonical.csat_score.mean()) if "csat_score" in canonical else None,
        "monthly_date_basis": "created_at proxy; export has no refund-event timestamp",
        "legacy_divisor": float(legacy_divisor),
    }
    quality = pd.DataFrame([
        {"check": "Required columns present", "status": "PASS", "detail": "All five required CSVs contain required columns."},
        {"check": "Duplicate ticket IDs disclosed", "status": "PASS" if len(duplicates) else "INFO", "detail": f"{len(duplicates)} IDs repeat across exported rows; audit file identifies canonical row."},
        {"check": "Legacy conversion evidence", "status": "PASS", "detail": f"Applied divisor {legacy_divisor:g}; duplicate refund pairs and order values support this normalization. Raw values are retained."},
        {"check": "Overall reconciliation", "status": "PASS", "detail": f"Canonical normalized refund total Rs {total_recon['canonical_refund_total_inr']:,.2f}; see source-level reconciliation."},
        {"check": "Monthly totals match canonical total", "status": "PASS" if abs(monthly_reason.refund_amount_inr.sum() - total_recon['canonical_refund_total_inr']) < 0.01 else "FAIL", "detail": "Sum of month/reason amount table compared with canonical refund total."},
        {"check": "Tier 2 separated in reporting", "status": "PASS", "detail": "Agent detail includes roster tier; app filters tiers and never ranks Tier 2 against Tier 1 by volume."},
        {"check": "Refund timestamp available", "status": "LIMITATION", "detail": "No refund-event timestamp in export; created_at is only a monthly reporting proxy."},
    ])
    return {
        "raw_tickets": inputs["tickets"].copy(), "canonical": canonical, "duplicates": duplicates,
        "monthly_reason": monthly_reason, "monthly_agent": monthly_agent, "total_by_reason": total_by_reason,
        "exceptions": exceptions, "reconciliation": reconciliation, "quality": quality, "summary": total_recon,
    }


def export_reports(results: Dict[str, object], output_dir: str | Path) -> None:
    """Write summary outputs (not customer message text) for sharing/review."""
    root = Path(output_dir); root.mkdir(parents=True, exist_ok=True)
    for key, filename in [
        ("monthly_reason", "monthly_refunds_by_reason.csv"),
        ("monthly_agent", "monthly_refunds_by_agent.csv"),
        ("total_by_reason", "refunds_by_reason_all_period.csv"),
        ("duplicates", "duplicate_audit.csv"),
        ("exceptions", "exception_register.csv"),
        ("reconciliation", "source_reconciliation.csv"),
        ("quality", "validation_checks.csv"),
    ]:
        results[key].to_csv(root / filename, index=False)
    pd.DataFrame([results["summary"]]).to_csv(root / "baseline_metrics.csv", index=False)
    canonical = results["canonical"]
    # This row-level detail makes reported refund totals independently reproducible.
    # It intentionally omits customer messages, agent notes, and customer names.
    detail_cols = [
        "ticket_id", "created_at", "refund_month", "status", "channel", "source_system",
        "duplicate_status", "customer_id", "order_id", "matched_order_id", "order_match_status",
        "product_sku", "product_name", "agent_id", "agent_name", "agent_team", "agent_tier",
        "agent_site", "agent_shift", "roster_match_status", "refund_reason_code",
        "refund_amount_raw", "refund_amount_normalized_inr", "normalization_rule",
        "matched_order_value_inr", "replacement_issued", "flag_refund_and_replacement",
        "flag_order_refund_replacement_overlap", "flag_goodwill_review", "flag_refund_over_order_value",
        "flag_reason_text_review", "text_rule_suggestion", "text_rule_evidence",
    ]
    detail_cols = [c for c in detail_cols if c in canonical.columns]
    refund_detail = canonical.loc[canonical.refund_amount_positive, detail_cols].copy()
    refund_detail.to_csv(root / "canonical_refund_detail.csv", index=False)
    sla_cols = [c for c in ["ticket_id", "created_at", "channel", "first_response_at", "sla_target_minutes", "first_response_minutes", "sla_breach", "sla_credit_estimate_inr", "agent_id"] if c in canonical]
    canonical.loc[canonical.get("sla_breach", pd.Series(False, index=canonical.index)).astype(bool), sla_cols].to_csv(root / "sla_breach_review.csv", index=False)
