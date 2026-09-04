# Application Workflow

How Repechage processes payment events end to end: the recovery pipeline, the
request lifecycles, and the event/audit flow. Component details live in
[ARCHITECTURE.md](../architecture/ARCHITECTURE.md); data model in
[DATABASE.md](../architecture/DATABASE.md).

## 1. Recovery pipeline (batch + live)

```
Payment Failure
      |
      v
Detect ........... deterministic detector, observed signals only
      |
      v
Diagnose ......... recovery agent (LLM), enriched permitted context
      |
      v
Decide ........... one of five bounded actions + confidence
      |
      v
Policy Gate ...... deterministic, authoritative, no override
      |
      +------------+------------+
      v                         v
   Recover                 Escalate to merchant
      |                         |
      v                         v
Razorpay payment link     Approve / Dismiss (audited)
      |
      v
Webhook (payment_link.paid)
      |
      v
Audit + Recovery measurement
```

Every stage writes an audit entry. The audit trail is append-only and is the
source for the dashboard's Live Execution and Audit pages.

## 2. Agent decision pipeline (per event)

```
Observed signals (status, failure_reason, previous_recovery_attempts)
      |
      v
Pre-filter gates
      attempts >= 3 ......... STOP (hard)
      amount > Rs 5,000 ..... ESCALATE
      |
      v
Prompt (enriched permitted context, no ground truth)
      |
      v
LLM (OpenRouter, structured JSON, schema-validated)
      |
      v
Post-filter gates
      invalid action ........ ESCALATE
      confidence < 0.5 ...... ESCALATE
      |
      v
Decision recorded (agent_decisions)
```

429 rate limits are retried with exponential backoff (2s/4s/8s, max 3).
Non-retryable failures fall through to a safe `escalate_to_merchant` decision.

## 3. Request lifecycles

### Sign-in (Google OAuth)

```
/auth/google/login  ->  Google consent  ->  /auth/google/callback?code=...
      ->  code exchange (server-side)
      ->  profile fetch (email, name)
      ->  merchant upsert (merchants table)
      ->  HS256 JWT (24h) in httpOnly recoverai_session cookie
      ->  redirect /dashboard
```

Every protected page/route verifies the cookie via
`get_current_merchant`; missing/expired/forged sessions return 401 and
the browser redirects to `/login`.

### Dashboard load

```
GET /auth/me            -> identity (401 -> /login)
GET /dashboard/summary  -> one payload:
     detection .......... total events, at-risk count, revenue at risk
     real_execution ..... 9 demo transactions + audit chains + recovered
     agent_evaluation ... agent vs benchmark + verdict
```

Aggregate queries run in a single round trip; the payload is cached for
30 seconds (repeat loads are instant). Execution runs and merchant actions
take effect within one TTL window.

### Escalation resolution

```
ESCALATE row on /dashboard
      |
      +-- Approve -> POST /dashboard/escalations/{id}/approve
      |                 creates a real Razorpay payment link
      |                 audits execution_action_taken
      |                 (triggered_by: merchant_manual_approval)
      |
      +-- Dismiss -> POST /dashboard/escalations/{id}/dismiss
                        audits merchant_dismissed, no Razorpay call
```

Preconditions for both: the transaction's latest execution event must be
`execution_escalated`. Hard-stopped transactions refuse with 409 — hard
stops have no override.

## 4. Execution run flow (batch)

```
execute_recovery.py (LIVE_EXECUTION_ENABLED=true)
      |
      v
For each demo transaction:
  classify (detector rules) -> hard stops -> tier decision
      |
      +-- high + within limits -> create payment link (Razorpay)
      +-- over cap -------------> ESCALATE (no Razorpay call)
      +-- attempts at cap ------> STOP (no Razorpay call)
      +-- recovered ------------> STOP (no Razorpay call)
      |
      v
Audit entry per outcome; decisions committed every 25
```

Repeat runs skip transactions that were already actioned and later recovered
via webhook — their lifecycle is complete and fully audited.

## 5. Event and audit flow

| Event | Written when | Key details |
|---|---|---|
| order_created | Test Mode order created | order id, amount |
| payment_link_created | Recovery payment link created | link id, short URL |
| demo_scenario_state_applied | Demo scenario state set locally | scenario, status, reason, attempts |
| agent_recommendation | Read-only agent reasoning pass | diagnosis, action, probability, confidence, model |
| execution_action_taken | Payment link created under policy | link id, triggered_by |
| execution_stopped | Hard stop fired | reason (attempts_at_cap / already_recovered) |
| execution_escalated | Sent to human judgment | reason (amount_above_cap / low_recoverability) |
| execution_capped | Run volume cap reached | actions taken, cap |
| execution_action_failed | Payment link creation failed | error |
| merchant_dismissed | Merchant dismissed an escalation | dismissed_by |
| webhook_verified | Valid Razorpay webhook accepted | event id, type |
| webhook_signature_rejected | Invalid signature | signature prefix |
| revenue_recovered | Webhook confirmed a paid recovery link | event id, amount |

The `phase` field inside each details payload identifies the owning layer
(`execution_policy`, `agent_reasoning`), separating infrastructure failures
(`llm_call_failed`) from model-quality issues (`low_confidence`).
