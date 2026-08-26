# RecoverAI — Razorpay Hackathon — Session Summary

## Context

Ayu is building for Razorpay's Intern Hiring Hackathon, competing for an internship. Track chosen: **Track 03 — AI Revenue Recovery** (detect revenue at risk → diagnose → intervene → recover, with audit trail, bounded actions, and honest metrics). Timeline: 7 days.

Judging criteria:
- **Problem taste** — did you pick something that matters
- **Build quality** — does it run, is it structured, would you trust it
- **AI judgment** — the right tool in the right place, and where you chose not to use one
- **Failure recovery** — what broke, and what you did about it

## Track & Plan Decisions

- Track 03 chosen over Tracks 01/02/04/05 — best fit for reusing prior agentic-workflow experience (ClauseChain-style bounded loops, audit trails).
- A prior `RAZORPAY_BUILDATHON_PLAN.md` was reviewed and revised (`review_discuss.md`) before Day 1 started. Key changes from that review:
  1. **Neon PostgreSQL from Day 1** (not SQLite) — more credible architecture, still lightweight schema (4-6 tables).
  2. **Provider-agnostic LLM interface** — no AI provider committed yet; OpenRouter planned for Phase 2, not purchased yet.
  3. **Stricter Phase 0 exit condition** — prove the full money-flow loop (order → payment link → payment → webhook → DB → audit log) before writing any AI or dashboard code.

## Stack Locked In

- Frontend: Next.js + TypeScript + Tailwind/shadcn (not yet built)
- Backend: FastAPI + Python
- Database: Neon PostgreSQL
- ORM: SQLAlchemy + Alembic (migrations)
- Payments: Razorpay Test Mode
- AI: Provider-agnostic interface, OpenRouter planned for Phase 2 (not started)
- Agent: Simple Python orchestration (no LangGraph)

## Day 1 (Phase 0) — What Was Built

Repo: `razor_recover`, coded via opencode following a sequential prompt list.

**Prompts executed:**
1. FastAPI project scaffold (`main.py`, `db.py`, `models.py`, `config.py`, `.env.example`, health check)
2. Database models — 4 tables: `transactions`, `recovery_attempts`, `webhook_events`, `audit_logs`. Alembic configured against Neon, hand-written initial migration (JSONB via postgres dialect, UUID PKs).
3. Orders API integration — `POST /transactions/create-test-order` creates a real Razorpay Test Mode order, inserts a `transactions` row, writes `order_created` audit log.
4. Payment Links API integration — `POST /transactions/{id}/create-payment-link` creates a real payment link, updates the transaction, writes `payment_link_created` audit log.
5. Webhook handler — `POST /webhook`, signature verification, idempotency check, DB writes, audit logging.
6. Audit trail viewer — `GET /audit/{transaction_id}`, UUID-typed path param, returns `200 []` when empty (not 404).
7. Regression test script — `test_phase0.py`, checks idempotency, signature rejection, UUID validation, empty audit trail.

**Environment setup completed:**
- Razorpay Test Mode account + API keys
- Neon project + connection string
- ngrok tunnel + Razorpay webhook registered (URL + secret + 3 active events: `payment.failed`, `payment.captured`, `payment_link.paid`)
- Migration applied and verified (`alembic upgrade head`, tables confirmed in Neon)

## Real Bugs Found and Fixed (Day 1)

These are genuine "failure recovery" material for the hackathon submission:

1. **Silent signature-verification bypass.** The webhook handler's `except Exception: return {"status": "ignored"}` around `verify_webhook_signature` meant an invalid/forged signature returned 200 OK instead of being rejected. Fixed to `raise HTTPException(status_code=401, ...)`, with a `webhook_signature_rejected` audit log entry added for security-relevant traceability.

2. **Wrong event-ID source.** Code was reading `payload.get("id", "")` from the JSON body, but Razorpay does not send a top-level `id` in the webhook body — the actual unique identifier is in the `X-Razorpay-Event-Id` HTTP header. This caused every real webhook to silently no-op (`{"status": "ignored"}` with 200 OK) despite passing signature verification. Confirmed via a temporary debug dump of raw payload + headers, then fixed to read `request.headers.get("X-Razorpay-Event-Id", "")`.

Also fixed along the way:
- `create-test-order` / `create-payment-link` had a `500` when a literal placeholder (`{transaction_id}`) was sent instead of a real UUID — this was user error, not a code bug, but it surfaced that the UUID path param wasn't typed. Fixing the `/audit/{transaction_id}` route to use a proper `uuid.UUID` type param turned raw Postgres errors into clean `422` responses.
- Razorpay test card gotcha: the commonly-cited generic test number `4111 1111 1111 1111` was rejected as an unsupported international card. A working domestic Mastercard test number (`5267 3181 8797 5449`) was used successfully instead. Test OTP for card auth: `1234` (worked). Test mobile-number OTP is a real SMS in Test Mode (not simulated).

## End-to-End Verification (Confirmed Working)

Full loop proven live with a real payment (`pay_TUKTg0SaVCeCWG`, ₹4,999):

```
order_created → payment_link_created → revenue_recovered
```

