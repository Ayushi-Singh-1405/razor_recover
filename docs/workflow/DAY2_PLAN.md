# Day 2 Plan — RecoverAI (Phase 1: Synthetic Dataset + Detection)

## Where You're Starting From

Phase 0 is done and proven: real Razorpay order → payment link → payment → webhook → DB update → audit trail, all working end-to-end against Neon, with signature verification and idempotency confirmed correct. See `CHAT_SUMMARY.md` for the full Day 1 record, including two real bugs found and fixed (silent signature bypass, wrong event-ID source).

## Goal for Today

Build a reproducible synthetic dataset of at-risk transactions, and a detector that scores/flags which ones need recovery action. No AI yet — this is deterministic logic and data generation. The agent (Phase 2) will consume what you build today.

**Exit condition:** You can run one command and get a batch of ~1,000 synthetic transaction events, each with realistic failure/risk signals, stored in the database, with a detector that correctly flags which ones are "at risk" and why — no LLM involved yet.

---

## Explicitly Out of Scope Today

- ❌ LLM / AI reasoning of any kind
- ❌ Recovery agent or policy engine
- ❌ Dashboard / frontend
- ❌ Wiring detection results back into real Razorpay actions
- ❌ Buying any AI API credits

Today is data + deterministic detection logic only.

---

## Step-by-Step Checklist

### 1. Design the Synthetic Event Model

Decide what a synthetic "revenue-at-risk" event looks like. Base it on the real webhook payload shapes you already saw in Phase 0 (`payment.captured`, `payment.failed`, `payment_link.paid`) so the synthetic data is structurally realistic, not invented from scratch.

At minimum, each synthetic transaction needs:
- `amount_paise`
- `status` at time of generation (`failed`, `authorized_not_captured`, `abandoned_checkout`, `succeeded`)
- `failure_reason` (when applicable — e.g. `insufficient_funds`, `card_declined`, `network_error`, `otp_timeout`, `customer_abandoned`)
- `customer_history` signals (e.g. `previous_successful_payments`, `previous_recovery_attempts`) — needed later for recovery-probability judgment, but generate the raw signal now
- `created_at` timestamp (spread over a realistic window, not all identical)

- [ ] Decide the exact schema/fields for a synthetic event (extend this list as needed)
- [ ] Decide the distribution: what % should be `failed`, what % `abandoned`, what % `succeeded` (successes matter too — you need negatives, not just positives, to prove the detector isn't just flagging everything)

### 2. Build the Generator

- [ ] Write a generator script (`generate_synthetic_data.py`) that produces N events (start with 1,000) matching the schema above
- [ ] Use `random.seed()` so the dataset is reproducible — you will want to regenerate the exact same batch multiple times while debugging the detector and, later, the agent
- [ ] Insert generated events into a new table (see schema below) rather than directly mutating your real Phase 0 `transactions` table — keep synthetic data clearly separated from the real Test Mode transactions you already proved

### 3. New Table: `synthetic_events` (or similar)

Keep this additive to your existing schema — don't touch the 4 Phase 0 tables.

```sql
CREATE TABLE synthetic_events (
    id UUID PRIMARY KEY,
    amount_paise INTEGER,
    status VARCHAR,              -- failed, authorized_not_captured, abandoned_checkout, succeeded
    failure_reason VARCHAR,      -- nullable
    customer_ref VARCHAR,        -- synthetic customer identifier, for repeat-customer scenarios
    previous_successful_payments INTEGER DEFAULT 0,
    previous_recovery_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    raw_payload JSONB            -- keep the full synthetic event for inspection/debugging
);

CREATE TABLE detection_results (
    id UUID PRIMARY KEY,
    synthetic_event_id UUID REFERENCES synthetic_events(id),
    at_risk BOOLEAN,
    risk_reason VARCHAR,         -- deterministic explanation, not AI-generated yet
    detected_at TIMESTAMP DEFAULT now()
);
```

- [ ] Add these two tables via a new Alembic migration (don't touch Phase 0 tables/migration)
- [ ] Run `alembic upgrade head`, confirm both tables exist in Neon

### 4. Build the Detector (Deterministic — No AI)

This is rule-based logic, matching the plan's principle from earlier: deterministic code handles clear-cut cases, AI (in Phase 2) handles judgment calls.

Example deterministic rules to start with:
- `status == "failed"` and `failure_reason in ("network_error", "otp_timeout")` → at risk, likely recoverable (transient)
- `status == "failed"` and `failure_reason == "insufficient_funds"` → at risk, lower recovery probability
- `status == "abandoned_checkout"` → at risk, recoverable via reminder/link
- `status == "succeeded"` → not at risk (control group — detector must correctly NOT flag these)
- `previous_recovery_attempts >= 2` → flag separately as "exhausted attempts" (stopping-rule candidate for later)

- [ ] Write `detect_at_risk.py` that reads all `synthetic_events`, applies rules, writes results to `detection_results`
- [ ] Print a summary when run: total events, how many flagged at-risk, breakdown by `risk_reason`

### 5. Sanity-Check the Detector

- [ ] Confirm `succeeded` events are never flagged (0 false positives on the clear-cut control group)
- [ ] Confirm every `failed` / `abandoned_checkout` event gets *some* classification (no silent skips — this bit you yesterday with the webhook event-ID bug, don't let it happen again with detection)
- [ ] Spot-check 5-10 individual rows manually against the rules to confirm the logic matches what you intended

### 6. Basic Metrics Output

- [ ] Write a small script or endpoint that reports: total events processed, count flagged at-risk, breakdown by reason, total `amount_paise` at risk (this previews the "measured money recovered" metric you'll need for the final demo)

---

## Definition of Done — Today

- [ ] Reproducible synthetic dataset generator (seeded, ~1,000 events)
- [ ] Two new tables created via migration, populated with synthetic data
- [ ] Deterministic detector correctly separates at-risk from not-at-risk events
- [ ] Zero false positives on the `succeeded` control group
- [ ] Summary metrics script showing total flagged + amount at risk
- [ ] Everything kept separate from Phase 0's real Razorpay tables/data

If every box is checked, Phase 1 is complete and Day 3 can extend the detector (edge cases, tuning) or move straight into Phase 2 (the actual recovery agent) ahead of schedule, same as Phase 0 finished ahead of plan.
