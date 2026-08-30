#!/usr/bin/env python3
"""Durability tests for backend/run_agent.py — connection keepalives,
reconnect-and-retry inserts, and incremental flush cadence.

These are mock-based tests (no real database, no network) extracted from
the live debugging of a lost 662-event run on 2026-08-30: decisions were
held in memory for the whole run and the final insert failed on a stale
Neon SSL connection. The fix (keepalives + commit-every-N + reconnect)
is what this suite locks in.

Run from anywhere with the project venv:
    ./venv/bin/python tests/test_run_agent_durability.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

import run_agent as ra

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS  {name}")
        passed += 1
    else:
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))
        failed += 1


class FakeCursor:
    def __init__(self, name="cur"):
        self.name = name
        self.calls = []
        self.closed = False

    def execute(self, q):
        self.calls.append(("execute", q))

    def fetchone(self):
        return (0,)

    def close(self):
        self.closed = True


class FakeConn:
    def __init__(self, name="conn"):
        self.name = name
        self.commits = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def cursor(self):
        return FakeCursor(f"{self.name}.cur")

    def close(self):
        self.closed = True


insert_calls = []
connect_calls = []


def set_execute(side_effects):
    state = {"n": 0}

    def fake_execute_values(cur, query, rows, page_size=None):
        insert_calls.append({"cur": cur, "rows": len(rows), "page_size": page_size})
        effect = side_effects[min(state["n"], len(side_effects) - 1)]
        state["n"] += 1
        if isinstance(effect, Exception):
            raise effect
    return fake_execute_values


def fake_connect():
    connect_calls.append(1)
    return FakeConn(f"new{len(connect_calls)}")


# 1. Success path: no reconnect
insert_calls.clear(); connect_calls.clear()
ra.execute_values = set_execute([None])
conn, cur = FakeConn("c1"), FakeCursor("k1")
out_conn, out_cur = ra.insert_decisions(conn, cur, [("row",)] * ra.BATCH_SIZE)
check("1a same conn/cur returned on success", out_conn is conn and out_cur is cur)
check("1b one execute_values call, BATCH_SIZE rows, matching page_size",
      len(insert_calls) == 1 and insert_calls[0]["rows"] == ra.BATCH_SIZE and insert_calls[0]["page_size"] == ra.BATCH_SIZE)
check("1c one commit", conn.commits == 1)
check("1d no reconnect", connect_calls == [])

# 2. Dead connection on first attempt: reconnect once, retry succeeds
insert_calls.clear(); connect_calls.clear()
orig_connect_db = ra.connect_db
ra.connect_db = fake_connect
ra.execute_values = set_execute([ra.psycopg2.OperationalError("SSL connection has been closed unexpectedly"), None])
conn, cur = FakeConn("c2"), FakeCursor("k2")
out_conn, out_cur = ra.insert_decisions(conn, cur, [("row",)] * ra.BATCH_SIZE)
ra.connect_db = orig_connect_db
check("2a new conn/cur returned", out_conn.name == "new1" and out_cur.name == "new1.cur")
check("2b old resources closed", cur.closed and conn.closed)
check("2c exactly one reconnect", connect_calls == [1])
check("2d two execute_values attempts, retry has BATCH_SIZE rows",
      len(insert_calls) == 2 and insert_calls[1]["rows"] == ra.BATCH_SIZE)
check("2e new conn committed once", out_conn.commits == 1)

# 3. Incremental flush cadence: 250 events -> flush every BATCH_SIZE + final remainder
insert_calls.clear(); connect_calls.clear()
ra.execute_values = set_execute([None])
db_rows = []
for i in range(1, 251):
    db_rows.append(("row",))
    if len(db_rows) >= ra.BATCH_SIZE:
        ra.insert_decisions(conn, cur, db_rows)
        db_rows = []
# post-loop final flush (as main() does for the remainder)
if db_rows:
    ra.insert_decisions(conn, cur, db_rows)
    db_rows = []
committed = sum(c["rows"] for c in insert_calls)
expected_flushes = 250 // ra.BATCH_SIZE + (1 if 250 % ra.BATCH_SIZE else 0)
expected_sizes = [ra.BATCH_SIZE] * (250 // ra.BATCH_SIZE) + ([250 % ra.BATCH_SIZE] if 250 % ra.BATCH_SIZE else [])
check("3a expected number of flushes", len(insert_calls) == expected_flushes, f"got {len(insert_calls)}, want {expected_flushes}")
check("3b flush sizes match BATCH_SIZE cadence", [c["rows"] for c in insert_calls] == expected_sizes)
check("3c all rows flushed", committed == 250)
check("3d max in-memory rows bounded by BATCH_SIZE", all(c["rows"] <= ra.BATCH_SIZE for c in insert_calls))

# 4. connect_db passes keepalive options
captured = {}
orig_connect = ra.psycopg2.connect
def spy_connect(dsn, **kwargs):
    captured["dsn_is_url"] = "postgres" in dsn
    captured.update(kwargs)
    return FakeConn("spy")
ra.psycopg2.connect = spy_connect
ra.connect_db()
ra.psycopg2.connect = orig_connect
check("4a keepalives enabled", captured.get("keepalives") == 1)
check("4b keepalive idle/interval/count set",
      captured.get("keepalives_idle") == 30 and captured.get("keepalives_interval") == 10 and captured.get("keepalives_count") == 5)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
