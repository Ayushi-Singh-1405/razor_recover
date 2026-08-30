# RecoverAI — Execution Policy

## Purpose

This document defines the policy that governs **real recovery actions** — creating and sending actual Razorpay payment links to real customers.

RecoverAI separates three layers that must not be conflated:

1. **Decisions** — what the system thinks should happen (deterministic baseline rules, AI agent recommendations). In the current benchmark, decisions are recorded, never executed.
2. **Evaluation** — what would have happened, measured against synthetic ground truth (`GROUND_TRUTH_POLICY.md`).
3. **Execution** — what the system is actually allowed to *do* against real customers and real money.

This document governs layer 3. It is deliberately more conservative than the decision layers, because execution touches real customers and has real costs.

The configuration values referenced here live in `backend/execution_config.py` and can be overridden via environment variables (see `.env.example`).

---

## Confirmation: Where the Recoverability Tiers Come From

> **recoverability tiers used below are computed by the Phase 1 deterministic detector (detect_at_risk.py) from three observed fields only — status, failure_reason, previous_recovery_attempts. Ground-truth fields and enriched-context fields (customer_tenure_days, checkout_duration_seconds, etc.) are never read outside of evaluation/simulation code. The detector's recoverability domain is {high, low, none} — it never emits a "medium" tier.**

The tier for a transaction is read from `detection_results.recoverability`, produced by `backend/detect_at_risk.py`. It is an *observed-signal* classification, not a prediction of recovery value and not a ground-truth label.

---

# 1. Inputs to the Execution Decision

For each at-risk transaction, the execution layer may use:

### `detection_results.recoverability`

The detector tier: `high`, `low`, or `none`.

### `synthetic_events` / transaction amount

The transaction amount, compared against `MAX_AUTOMATED_AMOUNT_PAISE`.

### `previous_recovery_attempts`

The number of recovery attempts already made, compared against `MAX_ATTEMPTS`.

### Transaction status

Whether the transaction is already `recovered` (via the live webhook path).

Nothing else. Enriched-context fields and ground-truth fields are never inputs to execution.

---

# 2. Tier-to-Action Mapping

## 2.1 HIGH recoverability → ACTION

A `high` tier means the detector saw a transient, plausibly recoverable failure.

```text
recoverability == "high"
        ↓
ACTION: create and send a Razorpay recovery payment link
        ↓
but only if the transaction passes every hard stop in Section 3 and
the amount escalation check in Section 4
```

ACTION is the only tier that may produce a real payment link. Being permitted by tier is necessary but not sufficient — the hard stops always apply.

## 2.2 LOW recoverability → ESCALATE

A `low` tier means the detector saw a failure with poor recovery odds (`insufficient_funds`, `card_declined`).

```text
recoverability == "low"
        ↓
ESCALATE to merchant human review
        ↓
never auto-create a payment link
```

The system may not spend a real intervention on a low-odds transaction. A human decides.

## 2.3 NONE recoverability → STOP

`none` means no recovery should be pursued (transaction succeeded, or attempts exhausted).

```text
recoverability == "none"
        ↓
STOP — do nothing, do not contact the customer
```

---

# 3. Hard STOP Conditions (checked before ANY action, regardless of tier)

Exactly two conditions are true hard stops. They are checked first, for every transaction, even `high` tier. A hard stop can never be overridden by tier, by the AI agent, or by configuration laziness — and it means "done: no further automated action is ever needed for this transaction."

## 3.1 Recovery attempts at cap

```text
previous_recovery_attempts >= MAX_ATTEMPTS
        → STOP
```

Default cap: `MAX_ATTEMPTS = 3`. This matches the detector's `EXHAUSTED_ATTEMPTS` rule and the agent's pre-filter — three independent layers enforce the same limit, which is intentional defense in depth.

## 3.2 Transaction already recovered

```text
transaction status == "recovered"
        → STOP
```

If the live webhook path already marked the transaction recovered (the customer paid), sending a recovery link is at best redundant and at worst embarrassing. Never re-intervene on recovered revenue.

---

# 4. Amount Escalation — ESCALATE, not STOP

```text
amount_paise > MAX_AUTOMATED_AMOUNT_PAISE
        → ESCALATE to merchant human review
```

Default ceiling: `MAX_AUTOMATED_AMOUNT_PAISE = 500000` (₹5,000). This is intentionally stricter than the AI agent's ₹18,000 escalation threshold — real money deserves a lower ceiling than benchmark decisions.

