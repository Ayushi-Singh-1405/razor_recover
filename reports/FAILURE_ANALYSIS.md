# Failure Analysis

What broke during the build, why, and what changed because of it. Recorded
per layer — security, integration, business logic, infrastructure, LLM I/O,
data model, deployment. Full raw detail: [LEARNING_LOG.md](../LEARNING_LOG.md).

The pattern across all of these: **we verified every step instead of trusting
first output** — and every verification caught something.

## 1. Security — silent signature bypass

**What broke:** webhook signature verification failures returned 200 instead
of 401. A forged webhook would have been processed as a valid payment event.

**Root cause:** the verification call's result was never checked before
proceeding.

**Fix:** invalid signatures now raise 401 and write a
`webhook_signature_rejected` audit entry. Verified in `tests/test_phase0.py`.

## 2. Integration — wrong event-id source

**What broke:** the webhook deduplication read the event id from the JSON
body — Razorpay puts it in the `X-Razorpay-Event-Id` header. Every real
webhook silently no-op'd.

**Root cause:** wrong assumption about the provider's contract, never
verified against a live webhook.

**Fix:** event id read from the header, used as the primary key of
`webhook_events` for dedup. Verified in `tests/test_phase0.py`.

## 3. Business logic — detector rule priority

**What broke:** `EXHAUSTED_ATTEMPTS` was evaluated before
`status == "succeeded"`, so 16 transactions that had succeeded despite 3+
prior attempts were misclassified as at-risk (EXHAUSTED_ATTEMPTS 50 instead
of 34; NOT_AT_RISK 316 instead of 332).

**Root cause:** rule-ordering assumption. Caught by cross-checking detector
counts against the generator's own counts — 332 + 265 + 203 + 166 + 34
reconciles to exactly 1,000.

**Fix:** the succeeded check short-circuits first.

## 4. Infrastructure — silent Neon connection drops

**What broke (twice, two layers):**

- A full 662-event agent run completed in memory, then the final bulk write
  hit `SSL connection has been closed unexpectedly` — Neon had dropped the
  idle connection. All 662 decisions lost.
- Later, the deployed API layer returned 500/hangs on authenticated
  requests for the same reason: dead pooled connections handed to handlers.

**Root cause:** SQLAlchemy engine without pool validation or keepalives;
Neon silently closes idle connections and suspends free-tier compute.

**Fix:** TCP keepalives + `pool_pre_ping` + `pool_recycle` on the engine;
incremental commits (every 25 decisions); reconnect-and-retry on dropped
connections; a keep-warm thread so Neon never suspends mid-demo. Verified by
`tests/test_run_agent_durability.py`.

## 5. LLM I/O — free-router model output variance

**What broke:** the `openrouter/free` router routes across arbitrary free
models. Two failure shapes appeared: truncated JSON (valid reasoning,
missing closing brace) and reasoning-only responses (`content: None` with
the decision in `message.reasoning`).

**Fix:** 429 rate limits retried with exponential backoff (2s/4s/8s);
non-retryable failures fall through to a safe escalation decision with the
error recorded; the provider falls back to `message.reasoning` when
`content` is empty. Model + retry count recorded in every audit entry.

**Impact honestly stated:** one recoverable ₹9,799 was lost to a format
failure in the 15-event sample — format robustness is a real cost of
model-agnostic routing.

## 6. Data model — agent decisions and demo transactions don't overlap

**What broke:** the new Agent Decision viewer had nothing to show —
`agent_decisions` rows link to `synthetic_events`, while the demo
transactions live in `transactions`. The demo scenarios were decided by the
deterministic execution policy; the LLM was never invoked on them.

**Fix:** a read-only recommendation pass (`agent_recommendations.py`) runs
the agent on each demo transaction and records the structured reasoning as
an `agent_recommendation` audit entry — idempotent, model-attributed, no
Razorpay calls. The dashboard renders it per row.

## 7. Deployment — environment-driven redirect mismatch

**What broke:** Google sign-in on the deployed app returned 400
`redirect_uri_mismatch` — the login flow built its redirect URI from the
localhost default because `APP_BASE_URL` was unset in the deployment
environment.

**Fix:** `APP_BASE_URL` / `FRONTEND_URL` set to the deployment URL; the
callback URI registered in Google Cloud Console. Caught by reading the
`redirect_uri` parameter on the consent-screen redirect.

## 8. Policy labeling — amount-above-cap was mislabeled

**What broke:** amount-over-cap transactions were labeled STOP — semantically
wrong: over-cap needs human judgment, it is not a terminal state.

**Fix:** relabeled to ESCALATE in code and policy; hard stops reduced to
attempts-at-cap and already-recovered. The audit trail deliberately shows
the correction (STOP -> ESCALATE) — see the dashboard's Live Execution rows.

## Verification culture

These were caught by mechanisms, not luck:

- Detector counts cross-checked against generator counts (caught bug 3)
- Pass/fail assertions on webhook behavior (caught bugs 1-2)
- Report cross-checking: summary numbers vs written reports, every run
  (caught the analytics regressions)
- Incremental commits + reconnect-retry (bounds the damage of the drops)
- Idempotent, audited operations (so retries never double-execute)

See [LEARNING_LOG.md](../LEARNING_LOG.md) for the complete incident table
and [../tests/](../tests/) for the suites.
