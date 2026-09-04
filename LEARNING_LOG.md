# Learning Log

The following document consists of the all the bugs and issues that occured during the building process of this application. All the issues  are tracked in the given tabular format.


Track failures, bugs, and misconfigurations encountered during development.

## Format

| Date | Component | Failure | Root Cause | Fix |
|------|-----------|---------|------------|-----|

## Log

| Date | Component | Failure | Root Cause | Fix |
|------|-----------|---------|------------|-----|
| 2026-09-04 | Agent Decision viewer (`backend/main.py`, `agent_recommendations.py`) | The new viewer had nothing to show: `agent_decisions` rows link to `synthetic_events`, but the 9 demo transactions live in `transactions` — no overlap, because they were decided by the deterministic execution policy, never by the LLM | Data-model assumption that "demo transaction" and "benchmark event" shared an identifier | Read-only recommendation pass (`agent_recommendations.py`): LLM reasoning per demo transaction recorded as `agent_recommendation` audit entries (idempotent, model-attributed); no Razorpay calls, no schema change |
| 2026-08-29 | Execution layer (`execute_recovery.py`, `EXECUTION_POLICY.md`) | Amount-above-cap transactions were labeled STOP — semantically wrong: over-cap needs human judgment, it is not a terminal state | Label inherited from an early policy draft | Relabeled to ESCALATE in code and policy; hard stops reduced to attempts-cap and already-recovered |
| 2026-08-31 | FastAPI API layer (`backend/db.py`) | Authenticated dashboard requests returned 500 / hung after the server had been running for a while; fresh processes worked fine | SQLAlchemy engine had no pool pre-ping/keepalives — Neon silently closed idle pooled connections (and suspends compute on the free tier), so requests grabbed dead connections | `db.py` engine hardened (pool_pre_ping, pool_recycle=280, TCP keepalives) + a 45s keep-warm thread so Neon never suspends mid-demo; summary route reduced to one aggregate round trip + 30s TTL cache |
| 2026-08-30 | `backend/run_agent.py` (final insert) | Full 662-event agent run completed in memory, then `psycopg2.OperationalError: SSL connection has been closed unexpectedly` on the final bulk insert — all 662 decisions lost | Decisions accumulated in memory with zero commits during the ~1.5h run; the idle Neon connection was dropped server-side before the write phase | `connect_db()` now enables TCP keepalives (30s idle probe); decisions commit incrementally every 25; `insert_decisions()` reconnects once and retries a batch on `OperationalError` (verified by mock tests, `tests/test_run_agent_durability.py`) |
| 2026-08-30 | `backend/llm_provider.py` | Free-router models produced malformed agent output: one truncated JSON (a recoverable ₹9,799 was lost to the safe fallback) and one response with the valid decision in `message.reasoning` but `content=None` ("empty choices" failure) | `openrouter/free` routes across arbitrary free models; output shape varies and some emit reasoning-only responses | 429s retried with exponential backoff (2s/4s/8s); `llm_provider` falls back to `message.reasoning` when `content` is empty; every audit entry records the model and retry count |
| 2026-08-26 | `backend/generate_synthetic_data.py` | Bulk insert of 1,000 events timed out against Neon (SQLAlchemy `executemany` sends row-by-row over a high-latency link) | Per-row round trips on a remote database | `psycopg2.extras.execute_values` multi-row INSERT (~4s for 1,000 rows); became the project-wide batching pattern |
| 2026-08-25 | `backend/main.py` (webhook) | Two Phase 0 bugs: signature rejections silently returned 200 instead of 401, and the event id was read from the JSON body instead of the `X-Razorpay-Event-Id` header — every real webhook silently no-op'd | Header/source assumptions never tested against a live webhook | 401 + `webhook_signature_rejected` audit entry on bad signatures; event id read from the header with DB dedup as primary key (verified in `tests/test_phase0.py`) |
