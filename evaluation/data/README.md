# Benchmark Data — Dictionary and Provenance

CSV snapshots of the benchmark tables, exported from Neon via
`backend/export_datasets.py`. Regenerate with:

```bash
cd backend && ../venv/bin/python export_datasets.py
```

## Snapshot provenance

| File | Rows | Notes |
|---|---:|---|
| `synthetic_events.csv` | 1,000 | Seed-42 dataset with ground-truth columns |
| `detection_results.csv` | 1,000 | Baseline detector output (1:1 with events) |
| `agent_decisions.csv` | 662 | Recovery agent decisions (at-risk events only) |

Snapshot taken 2026-08-31 after the full 662-event agent run. Regenerating
the dataset with seed 42 reproduces these rows exactly.

## Ground truth warning

`ground_truth_recoverable`, `ground_truth_outcome`, and
`ground_truth_recovered_amount` are **evaluation-only** fields. They were
never shown to the detector or the agent at decision time — using them as
model inputs would defeat the benchmark's information separation.

## Column dictionary

### synthetic_events.csv

| Column | Meaning |
|---|---|
| id | Event UUID |
| amount_paise | Transaction amount (100 paise = Rs 1) |
| status | succeeded / failed / abandoned_checkout |
| failure_reason | network_error / otp_timeout / insufficient_funds / card_declined / customer_abandoned / NULL |
| customer_ref | Synthetic customer identifier |
| previous_successful_payments | Prior successful payments (enriched context) |
| previous_recovery_attempts | Recovery attempts before this event (observed signal) |
| customer_tenure_days | Customer age in days (enriched context) |
| previous_failed_payments | Prior failed payments (enriched context) |
| average_order_value | Historical AOV in paise (enriched context) |
| time_since_last_successful_payment_hours | Recency signal (enriched context) |
| time_since_last_recovery_attempt_hours | Recovery recency (enriched context) |
| checkout_duration_seconds | Behavioral signal (enriched context) |
| payment_method | card / upi / netbanking (enriched context) |
| ground_truth_recoverable | **Evaluation-only** — benchmark label |
| ground_truth_outcome | **Evaluation-only** — recovered / not_recovered |
| ground_truth_recovered_amount | **Evaluation-only** — credited on simulated success |
| created_at | Generation timestamp |

### detection_results.csv

| Column | Meaning |
|---|---|
| id | Result UUID |
| synthetic_event_id | FK to synthetic_events |
| at_risk | Detector flag (observed signals only) |
| recoverability | high / low / none — never "medium" |
| risk_reason | TRANSIENT_FAILURE / LOW_RECOVERY_PROBABILITY / CHECKOUT_ABANDONMENT / EXHAUSTED_ATTEMPTS / NOT_AT_RISK |
| detected_at | Detection timestamp |

### agent_decisions.csv

| Column | Meaning |
|---|---|
| id | Decision UUID |
| synthetic_event_id | FK to synthetic_events |
| diagnosis | Agent's root-cause diagnosis (LLM output) |
| recovery_probability | Agent-estimated recovery probability |
| recommended_action | One of the five bounded actions |
| reason | Agent's reasoning (enriched-context citations) |
| confidence | Agent's self-reported confidence |
| decision_path | ai_decision / pre_filtered / gated_override |
| override_reason | Why the policy gate overrode the agent, if it did |
| created_at | Decision timestamp |
| ground_truth_* | Evaluation-only join columns |

## Regeneration contract

- Seed 42 reproduces the dataset exactly.
- Re-export after any regeneration and update the row counts + date here.
- These snapshots correspond to the numbers in `../METRICS.md` and
  `../FAILURE_ANALYSIS.md` and the reports in `backend/reports/`.
