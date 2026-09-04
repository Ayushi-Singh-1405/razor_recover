# Engineering Decisions

Why the stack and the approaches were chosen — recorded so future changes
argue against a rationale, not against nothing.

## FastAPI + uvicorn (Python)

- Async-capable, typed validation via Pydantic, automatic OpenAPI docs.
- Sync route handlers run in a threadpool — simple DB code without async
  ceremony, while the webhook endpoint stays responsive.
- Rejected: Flask (no native validation/OpenAPI), Django (heavier than the
  product needs).

## Neon PostgreSQL (free tier) + SQLAlchemy + Alembic

- Server-side Postgres for real relational integrity: deduplication by
  provider event id, foreign keys, JSONB audit payloads.
- Neon's scale-to-zero fits a demo budget; the engine is hardened against
  its failure modes (pool_pre_ping, recycle, TCP keepalives, keep-warm
  thread) after a stale-connection incident cost a full 662-event run.
- Alembic because schema drift broke the detector once (a column set change
  needed versioning, not ad-hoc DDL).

## Vanilla frontend (HTML + ES modules, no framework)

- The product surface is five authenticated pages and one landing page.
- Same-origin serving makes the httpOnly session cookie work without CORS
  or token plumbing.
- A framework would add a build step and a second deployment artifact
  without adding capability. Rejected: React/Next.js/Vite/Tailwind.
- Cost accepted: rendering is template-string based and needs discipline —
  mitigated by shared modules (`api`, `state`, `utils`, `charts`) and a
  syntax check on every module.

## Hand-rolled SVG charts (no chart library)

- Four chart types (line, bars, donut, comparison) with theme-token colors
  in ~200 lines — lighter than any chart dependency and fully consistent
  with the flat design system.
- Rejected: Chart.js/Recharts (extra dependency for four charts, harder to
  keep on-brand).

## OpenRouter with schema-validated structured output

- One provider-agnostic endpoint with model routing; the model is
  configuration, not code.
- Strict JSON-schema validation in `llm_provider.py` with typed errors —
  malformed model output is deterministic to handle (safe escalation), and
  free-router models that answer in `message.reasoning` are supported via a
  fallback.
- Rejected: pinning a single paid model (quota/cost risk), agent frameworks
  (LangGraph etc. — the pipeline is five stages, not a graph).

## Deterministic policy gate between the LLM and money

- The LLM has zero execution authority. Attempt caps, amount ceilings,
  action whitelists, confidence floors, and a master switch are enforced by
  code that cannot be argued with.
- This is the product's core claim: AI reasons, policy decides, execution
  is controlled — and every override is auditable.

## Rupee-based evaluation with a pre-registered benchmark

- Ground truth is generated once from a wider signal set than any system
  sees, is never exposed at decision time, and is protected from post-hoc
  tuning (`GROUND_TRUTH_POLICY.md`).
- Scoring in net rupees (with a flat Rs 200 penalty per bad intervention)
  instead of F1 alone: precision-only metrics reward withholding recovery
  entirely; rupees expose that trade-off honestly. The first full run showed
  the agent losing to the benchmark — reported as-is.

## Audit trail as a first-class feature

- Every decision, gate override, escalation, merchant approval, and
  webhook-confirmed recovery writes an immutable audit entry with a `phase`
  field separating infrastructure failures from model-quality issues.
- JSONB details keep entries self-describing without schema churn.

## execute_values batching + keepalives (Neon-specific)

- SQLAlchemy `executemany` sends row-by-row and times out against Neon on
  1,000-row inserts; `psycopg2.extras.execute_values` cut it to ~4 seconds.
- TCP keepalives + pool_pre_ping + a keep-warm thread after an incident
  where idle-connection drops caused a 500 and a lost 662-event run.

## Mock-based tests without a test framework

- Three standalone suites with their own pass/fail output and a
  `run_all.sh` entry point: durability (mocked DB), summary-vs-reports
  (audit-driven, catches regressions against the written reports), and
  Phase 0 smoke tests (live API).
- Rejected: pytest — the suites predate it and the standalone form runs
  anywhere, including CI, without collection magic.
