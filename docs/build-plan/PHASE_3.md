# Day 4 Plan — RecoverAI (Phase 3: Real Razorpay Execution)

## Where You're Starting From

Phase 0 (real Razorpay plumbing), Phase 1 (deterministic detector, baseline F1 0.80), and Phase 2 (AI experiment, documented and concluded) are all done. The Day 3 experiment produced a clear, honest result: the deterministic baseline recovers more net ₹ (₹42.44L vs ₹25.55L) under the defined cost model, so **the deterministic detector is the system being wired to real actions today** — not the AI agent. See `day3_experiment_writeup.md` for the full reasoning.

## Goal for Today

Take the deterministic detector's `at_risk=True` decisions and, for a small, real, bounded batch, actually execute the recovery action in Razorpay Test Mode — reusing Phase 0's proven plumbing (order/payment-link creation, webhook handling, audit logging) rather than rebuilding it. This closes the loop the plan always pointed toward: `detect → decide → policy gate → real Razorpay action → outcome → audit`.

**Exit condition:** You can point the system at a handful of real (test-mode) at-risk transactions, watch it create real payment links for the recoverable ones, and see the resulting recovery — or a correctly-triggered stop/escalation — show up in a clean audit trail end to end.

---

## Explicitly Out of Scope Today

-  Wiring the AI agent to real actions (per the Day 3 decision, it's documented future work, not today's build)
-  Running this against all 662 at-risk synthetic events for real — Razorpay Test Mode has a **30 Payment Link limit per business**, so today's real-API demo is a small, deliberately chosen batch (10-20 transactions), not the full dataset
-  Dashboard / frontend — still last, per the standing priority order
-  Customer messaging beyond what Razorpay's payment link itself sends

---

## Step 1 — Decide the Real-Execution Policy (Reuse, Don't Reinvent)

You already have a working policy structure from the original master plan (Section 9) and from Phase 2's pre/post-filter pattern. Today's version is simpler since there's no LLM in the loop:

```
detection_results.at_risk == True
        ↓
recoverability tier (from Phase 1 detector)
        ↓
   HIGH / MEDIUM  →  create a real Payment Link (bounded by amount + attempt limits)
   LOW             →  create a real Payment Link only if under a stricter amount cap
   NONE            →  do not attempt; log as "not pursued"
        ↓
   STOP conditions (reuse from the original master plan, Section 9):
     - previous_recovery_attempts already at cap
     - amount exceeds automated-action limit
     - transaction already recovered (shouldn't happen in synthetic data, but guard anyway)
```

- Write this down explicitly (a short section in `GROUND_TRUTH_POLICY.md` or a new `backend/EXECUTION_POLICY.md`) before writing code — same discipline as Phase 2, decide the rule before you see results, not after
- Pick your amount cap and batch size for today's live demo (e.g. ≤ ₹5,000, 15 transactions) — small enough to stay well under Razorpay's 30-link Test Mode ceiling with room for retries/mistakes

## Step 2 — Select a Real Demo Batch

You can't run real Razorpay actions against 662 synthetic rows — those aren't real orders. Today's real-API portion needs **actual new orders created through Phase 0's existing endpoints**, seeded with realistic amounts/scenarios that mirror what the detector would flag.

- Decide: are you (a) creating a handful of brand-new real test orders that mimic at-risk scenarios (simplest, most reliable for a live demo), or (b) trying to replay specific synthetic_events through the real API (more "authentic" but more engineering to bridge synthetic data into real Razorpay calls)? **Recommend (a)** — it's what your original demo flow (Section 17 of the master plan) already describes, and it keeps today's scope tight.
- Pick 3-5 concrete scenarios to demo, mirroring your detector's categories: one `TRANSIENT_FAILURE` (should recover), one `CHECKOUT_ABANDONMENT` (should recover), one `EXHAUSTED_ATTEMPTS` (should stop, no action), one high-value case (should escalate, not auto-act)

## Step 3 — Build the Execution Runner

- Create `backend/execute_recovery.py`: for each demo scenario, reuses Phase 0's `create-test-order` and `create-payment-link` endpoints (or calls the same underlying functions directly rather than going through HTTP, your choice) to actually create real Razorpay Test Mode artifacts
- Apply Step 1's policy gate before calling Razorpay — this is the "deterministic policy gate controls money actions" requirement from the master plan's Definition of Done
- Write an `audit_logs` entry for every decision, including ones that result in **no action** (STOP/escalate) — the audit trail should show *why* nothing happened, not just what did happen
- For the "should stop" and "should escalate" scenarios, confirm the code path genuinely refuses to call Razorpay's API at all — don't just log a stop reason after already creating the link

## Step 4 — Run the Real Batch, Capture the Full Trail

- Run `execute_recovery.py` against your chosen demo batch
- For the "should recover" scenarios: manually complete the test payments (same test card as Phase 0: `5267 3181 8797 5449`, OTP `1234`), let the existing webhook handler pick them up
- Pull `/audit/{transaction_id}` for each scenario and confirm the full story is visible: order created → policy decision → (payment link created, or stop/escalate logged) → (payment received → recovered, if applicable)

## Step 5 — The Failure Demo (Explicitly Required by the Master Plan, Section 13)

Your submission needs one failure handled gracefully, on camera. Reuse Phase 0's proven pattern:

- Pick one scenario, attempt recovery, let the test payment fail (Razorpay documents test cards/flows that simulate failure — or simply let a payment link expire/go unpaid)
- Confirm the system correctly does **not** retry indefinitely — hits the attempt cap, logs a clear STOP reason, and the audit trail shows: *"Automation stopped after N unsuccessful recovery attempts. No further automated action was permitted."* (this is the exact language the master plan asks the dashboard to eventually show — for today, confirming it's true in the audit log/logs is enough, the dashboard rendering comes in Phase 4)

---

## Definition of Done — Today

- Execution policy documented in writing before running anything
- Real Razorpay Test Mode Payment Links created for a small, deliberately chosen batch of recoverable scenarios
- At least one scenario correctly results in **no automated action** (STOP or escalate), with the refusal itself logged
- At least one scenario demonstrates the failure → stop → escalation path end to end
- Full audit trail visible for every scenario in the batch, including the ones where nothing was executed
- Stayed well under Razorpay's 30 Payment Link Test Mode limit

**Target end-of-day milestone:** *"I can point to a handful of real Test Mode transactions and show, end to end in the audit log, exactly why the system acted on some and correctly refused to act on others — including one real failure that stopped safely instead of retrying forever."* That's the master plan's core promise (*"Recover revenue automatically — but never blindly"*) made concrete and demonstrable, not just described.
