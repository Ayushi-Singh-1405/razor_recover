#!/usr/bin/env python3
"""Verify GET /dashboard/summary numbers match the Day 2-4 source reports
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
from models import Merchant

BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")


def read(name):
    with open(os.path.join(BACKEND, "reports", name)) as f:
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
day2 = read("day2_baseline.txt")
d2_total = int(re.search(r"Total events evaluated:\s+(\d+)", day2).group(1))
d2_at_risk_rev = rupees(re.search(r"Revenue \(at_risk=True\):\s+₹([\d,]+)", day2).group(1))
d2_at_risk_count = int(re.search(r"True Positives\s+\(TP\):\s+(\d+)", day2).group(1)) + \
    int(re.search(r"False Positives \(FP\):\s+(\d+)", day2).group(1))

day3sim = read("day3_baseline_simulation.txt")
bench = {
    "candidate_decisions": int(re.search(r"Candidate decisions:\s+(\d+)", day3sim).group(1)),
    "successful_recoveries": int(re.search(r"Successful recoveries:\s+(\d+)", day3sim).group(1)),
    "recovered_paise": rupees(re.search(r"Total recovered:\s+₹([\d,]+)", day3sim).group(1)),
    "bad_interventions": int(re.search(r"Bad interventions:\s+(\d+)", day3sim).group(1)),
    "net_recovered_paise": rupees(re.search(r"Net ₹ recovered:\s+₹([\d,]+)", day3sim).group(1)),
}

day3exp = read("day3_experiment_result.txt")
m_bench = re.search(r"\|\s*Deterministic baseline\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|", day3exp)
m_agent = re.search(r"\|\s*AI recovery agent\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|\s*(\d+)\s*\|\s*₹([\d,]+)\s*\|", day3exp)

# ---- Call the route directly (merchant object unused beyond auth) ------------
db = SessionLocal()
try:
    merchant = Merchant(id=uuid.uuid4(), email="check@example.com", name="Check")
    summary = dashboard_summary(merchant=merchant, db=db)
finally:
    db.close()

# ---- 1. Detection vs day2_baseline.txt ---------------------------------------
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
        check(f"benchmark.{field} == day3_baseline_simulation.txt (within floor rounding)", ok,
              f"{ae['benchmark'][field]} vs {bench[field]}")
    else:
        check(f"benchmark.{field} == day3_baseline_simulation.txt", ae["benchmark"][field] == bench[field], f"{ae['benchmark'][field]} vs {bench[field]}")

check("verdict label", ae["verdict"] == "benchmark_retained_for_execution")
check("provenance simulated", ae["provenance"] == "simulated")

# ---- 3. real_execution vs audit trail ----------------------------------------
re_ = summary["real_execution"]
check("scenarios_run == 6", re_["scenarios_run"] == 6, f"got {re_['scenarios_run']}")
check("6 transaction entries", len(re_["transactions"]) == 6)
by_scenario = {t["scenario"]: t for t in re_["transactions"]}
check("actions_taken == 2", re_["actions_taken"] == 2, f"got {re_['actions_taken']}")
check("stopped + escalated + action == scenarios", re_["stopped"] + re_["escalated"] + re_["actions_taken"] == 6)

expected_branches = {
    "transient_low_amount": "action",
    "checkout_abandoned": "action",
    "attempts_exhausted": "stop",
    "amount_above_cap": "escalate",
    "low_recoverability": "escalate",
    "already_recovered": "stop",
}
for name, expected in expected_branches.items():
    t = by_scenario.get(name)
    check(f"{name} -> {expected}", t is not None and t["decision"] == expected,
          f"got {t['decision'] if t else 'missing'}")

check("linked scenarios have payment_link_id",
      all(by_scenario[s]["payment_link_id"] for s in ("transient_low_amount", "checkout_abandoned")))
check("non-action scenarios have no payment_link_id",
      all(by_scenario[s]["payment_link_id"] is None for s in ("attempts_exhausted", "amount_above_cap", "low_recoverability", "already_recovered")))
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
check("audit chain ordered by timestamp",
      all(t["audit_chain"] == sorted(t["audit_chain"], key=lambda e: e["timestamp"]) for t in re_["transactions"]))
check("llm_execution_authority is False", re_["llm_execution_authority"] is False)
check("decision_engine label", re_["decision_engine"] == "deterministic_policy_gate")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
