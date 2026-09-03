# Learning Log

The following document consists of the all the bugs and issues that occured during the building process of this application. All the issues  are tracked in the given tabular format.


Track failures, bugs, and misconfigurations encountered during development.

## Format

| Date | Component | Failure | Root Cause | Fix |
|------|-----------|---------|------------|-----|

## Log

| Date | Component | Failure | Root Cause | Fix |
|------|-----------|---------|------------|-----|
| 2026-08-25 | 
| 2026-08-31 | FastAPI API layer (`backend/db.py`) | Authenticated dashboard requests returned 500 / hung after the server had been running for a while; fresh processes worked fine | SQLAlchemy engine had no pool pre-ping/keepalives — Neon silently closed idle pooled connections (and suspends compute on the free tier), so requests grabbed dead connections | `db.py` engine hardened (pool_pre_ping, pool_recycle=280, TCP keepalives) + a 45s keep-warm thread so Neon never suspends mid-demo; summary route reduced to one aggregate round trip + 30s TTL cache |
| 2026-08-30 | `backend/run_agent.py` (final insert) | Full 662-event agent run completed in memory, then `psycopg2.OperationalError: SSL connection has been closed unexpectedly` on the final bulk insert — all 662 decisions lost | Decisions accumulated in memory with zero commits during the ~1.5h run; the idle Neon connection was dropped server-side before the write phase | `connect_db()` now enables TCP keepalives (30s idle probe); decisions commit incrementally every 25; `insert_decisions()` reconnects once and retries a batch on `OperationalError` (verified by mock tests, `tests/test_run_agent_durability.py`) |
