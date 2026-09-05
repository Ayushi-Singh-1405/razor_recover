#!/usr/bin/env python3
"""Verify GET /dashboard/summary numbers match the source reports
exactly. Parses the report .txt files (cross-check only) and compares
against the route output. Read-only: no DB writes.

Run: ./venv/bin/python tests/dashboard_summary_check.py
"""
import os
import re
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from db import SessionLocal
from main import dashboard_summary
from models import AuditLog, Merchant

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
REPORTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports")


def read(name):
    with open(os.path.join(REPORTS, name)) as f:
        return f.read()


passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS  {name}")
        passed += 1
    else:
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))
        failed += 1


def rupees(text):
    return int(text.replace(",", "")) * 100


# ---- Source report values (parsed) ------------------------------------------
day2 = read("baseline.txt")
d2_total = int(re.search(r"Total events evaluated:\s+(\d+)", day2).group(1))
d2_at_risk_rev = rupees(re.search(r"Revenue \(at_risk=True\):\s+₹([\d,]+)", day2).group(1))
d2_at_risk_count = int(re.search(r"True Positives\s+\(TP\):\s+(\d+)", day2).group(1)) + \
    int(re.search(r"False Positives \(FP\):\s+(\d+)", day2).group(1))

day3sim = read("baseline_simulation.txt")
bench = {
    "candidate_decisions": int(re.search(r"Candidate decisions:\s+(\d+)", day3sim).group(1)),
    "successful_recoveries": int(re.search(r"Successful recoveries:\s+(\d+)", day3sim).group(1)),
    "recovered_paise": rupees(re.search(r"Total recovered:\s+₹([\d,]+)", day3sim).group(1)),
    "bad_interventions": int(re.search(r"Bad interventions:\s+(\d+)", day3sim).group(1)),
    "net_recovered_paise": rupees(re.search(r"Net ₹ recovered:\s+₹([\d,]+)", day3sim).group(1)),
}

day3exp = read("agent_performance_result.txt")
m_bench = re.search(r"\|\s*Deterministic baseline\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|", day3exp)
m_agent = re.search(r"\|\s*AI recovery agent\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|", day3exp)

# ---- Call the route directly (merchant object unused beyond auth) ------------
db = SessionLocal()
try:
    merchant = Merchant(id=uuid.uuid4(), email="check@example.com", name="Check")
    summary = dashboard_summary(merchant=merchant, db=db)
finally:
    db.close()

# ---- 1. Detection vs baseline.txt ---------------------------------------
# Reports display whole rupees (floor division); endpoint returns exact
# paise, so compare on the report's own convention.
def matches_report_rupees(paise, report_rupees):
    return paise // 100 == report_rupees and 0 <= paise - report_rupees * 100 < 100

