# Database Architecture

PostgreSQL hosted on **Neon** (free tier, pooled connection endpoint).
Two access layers: SQLAlchemy ORM for the FastAPI app, raw psycopg2 with
`execute_values` batching for pipeline scripts. Alembic migrations 001-006.

## Connection reliability

Long-running servers and free-tier Neon compute suspend/silently close idle
connections. The engine in `backend/db.py` is hardened against this:

- `pool_pre_ping=True` — validate every connection on checkout, replace dead ones
- `pool_recycle=280` — recycle before server-side idle cutoffs
- TCP keepalives (30s idle probe) in `connect_args`
- A 45s keep-warm thread keeps the Neon compute awake (see `LEARNING_LOG.md`,
  2026-08-31 incident)

## Tables

| Table | Purpose | Key columns |
|---|---|---|
| `transactions` | Live Razorpay orders + demo transactions | id, razorpay_order_id, razorpay_payment_link_id, amount_paise, status, failure_reason, previous_recovery_attempts, created_at |
| `recovery_attempts` | Recovery action tracking (schema reserved) | id, transaction_id FK, action, status, created_at |
| `webhook_events` | Raw Razorpay webhooks, deduplicated by provider event id | id (event id PK), event_type, payload JSONB, processed_at |
| `audit_logs` | Append-only audit trail | id, transaction_id (nullable), event, details JSONB, timestamp |
| `merchants` | Google-authenticated merchants | id, email (unique), name, created_at |
| `synthetic_events` | Benchmark dataset + enriched context + ground truth | id, amount_paise, status, failure_reason, customer_ref, previous_* counts, customer_tenure_days, average_order_value, time_since_last_* , checkout_duration_seconds, payment_method, ground_truth_recoverable, ground_truth_outcome, ground_truth_recovered_amount |
| `detection_results` | Baseline detector output (1:1 with synthetic_events) | id, synthetic_event_id FK, at_risk, recoverability, risk_reason, detected_at |
| `agent_decisions` | Recovery agent output (1:1 with decided events) | id, synthetic_event_id FK, diagnosis, recovery_probability, recommended_action, reason, confidence, decision_path, override_reason, created_at |

## Information separation

`synthetic_events` intentionally carries three column groups with different
consumers:

| Group | Columns | Consumer |
|---|---|---|
| Observed signals | amount_paise, status, failure_reason, previous_recovery_attempts, previous_successful_payments | Baseline detector (SELECTs 6 columns) |
| Enriched context | customer_tenure_days, previous_failed_payments, average_order_value, time_since_last_success/attempt, checkout_duration_seconds, payment_method | Recovery agent (SELECTs enriched set) |
| Ground truth (evaluation-only) | ground_truth_recoverable, ground_truth_outcome, ground_truth_recovered_amount | Evaluation/simulation only — never selected by the detector or the agent |

This separation is what prevents circular evaluation (see
`GROUND_TRUTH_POLICY.md`).

## Migrations

| Revision | Content |
|---|---|
| 001 | transactions, recovery_attempts, webhook_events, audit_logs |
| 002 | synthetic_events, detection_results |
| 003 | customer-behavior columns on synthetic_events |
| 004 | agent_decisions |
| 005 | transactions.failure_reason, transactions.previous_recovery_attempts |
| 006 | merchants |

Run with `alembic upgrade head` (also runs automatically on Render deploys).

## Access patterns

- Bulk inserts (1,000+ rows): `psycopg2.extras.execute_values`, 100-row pages
  — SQLAlchemy `executemany` times out against Neon (see `LEARNING_LOG.md`)
- Summary aggregates: one scalar-subquery statement computing detection,
  baseline and agent counts in a single round trip (cross-region queries are
  expensive — see `LEARNING_LOG.md`)
- 30s TTL cache on the `/dashboard/summary` payload (repeat loads instant)
- Long-running scripts: TCP keepalives + incremental commits + reconnect on
  dropped connections (`run_agent.py`, `execute_recovery.py`)
