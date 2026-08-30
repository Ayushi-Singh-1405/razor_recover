# Failure Log

Track failures, bugs, and misconfigurations encountered during development.

## Format

| Date | Component | Failure | Root Cause | Fix |
|------|-----------|---------|------------|-----|

## Log

| Date | Component | Failure | Root Cause | Fix |
|------|-----------|---------|------------|-----|
| 2026-08-30 | `backend/run_agent.py` (final insert) | Full 662-event agent run completed in memory, then `psycopg2.OperationalError: SSL connection has been closed unexpectedly` on the final bulk insert — all 662 decisions lost | Decisions accumulated in memory with zero commits during the ~1.5h run; the idle Neon connection was dropped server-side before the write phase | `connect_db()` now enables TCP keepalives (30s idle probe); decisions commit incrementally every 25; `insert_decisions()` reconnects once and retries a batch on `OperationalError` (verified by mock tests, `tests/test_run_agent_durability.py`) |