- `transactions.status` correctly flips to `recovered`
- `webhook_events` correctly stores the event once (idempotent — Razorpay's duplicate delivery was deduplicated)
- `audit_logs` shows a clean, ordered trail
- `/audit/{transaction_id}` returns proper JSON, handles missing/invalid UUIDs cleanly, returns `200 []` for no data
- Signature rejection returns a real `401`

**Phase 0 exit condition met. Day 1 complete, on schedule.**

## Day 1 Open Threads — Resolved on Day 2

- `payment_link.entity.reference_id` mismatch was checked at the start of Day 2 (Step 0 of the Day 2 plan) before building anything new on top of Phase 0.
- `webhook_verified` audit log entries are written with `transaction_id=None` by design (they fire before a transaction match is found), so they won't appear in `/audit/{transaction_id}` filtered results — this is expected behavior, not a bug.
- Debug logging (`webhook_debug.json` file writes, extra print statements) was added temporarily to diagnose the event-ID bug and was removed once the fix was confirmed.

## Day 2 (Phase 1) — What Was Built

Before starting Phase 1, a review of the Day 2 plan (external, pasted in by Ayu) recommended 5 improvements, all adopted:
1. Add `ground_truth_*` fields to synthetic data so detector accuracy can actually be measured
2. Separate `at_risk` (candidate for attention) from `recoverability` (worth pursuing) — distinct concepts, not one merged flag
3. Add a dataset validation pass before persisting (catch bad data before debugging the detector)
4. Use a controlled enum for `risk_reason` (not free-form strings) — deterministic system, deterministic reason
5. Produce a baseline report (precision/recall/F1 + revenue-at-risk) that Phase 2's AI-enhanced agent will need to beat

**Repo structure note:** project code lives under `backend/` (not repo root) — `generate_synthetic_data.py`, `detect_at_risk.py`, `evaluate.py`, `config.py`, `models.py`, `db.py` all live there. Scripts must be run from inside `backend/` with the venv active (`source ../venv/bin/activate`).

**Build steps executed:**
1. Verified `_find_transaction_for_payload()` does not rely on `reference_id` — Phase 0 matching logic confirmed sound before building on top of it.
2. New tables added via a fresh Alembic migration (Phase 0's 4 tables untouched): `synthetic_events` (observed fields + `ground_truth_recoverable`, `ground_truth_outcome`, `ground_truth_recovered_amount`) and `detection_results` (`at_risk`, `recoverability` tier, controlled `risk_reason` enum).
3. `generate_synthetic_data.py` — seeded (`--seed 42`, default), generates ~1,000 events across `succeeded` / `failed` (network_error, otp_timeout, insufficient_funds, card_declined) / `abandoned_checkout`, with ground truth baked in. Validates before persisting (status enum, failure_reason consistency, amount > 0, no impossible combos). Confirms reproducibility via checksum across repeated runs with the same seed.
4. `detect_at_risk.py` — deterministic rule-based detector, reads only observed fields (never ground truth), writes to `detection_results`.
5. `evaluate.py` — joins detection results back to ground truth, computes precision/recall/F1, checks for false positives on the `succeeded` control group, reports revenue at risk, writes `backend/reports/day2_baseline.txt`.

## Real Bugs Found and Fixed (Day 2)

1. **Bulk insert timeout against Neon.** Initial `executemany`-style insert of 1,000 rows timed out (only 610/1000 rows landing across earlier partial runs). Root cause: individual round-trips over Neon's connection latency. Fixed by switching to `psycopg2.extras.execute_values` for a single multi-row `INSERT ... VALUES` — 1,000 rows in ~4.2s. Applied to both `generate_synthetic_data.py` and `detect_at_risk.py`.
2. **Rule-priority bug in the detector.** The `EXHAUSTED_ATTEMPTS` rule (`previous_recovery_attempts >= 3`) was checked before `status == "succeeded"`, meaning a payment that actually succeeded (after 3+ prior attempts) was being misclassified as `at_risk=True`. Caught because `NOT_AT_RISK` count (316) didn't match the generator's `succeeded` count (332) — a 16-row discrepancy. Fixed by making the `succeeded` check short-circuit first, before any other rule. Confirmed fixed: `NOT_AT_RISK` now equals exactly 332, and the five `risk_reason` counts sum to exactly 1000.

## Day 2 Baseline Results (Confirmed)

Full run against 1,000 seeded synthetic events:

```
Confusion Matrix: TP=472, FP=196, TN=332, FN=0
Precision: 0.7066
Recall:    1.0000
F1 Score:  0.8281

Sanity check — succeeded events flagged at_risk=True: 0 (PASS)

Total revenue:           ₹10,052,456
Revenue at risk:         ₹6,721,189 (66.9%)

Ground-truth recoverable events (472 total):
  Assigned high/medium recoverability: 370 (78.4%)
  Assigned low/none recoverability:    102 (21.6%)
```

**Interpretation:** Recall = 1.0 means the deterministic detector misses zero genuinely recoverable events (safe failure mode). Precision = 0.71 reflects an expected limitation, not a bug — the ruleset can flag something as `at_risk` correctly but can't always judge whether it's actually worth pursuing (e.g. the intentionally-uncertain 50/50 split built into `insufficient_funds`/`card_declined` events, and `EXHAUSTED_ATTEMPTS` cases). This gap is the intended opening for Phase 2: AI-driven triage on *which* at-risk events are worth a recovery attempt, not detection itself. Baseline (`F1 = 0.83`) is the number the AI-enhanced agent needs to beat, saved to `backend/reports/day2_baseline.txt`.

**Phase 1 exit condition met:** reproducible 1,000-event dataset (seed 42) → detector → evaluation, all working end to end. Day 2 complete.

## Open Threads / Notes for Later

- Detector's `LOW_RECOVERY_PROBABILITY` tier intentionally mixes truly-recoverable and not-recoverable events 50/50 in the synthetic data (simulating real-world uncertainty) — this is a deliberate design choice, not a gap, and is the main driver of the 196 false positives.
- Distribution from the generator is slightly `failed`-heavy (48.8% vs. an intended ~45%) — cosmetic, not revisited.
