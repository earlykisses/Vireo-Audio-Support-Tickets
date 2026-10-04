# Validation report

- Raw ticket rows: 12,238
- Canonical ticket rows: 11,600
- Repeated ticket IDs: 638
- Repeated refund pairs matching after normalization: 125
- Repeated groups with non-amount conflicts: 0
- Normalized total before dedup: ₹7,070,943
- Canonical normalized refund total: ₹6,709,932
- Duplicate refund value removed: ₹361,011
- Same-ticket refund-plus-replacement flags: 166 tickets; ₹574,191 associated refund amount
- Matched order-level refund-plus-replacement candidates: 294 order IDs; 327 positive-refund tickets; ₹1,019,405 associated refund value
- CSAT response rate: 45.1%; responder-only mean: 3.49
- Holdout text model accuracy: 58.3%; macro-F1: 0.592 (585 test rows)

**Limitations:** `created_at` is used as a proxy because a refund-event timestamp is absent. Model labels are the existing agent-selected dropdown codes and can be noisy; holdout agreement is not ground-truth accuracy. Exception flags need operational review before being counted as confirmed leakage.
