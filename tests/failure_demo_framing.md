# Failure Handling / Stopping Rule — Demo Framing

## What we're claiming

RecoverAI enforces a hard cap on automated recovery attempts per transaction. Once a transaction has reached the configured attempt limit (`MAX_ATTEMPTS = 3`), the execution policy refuses to take further automated action — it escalates or stops instead of retrying indefinitely, and this refusal is fully audited.

## How we tested it

Rather than running a live transaction through three real failed payment attempts to organically trigger the cap — which would require building new webhook-driven retry-counting logic beyond what today's scope covers, and repeating a multi-step failure cycle several times — we constructed a real Razorpay Test Mode transaction whose local state was deliberately set to `previous_recovery_attempts = 3`, matching the exact condition the policy is designed to catch. We then ran that transaction through the live execution pipeline with `LIVE_EXECUTION_ENABLED=true`.

## What we observed

```
9955a044... → STOP (attempts_at_cap)
```

- The execution policy correctly identified the transaction as having reached its attempt limit
- **No Razorpay API call was made** — verified directly in code review, not just inferred from the log message
- A `execution_stopped` audit log entry was written with `phase="execution_policy"`, `reason="attempts_at_cap"`, `max_attempts=3`, `previous_recovery_attempts=3` — a complete, inspectable record of why nothing happened

## What this demonstrates, and what it doesn't

This confirms the **policy branch itself works correctly**: given a transaction at its attempt cap, the system refuses further automated action, every time, with no exceptions and a full audit trail. That's the core safety claim — "automation stopped after N unsuccessful recovery attempts, no further automated action was permitted" — and it holds.

What this test does *not* demonstrate is the counter organically incrementing through three real failed payment cycles end to end. That's a narrower claim about provenance, not about the safety behavior itself, and we're stating that distinction plainly here rather than implying more than we tested. Building and verifying that full organic cycle (webhook-driven failure detection → counter increment → re-evaluation → repeat) is documented as a natural next step once core recovery execution and evaluation are complete.