An above-ceiling transaction is **not** a hard stop: unlike exhausted attempts or an already-recovered payment, nothing about it is "done." It is a case that needs human judgment. The execution layer therefore records it as `execution_escalated` (reason: `amount_above_cap`), makes no Razorpay call, and moves on — the same ESCALATE semantics as low recoverability (§2.2) and the same labeling used in `demo_scenarios.py`.

---

# 5. Volume Cap on Real Actions

Even permitted ACTIONs are rate-limited:

```text
number of real payment links sent per execution run <= MAX_REAL_RECOVERY_ACTIONS
```

Default: `MAX_REAL_RECOVERY_ACTIONS = 10`.

A bug, a bad deploy, or a misconfigured detector must not be able to blast hundreds of real customers. If the cap is reached, remaining transactions are left for the next run and reported.

---

# 6. Master Switch: Live Execution

```text
LIVE_EXECUTION_ENABLED = False   (default)
```

Real execution is **disabled by default**. The flag becomes `True` only when the environment variable `LIVE_EXECUTION_ENABLED` is explicitly set to the string `true` (case-insensitive). Any other value — including `1`, `yes`, or an empty string — keeps it `False`.

With the switch off, the execution layer may compute what it *would* do (and log it), but must not create or send any real payment link. This is the "dry-run by default" guarantee: no configuration drift or missing env var can ever turn on live customer contact accidentally.

---

# 7. Configuration Reference

| Constant | Default | Env override | Meaning |
|---|---|---|---|
| `MAX_REAL_RECOVERY_ACTIONS` | `10` | `MAX_REAL_RECOVERY_ACTIONS` | Max real payment-link sends per execution run |
| `MAX_AUTOMATED_AMOUNT_PAISE` | `500000` | `MAX_AUTOMATED_AMOUNT_PAISE` | Transactions above this (₹5,000) escalate for human review — never auto-actioned, never stopped |
| `MAX_ATTEMPTS` | `3` | `MAX_ATTEMPTS` | Recovery-attempt cap; at/above this is a hard STOP |
| `LIVE_EXECUTION_ENABLED` | `False` | `LIVE_EXECUTION_ENABLED` | Master switch; only the exact string `true` enables it |

Defaults are conservative and fixed before any live run. They must not be relaxed after observing results without documenting the reason (same integrity rule as `GROUND_TRUTH_POLICY.md` §19).

---

# 8. Relationship to the AI Agent and the Benchmark

- The AI agent (Phase 2) *recommends* actions; the execution policy *decides* what may really execute. The agent cannot authorize a real payment link by recommendation alone — the same principle as the benchmark's policy gate (`AI = reasoning, Policy = authority, Execution = controlled`).
- In the current benchmark configuration, all agent decisions are recorded to `agent_decisions` and evaluated against synthetic ground truth; nothing executes. This policy governs the future live execution layer, whose implementation must read `execution_config.py` and obey Sections 2–5 exactly.
- A `low` tier may still appear in agent benchmark decisions — that is fine, because benchmark decisions are not executions. At execution time, `low` always escalates.

---

# 9. Auditability Requirements

Every real action (or refused action) taken under this policy must be recorded:

- which transaction, which tier, which action,
- which hard stops fired (if any),
- the run in which it happened.

The existing `recovery_attempts` and `audit_logs` tables are the designated audit points. An execution layer that acts without an audit trail is non-compliant with this policy, regardless of outcome.

---

# 10. What This Policy Does Not Cover

- **Decision quality** — whether `high`/`low`/`none` are the *right* tiers is the detector's concern (`GROUND_TRUTH_POLICY.md` §10); whether AI recommendations improve outcomes is the Gate B experiment's concern.
- **Ground truth and simulation** — Sections 20.7/20.8 of the ground truth policy govern benchmark accounting only; execution outcomes in the live path will be real webhook results (`payment_link.paid` / `payment.captured`), not simulations.

---

## Final Principle

Execution is the only layer that touches real customers. It runs on the most conservative rules, the smallest amount ceiling, the tightest attempt cap, a hard volume limit, and a master switch that is off unless a human explicitly turns it on.

```text
tier says maybe  →  hard stop says no                        →  nothing happens
tier says maybe  →  over the amount ceiling                  →  escalate to a human
tier says maybe  →  stops clear, under ceiling, cap has room,
                    switch on                                →  act, and log it
```

When in doubt, do not execute. Escalate instead.