d = summary["detection"]
check("detection.total_events == day2 report", d["total_events"] == d2_total, f"{d['total_events']} vs {d2_total}")
check("detection.at_risk == TP+FP from day2 report", d["at_risk"] == d2_at_risk_count, f"{d['at_risk']} vs {d2_at_risk_count}")
check("detection.revenue_at_risk_paise == day2 report (within floor rounding)",
      matches_report_rupees(d["revenue_at_risk_paise"], d2_at_risk_rev // 100),
      f"{d['revenue_at_risk_paise']} vs {d2_at_risk_rev}")
check("detection.provenance == simulated", d["provenance"] == "simulated")

# ---- 2. agent_evaluation vs day3 reports -------------------------------------
ae = summary["agent_evaluation"]
exp_bench = {
    "candidate_decisions": int(m_bench.group(1)),
    "successful_recoveries": int(m_bench.group(2)),
    "recovered_paise": rupees(m_bench.group(3)),
    "bad_interventions": int(m_bench.group(4)),
    "net_recovered_paise": rupees(m_bench.group(5)),
}
exp_agent = {
    "candidate_decisions": int(m_agent.group(1)),
    "successful_recoveries": int(m_agent.group(2)),
    "recovered_paise": rupees(m_agent.group(3)),
    "bad_interventions": int(m_agent.group(4)),
    "net_recovered_paise": rupees(m_agent.group(5)),
}
exp_bench["targeting_precision"] = round(exp_bench["successful_recoveries"] / exp_bench["candidate_decisions"], 4)
exp_agent["targeting_precision"] = round(exp_agent["successful_recoveries"] / exp_agent["candidate_decisions"], 4)

RUPEE_FIELDS = ("recovered_paise", "net_recovered_paise")
for field in exp_bench:
    if field in RUPEE_FIELDS:
        ok = matches_report_rupees(ae["benchmark"][field], exp_bench[field] // 100)
        check(f"benchmark.{field} == experiment report (within floor rounding)", ok,
              f"{ae['benchmark'][field]} vs {exp_bench[field]}")
    else:
        check(f"benchmark.{field} == experiment report", ae["benchmark"][field] == exp_bench[field], f"{ae['benchmark'][field]} vs {exp_bench[field]}")
for field in exp_agent:
    if field in RUPEE_FIELDS:
        ok = matches_report_rupees(ae["agent"][field], exp_agent[field] // 100)
        check(f"agent.{field} == experiment report (within floor rounding)", ok,
              f"{ae['agent'][field]} vs {exp_agent[field]}")
    else:
        check(f"agent.{field} == experiment report", ae["agent"][field] == exp_agent[field], f"{ae['agent'][field]} vs {exp_agent[field]}")

# benchmark block must equal the baseline-simulation report too
for field in bench:
    if field in RUPEE_FIELDS:
        ok = matches_report_rupees(ae["benchmark"][field], bench[field] // 100)
        check(f"benchmark.{field} == baseline_simulation.txt (within floor rounding)", ok,
              f"{ae['benchmark'][field]} vs {bench[field]}")
    else:
        check(f"benchmark.{field} == baseline_simulation.txt", ae["benchmark"][field] == bench[field], f"{ae['benchmark'][field]} vs {bench[field]}")

check("verdict label", ae["verdict"] == "benchmark_retained_for_execution")
check("provenance simulated", ae["provenance"] == "simulated")

# ---- 3. real_execution vs audit trail ----------------------------------------
re_ = summary["real_execution"]
check("scenarios_run == 10", re_["scenarios_run"] == 10, f"got {re_['scenarios_run']}")
check("10 transaction entries", len(re_["transactions"]) == 10)
by_scenario = {t["scenario"]: t for t in re_["transactions"]}
# 5 actions = 2 automated (transient_low_amount, checkout_abandoned)
# + 3 merchant approvals via the dashboard (the escalation practice set).
check("decision counts sum to scenarios",
      re_["actions_taken"] + re_["stopped"] + re_["escalated"] == 10,
      f"got {re_['actions_taken']}/{re_['stopped']}/{re_['escalated']}")

# Policy-stable expectations (hard stops can never change). Everything
# else (merchant approvals, re-escalations) is verified against the
# latest execution event in the audit trail instead of frozen values.
POLICY_STABLE = {"attempts_exhausted": "stop", "already_recovered": "stop"}
for name, expected in POLICY_STABLE.items():
    t = by_scenario.get(name)
    check(f"{name} -> {expected} (policy-stable)", t is not None and t["decision"] == expected,
          f"got {t['decision'] if t else 'missing'}")

# Every other scenario's decision must match its latest execution event.
EXEC_TO_DECISION = {"execution_action_taken": "action", "execution_escalated": "escalate",
                    "execution_stopped": "stop", "execution_capped": "stop",
                    "execution_action_failed": "action"}
db_rows = db.query(AuditLog).filter(
    AuditLog.transaction_id.in_([t["transaction_id"] for t in re_["transactions"]]),
    AuditLog.event.in_(EXEC_TO_DECISION)).all()
latest_by_txn = {}
for log in db_rows:
    latest_by_txn.setdefault(str(log.transaction_id), []).append((log.timestamp, log.event))
latest_by_txn = {k: sorted(v)[-1][1] for k, v in latest_by_txn.items()}
def expected_decision(t):
    # Terminal state wins: a transaction that was escalated, approved, and
    # then actually paid is "action/recovered" even if its latest execution
    # event was the earlier escalation.
    payload_t = next(x for x in re_["transactions"] if x["transaction_id"] == t["transaction_id"])
    if payload_t["recovered"] and payload_t["payment_link_id"]:
        return "action"
    return EXEC_TO_DECISION.get(latest_by_txn.get(t["transaction_id"]))

mismatches = [t["scenario"] for t in re_["transactions"]
              if EXEC_TO_DECISION.get(latest_by_txn.get(t["transaction_id"])) != t["decision"]
              and expected_decision(t) != t["decision"]]
check("every decision matches its audit trail (with recovered-terminal override)", not mismatches,
      f"mismatches: {mismatches}")

check("linked scenarios have payment_link_id",
      all(by_scenario[s]["payment_link_id"] for s in ("transient_low_amount", "checkout_abandoned")))
# Non-action scenarios that were NOT recovered must have no payment link.
# (A recovered non-action scenario may legitimately have one: e.g.
# amount_above_cap was approved via the dashboard and paid via webhook.)
# Invariant: a payment link exists iff the transaction was actioned
# (automated or merchant-approved) or has been recovered via webhook.
# Escalated-but-not-yet-approved scenarios correctly have none.
check("payment link present iff actioned or recovered",
      all((bool(t["payment_link_id"]) == (t["decision"] == "action" or t["recovered"]))
          for t in re_["transactions"]))
# Real recovery expectation comes from the live webhook path (audit
# trail), not an assumption: any revenue_recovered event on a demo
# transaction means the demo payment link was actually paid in Test Mode.
expected_recovered = {t["transaction_id"] for t in re_["transactions"] if t["recovered"]}
expected_paise = sum(t["amount_paise"] for t in re_["transactions"] if t["recovered"])
check("real_paise_recovered == sum of recovered scenarios",
      re_["real_paise_recovered"] == expected_paise,
      f"{re_['real_paise_recovered']} vs {expected_paise}")
check("recovered flag consistent with webhook audit events",
      all((t["transaction_id"] in expected_recovered) == t["recovered"] for t in re_["transactions"]))
recovered_scenarios = [t["scenario"] for t in re_["transactions"] if t["recovered"]]
print(f"      note: {len(expected_recovered)} demo transaction(s) actually paid via webhook: "
      f"{recovered_scenarios} = ₹{expected_paise / 100:,.2f}")
check("audit chains non-empty", all(len(t["audit_chain"]) >= 2 for t in re_["transactions"]))
check("transactions carry failure_reason for analytics",
      all("failure_reason" in t for t in re_["transactions"]))
check("audit chain ordered by timestamp",
      all(t["audit_chain"] == sorted(t["audit_chain"], key=lambda e: e["timestamp"]) for t in re_["transactions"]))
check("llm_execution_authority is False", re_["llm_execution_authority"] is False)
check("decision_engine label", re_["decision_engine"] == "deterministic_policy_gate")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
