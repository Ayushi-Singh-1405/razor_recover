# Changelog

All notable changes to **Repechage** (formerly RecoverAI) will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.5.0] — Dashboard V2 & Merchant Auth (2026-08-31)

### Added
- Google OAuth login with HS256 JWT sessions (httpOnly `recoverai_session` cookie, 24h expiry); `merchants` table (migration 006)
- `get_current_merchant` dependency; `/auth/me` and `/auth/logout` endpoints
- Public Repechage landing page at `/` (product overview, static pipeline diagram and dashboard preview)
- Analytics page: stat tiles, hand-rolled SVG charts (recovery trend, failure reasons, outcome donut, agent-vs-benchmark comparison, amount exposure by decision), detailed evaluation table with verdict
- Audit page: filterable chronological audit trail across all demo transactions
- Developers page (API reference, decision schema, policy gates) and Security page (auth model, execution safety, evaluation integrity)
- Shared frontend JS modules (`api`, `state`, `utils`, `navigation`, page modules) — ES modules, no framework or bundler
- Top navigation with active-link states; Resources/Security content pages

### Changed
- Dashboard slimmed to markup + page module; logic moved to shared JS modules
- Branding unified to lowercase `repechage`; UI typography moved to Inter / Inter Tight (Google Fonts, system fallbacks)
- `/` now serves the public landing page (previously redirected to `/login`)
- `FAILURE_LOG.md` renamed to `LEARNING_LOG.md`
- `/dashboard/summary` transaction entries now include `failure_reason` (additive)

### Fixed
- Agent Evaluation detail table rendering regression (restored live values instead of placeholders)
- Amount-exposure visualization showed normalized ratios instead of ₹ amounts

### Security
- Session JWTs signed server-side; secrets held in environment variables only; httpOnly + SameSite cookie flags

## [0.4.0] — Execution Layer & Merchant Oversight (2026-08-30)

### Added
- `EXECUTION_POLICY.md` and `execution_config.py`: tier-to-action mapping, hard stops (attempt cap, already-recovered), amount ceiling escalation, per-run volume cap, live-execution master switch — all env-overridable
- `execute_recovery.py`: policy-gated live execution creating real Razorpay payment links, with per-decision audit entries (`execution_action_taken` / `execution_stopped` / `execution_escalated` / `execution_capped`)
- `demo_scenarios.py` + `demo_scenarios_extra.py`: 9 real Test Mode orders covering every execution-policy branch
- Merchant oversight: `POST /dashboard/escalations/{id}/approve` and `/dismiss` (409 on non-escalated or hard-stopped transactions; all decisions audited)
- `GET /dashboard/summary`: detection, real-execution and agent-evaluation blocks for the dashboard
- `transactions.failure_reason` and `transactions.previous_recovery_attempts` columns (migration 005)
- Live Execution and System Status sections on the dashboard

### Changed
- Amount-over-cap outcomes relabeled from STOP to ESCALATE (needs human judgment, not a terminal state) — code and policy updated together
- Transactions already recovered after an executed action are skipped on repeat execution runs instead of accruing duplicate audit entries

### Fixed
- Amount-exposure and recovery outcomes no longer expose normalized chart values (₹ amounts displayed)

## [0.3.0] — Agent Reliability (2026-08-30)

### Added
- Retry with exponential backoff (2s/4s/8s, max 3) on 429 rate-limit failures only; non-retryable errors fail straight through to the safe escalation path
- Per-event retry tracking with a run-level "LLM Retry Summary"
- `--resume` flag: batched full-dataset runs that keep existing decisions and process only undecided events
- `--limit N` dry-run support
- Incremental decision commits (every 25), TCP keepalives, and reconnect-and-retry on dropped connections
- Mock-based durability test suite (`tests/test_run_agent_durability.py`)

### Changed
- LLM provider chain consolidated to OpenRouter only (dead Puter/AgentRouter endpoints removed; chain remains provider-agnostic)
- `OPENROUTER_MODEL` switchable via environment (`openrouter/free` used for the full benchmark run)

### Fixed
- Long agent runs no longer lose completed work to stale connections: a full 662-event run had been lost when Neon dropped an idle SSL connection before the final write (see `LEARNING_LOG.md`)

## [0.2.0] — Recovery Agent & Gate B Evaluation (2026-08-29)

### Added
- Recovery agent runner (`run_agent.py`): deterministic pre-filter gates (attempt cap, high-value escalation), LLM structured decisions, post-filter safety gates (confidence floor, action whitelist), full persistence to `agent_decisions`
- LLM provider module (`llm_provider.py`): OpenAI-compatible calls, JSON-schema validation, typed error taxonomy
- Gate B experiment: full 662-event agent run vs deterministic benchmark — decision paths, override reasons (infrastructure vs model quality), targeting quality per action
- Baseline-vs-agent comparison report (`day3_experiment_result.txt`) with fixed simulation economics (₹200 penalty per bad intervention)
- Pinned-model sample evaluation (nemotron, n=15) with same-events comparison against the auto-router run
- Audit-driven verification suite (`tests/dashboard_summary_check.py`)
- Agent Decision model + `agent_decisions` table (migration 004)

## [0.1.0] — Detection Benchmark & Razorpay Plumbing (2026-08-25/28)

### Added
- FastAPI backend: `/health`, Razorpay order and payment-link creation, signature-verified idempotent webhooks, audit-trail endpoint
- SQLAlchemy models + Alembic migrations (001–003): transactions, recovery_attempts, webhook_events, audit_logs, synthetic_events, detection_results with enriched customer-behavior columns
- Seeded synthetic data generator with pre-registered ground-truth policy (`GROUND_TRUTH_POLICY.md`: tier model, probability draw, information separation, simulation economics)
- Deterministic at-risk detector (limited observable signal set) and Day 2 evaluation report (precision/recall/F1, revenue at risk)
- `EXECUTION`/`GROUND_TRUTH` policy documentation and engineering decision log
- Phase 0 smoke tests (`test_phase0.py`)
- Project scaffolding, sprint plans, architecture documentation

### Fixed
- Detector rule priority: `succeeded` status now short-circuits before the exhausted-attempts rule
- Webhook event-id source corrected to the `X-Razorpay-Event-Id` header (body lookups silently no-op'd every real webhook)
- Signature-rejection responses corrected from silent 200 to 401 with audit entry
- Neon bulk-insert timeouts resolved with `execute_values` batching

[Unreleased]: https://github.com/Ayushi-Singh-1405/razor_recover/compare
