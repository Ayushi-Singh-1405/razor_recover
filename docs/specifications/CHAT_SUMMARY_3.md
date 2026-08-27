# Chat Session 3 Summary

**Date:** 2026-08-26
**Repo:** `/home/aps/razor_recover` (branch: `main`, remote: `Ayushi-Singh-1405/razor_recover`)
**Commits this session:** `434e169`, `e22602b`, `378af15`, `4deff81`, `b655d72`

---

## What Was Done

### 1. Tuned `generate_synthetic_data.py` to hit policy target distribution
- Iteratively adjusted baseline tiers, signal scoring, and tier-up/tier-down thresholds
- Final baselines: network_error/otp_timeout/customer_abandoned → HIGH, insufficient_funds/card_declined → MEDIUM
- Signal scoring: 6 signals (previous_successful_payments, previous_failed_payments, checkout_duration ×2, amount deviation, time since last success)
- Tier-up threshold: ratio ≥ 0.35; tier-down: ratio < 0.10
- **Result:** HIGH=34.5%, MEDIUM=24.9%, LOW=3.6%, NONE=37.0%; ground_truth_recoverable=438 (43.8%, within policy target ~45-50%)

### 2. Fixed `previous_recovery_attempts` distribution (was broken)
- Problem: repeat customers got `randint(0,2)`, unique customers got `0` — never reached ≥3
- Fix: decoupled from repeat/unique decision, used weighted distribution (0→75%, 1→10%, 2→10%, 3→3%, 4→1.5%, 5→0.5%)
- Events with ≥3 attempts get plausible correlated fields: `previous_successful_payments ≥ 2`, `time_since_last_recovery_attempt_hours` always populated (1-168 hrs)
- **Result:** 54 events (5.4%) with ≥3 attempts; EXHAUSTED_ATTEMPTS=32 in detector (22 are succeeded→NOT_AT_RISK)

### 3. Committed 3 documentation files separately
- `backend/GROUND_TRUTH_POLICY.md` — 893-line policy doc
- `docs/specifications/CHAT_SUMMARY_2.md` — previous session summary
- `docs/workflow/DAY3_PLAN (1).md` — Day 3 workflow plan

---

## Current State of the Pipeline

| Component | File | Status |
|---|---|---|
| Synthetic data generator | `backend/generate_synthetic_data.py` | ✅ Working, seeded, reproducible |
| Detection rules | `backend/detect_at_risk.py` | ✅ Working, 5 risk reasons |
| Evaluation | `backend/evaluate.py` | ✅ Working, writes to `backend/reports/day2_baseline.txt` |
| ORM models | `backend/models.py` | ✅ SyntheticEvent has 7 new columns |
| Migration 003 | `backend/alembic/versions/003_add_customer_behavior_columns.py` | ✅ Applied |
| Ground truth policy | `backend/GROUND_TRUTH_POLICY.md` | ✅ Complete |

### Latest Evaluation Numbers
- **TP=438, FP=224, TN=338, FN=0**
- **Precision=0.66, Recall=1.00, F1=0.80**
- Risk reasons: NOT_AT_RISK=338, TRANSIENT_FAILURE=264, LOW_RECOVERY_PROBABILITY=204, CHECKOUT_ABANDONMENT=162, EXHAUSTED_ATTEMPTS=32

---

## Day 3 Plan Progress

### Gate A (non-negotiable) — 5/8 done
- ✅ Step 1: Enriched synthetic data with correlated fields
- ✅ Step 2: GROUND_TRUTH_POLICY.md written
- ✅ Step 3: Regenerate + validate dataset (seed 42, 1000 events)
- ✅ Distribution/realism documented honestly
- ❌ "What counts as a successful recovery" rules (no SIMULATION_RULES.md)
- ❌ Intervention penalty defined
- ❌ Baseline outcome simulation — no `simulate_outcomes.py`, no ₹ number
- ✅ Detection + evaluation pipeline working

### Gate B (AI experiment) — 0/8 done
- ❌ AI decision space (5 actions: recover_now, send_payment_link, wait_and_retry, escalate_to_merchant, stop)
- ❌ LLM provider setup (`backend/llm_provider.py`)
- ❌ Policy gate implementation
- ❌ Simulation rules for both systems
- ❌ AI-gated agent run
- ❌ Comparison table + verdict

---

## Key Technical Details for Next Session

### Neon Postgres Constraints
- Bulk inserts MUST use `psycopg2.execute_values` (SQLAlchemy `executamany` times out)
- Batch size 100 rows per commit

### Razorpay Webhook
- Signature: `razorpay_client.utility.verify_webhook_signature(body, signature, secret)`
- Event ID from `X-Razorpay-Event-Id` header, NOT `payload["id"]`
- Signature rejection writes audit log, raises HTTPException(401)

### Generator Ground Truth Logic (Section 20)
1. `status == "succeeded"` → NONE (first check)
2. `previous_recovery_attempts >= 3` → NONE (second check)
3. Failure-reason baseline tier → engagement adjustment → probability draw
4. Recovery probability: HIGH=0.85, MEDIUM=0.50, LOW=0.15, NONE=0.00
5. `ground_truth_outcome` values: `recovered` / `not_recovered`

### What to Do Next
1. Write simulation rules (SIMULATION_RULES.md or section in GROUND_TRUTH_POLICY.md)
2. Build `backend/simulate_outcomes.py` — run deterministic detector's actions through simulation rules, get baseline ₹ number
3. Define AI decision schema (5 actions from Day 3 plan Step 3)
4. Set up `backend/llm_provider.py` (OpenRouter, structured output)
5. Build AI agent, run through same simulation rules
6. Comparison table + honest verdict
7. Write `backend/reports/day3_experiment_result.md`
