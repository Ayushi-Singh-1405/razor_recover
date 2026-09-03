# Revoco

Agentic payment recovery for failed Razorpay checkouts.

Revoco detects at-risk payments, reasons about why they failed, and recovers
the ones worth recovering — while a deterministic policy gate keeps every
action safe, bounded, and fully audited.

**AI reasons. Policy decides. Execution is controlled.**

## How it works

```
Payment Failure
      ↓
Detect → Diagnose → Decide
      ↓
Policy Gate (deterministic, authoritative)
      ↓
Recover / Escalate to merchant
      ↓
Audit
```

- **Detection** — a deterministic detector flags at-risk payments from observed
  signals only (status, failure reason, recovery-attempt history).
- **Diagnosis & decision** — a recovery agent receives richer permitted context
  (customer history, order-value deviation, checkout behavior) and recommends
  one of five bounded actions.
- **Policy gate** — attempt caps, amount ceilings, action whitelists, and
  confidence floors are enforced by code that cannot be overridden.
- **Evaluation** — the agent is graded in rupees recovered against a
  pre-registered deterministic benchmark on identical events. Ground truth is
  never visible to the agent or the detector.

## Pages

| Route | Description |
|---|---|
| `/` | Public product landing page |
| `/login` | Google sign-in |
| `/dashboard` | Live execution (real Test Mode recovery runs), System Status |
| `/analytics` | Detection benchmark + agent-vs-benchmark evaluation with charts |
| `/audit` | Filterable chronological audit trail |
| `/developers` | API reference, decision schema, policy gates |
| `/security` | Auth model, execution safety, evaluation integrity |
| `/resources` | Policies, evaluation reports, repository |

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | — | Health check |
| GET | `/auth/google/login` | — | Redirect to Google consent |
| GET | `/auth/google/callback` | — | OAuth callback → session cookie |
| GET | `/auth/me` | session | Current merchant (401 otherwise) |
| GET | `/auth/logout` | — | Clears the session |
| POST | `/transactions/create-test-order` | — | Razorpay Test Mode order |
| POST | `/transactions/{id}/create-payment-link` | — | Razorpay payment link |
| POST | `/webhook` | signature | Razorpay webhook (verified, idempotent) |
| GET | `/audit/{transaction_id}` | — | Audit trail for a transaction |
| GET | `/dashboard/summary` | session | Detection + execution + evaluation payload |
| POST | `/dashboard/escalations/{id}/approve` | session | Merchant approves an escalation |
| POST | `/dashboard/escalations/{id}/dismiss` | session | Merchant dismisses an escalation |

## Project structure

```
frontend/            Static pages (vanilla JS ES modules) + theme.css
backend/
  main.py            FastAPI app (pages, auth wiring, summary, webhooks)
  auth.py            Google OAuth + JWT sessions
  dashboard_actions.py  Escalation approve/dismiss
  run_agent.py       Recovery agent runner (policy gates, retries, resume)
  llm_provider.py    OpenRouter structured-decision client
  generate_synthetic_data.py   Seeded benchmark dataset + ground truth
  detect_at_risk.py  Baseline detector (limited observable signals)
  evaluate.py / simulate_outcomes.py / execute_recovery.py
  GROUND_TRUTH_POLICY.md / EXECUTION_POLICY.md
  alembic/           migrations 001-006
  reports/           evaluation reports
tests/               smoke, durability, summary-verification suites
docs/                architecture, specs, workflow plans
```

## Run locally

```bash
python -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env            # add Razorpay, Neon, Google, JWT secrets
cd backend && ../venv/bin/alembic upgrade head
../venv/bin/uvicorn main:app --reload
# open http://localhost:8000/
```

Environment variables: see `.env.example` (Razorpay Test Mode keys, Neon
PostgreSQL URL, Google OAuth client, `JWT_SECRET`, execution-policy caps).

## Documentation

- [GROUND_TRUTH_POLICY.md](backend/GROUND_TRUTH_POLICY.md) — benchmark rules,
  information separation, simulation economics
- [EXECUTION_POLICY.md](backend/EXECUTION_POLICY.md) — what the execution layer
  may do with real money
- [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) — system architecture
- [CHANGELOG.md](CHANGELOG.md) — release history
- [LEARNING_LOG.md](LEARNING_LOG.md) — failures and what they changed

## License

MIT — see [LICENSE](LICENSE)
