# Application Architecture

Repechage is an agentic payment recovery system for failed Razorpay checkouts.
It detects at-risk payments, reasons about why they failed, recovers the ones
worth recovering — and a deterministic policy gate keeps every action safe,
bounded, and fully audited.

Related documents: [DATABASE.md](DATABASE.md) (data model),
[REPOSITORY_MAP.md](REPOSITORY_MAP.md) (repository layout),
[WORKFLOW.md](../workflow/WORKFLOW.md) (request/event lifecycles),
[../engineering-decisions/ENGINEERING_DECISIONS.md](../engineering-decisions/ENGINEERING_DECISIONS.md)
(technology rationale).

## 1. Two subsystems, one origin

| Subsystem | Components | Role |
|---|---|---|
| Live app | `main.py`, `auth.py`, `dashboard_actions.py`, `frontend/` | Public landing, Google OAuth, merchant dashboard, escalation actions, Razorpay webhooks |
| Benchmark pipeline | `generate_synthetic_data.py`, `detect_at_risk.py`, `run_agent.py`, `simulate_outcomes.py`, `evaluate.py`, `agent_recommendations.py`, `execute_recovery.py` | Seeded dataset, detection, agent decisions, live execution runs, evaluation reports |

Both share one PostgreSQL database (Neon) and are served from one FastAPI
process — the frontend is static HTML + ES modules served by the same origin,
which is what allows the httpOnly session cookie to work without CORS.

## 2. End-to-end recovery flow

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

Every stage writes an audit entry. The audit trail is the product's memory:
it separates what the AI thought from what the policy allowed.

## 3. Agent decision pipeline

Implemented in `run_agent.py` (benchmark runner) and mirrored by the live
execution layer in `execute_recovery.py`.

```
Observed signals (status, failure_reason, previous_recovery_attempts)
      |
      v
Pre-filter gates
      attempts >= 3 ......... STOP (hard)
      amount > Rs 5,000 ..... ESCALATE
      |
      v
Prompt (enriched permitted context, never ground truth)
      |
      v
LLM via llm_provider.get_structured_decision
      (OpenRouter, JSON-schema validated, 429 backoff retry)
      |
      v
Post-filter gates
      invalid action ........ ESCALATE
      confidence < 0.5 ...... ESCALATE
      |
      v
Decision persisted (agent_decisions)
```

### Permitted actions

recover_now, send_payment_link, wait_and_retry, escalate_to_merchant, stop.

### Information separation

Three column groups in `synthetic_events` with different consumers:

- Observed signals — baseline detector only
- Enriched context (tenure, AOV deviation, checkout behavior) — agent only
- Ground truth — evaluation/simulation only, never shown to either

This is what prevents circular evaluation: the agent is graded against a
benchmark it cannot see (see `GROUND_TRUTH_POLICY.md`).

## 4. Policy gates (deterministic, authoritative)

| Gate | Rule | Outcome |
|---|---|---|
| Attempts cap | previous_recovery_attempts >= 3 | STOP (hard, no override) |
| Already recovered | transaction status == recovered | STOP (hard, no override) |
| Amount ceiling | amount_paise > 500000 (Rs 5,000) | ESCALATE to human review |
| Action whitelist | only 5 bounded actions possible | anything else ESCALATEs |
| Confidence floor | confidence < 0.5 | ESCALATE |
| Volume cap | 10 real actions per execution run | excess CAPPED |
| Master switch | LIVE_EXECUTION_ENABLED != "true" | no Razorpay calls at all |

The LLM recommends; the policy decides; execution is controlled.

## 5. Reliability decisions

- **Connections**: `pool_pre_ping`, `pool_recycle`, TCP keepalives, and a
  45s keep-warm thread — Neon silently closes idle connections and suspends
  free-tier compute; both failure modes have bitten (see `LEARNING_LOG.md`).
- **Bulk writes**: `execute_values` batching — `executemany` times out on Neon.
- **Incremental commits**: long runs commit every 25 decisions and reconnect
  on dropped connections, so a failure cannot erase hours of work again.
- **429 retries**: exponential backoff (2s/4s/8s, max 3) on rate limits only;
  non-retryable failures fail fast to the safe escalation path.
- **TTL cache**: `/dashboard/summary` aggregates run in one round trip and
  the payload is cached for 30 seconds (repeat page loads are instant).

## 6. Evaluation (Gate B)

The agent and the deterministic benchmark ran over the same 662 at-risk
events under identical fixed economics. Full report:
[../../backend/reports/agent_performance_result.md](../../backend/reports/agent_performance_result.md).

The honest outcome: the agent is more precise per attempt (73% vs 66%,
110 vs 224 bad interventions) but more conservative — net Rs 25.5L vs the
benchmark's Rs 42.4L. The benchmark is retained for real execution; the
agent's reasoning is evaluated, not yet execution-authorized. The learning
log records three real bugs found by verifying instead of assuming.

## 7. Status

| Component | State |
|---|---|
| Razorpay plumbing (orders, links, webhooks, audit) | Implemented |
| Detection benchmark (1,000 events, detector, reports) | Implemented |
| Recovery agent (gates, retries, persistence) | Implemented |
| Gate B evaluation vs benchmark | Implemented |
| Execution layer (policy-gated live actions) | Implemented |
| Merchant auth (Google OAuth + JWT sessions) | Implemented |
| Dashboard V2 (live execution, status, analytics, audit) | Implemented |
| LLM reasoning viewer on dashboard rows | Implemented |
| Deployment (Render blueprint, secure cookies, migrations-on-deploy) | Implemented |
| Agent Decisions viewer data for demo transactions | Implemented (recommendation pass) |
| Payment-method analytics (requires schema addition) | Planned |
| Deployment region co-location check | Implemented (Render US East near Neon us-east-2) |
