#!/usr/bin/env python3
"""Three additional escalation-only demo orders (Approve/Dismiss practice).

Creates real Razorpay Test Mode orders that each land in ESCALATE for a
different reason — practice material for the dashboard's Approve/Dismiss
flow, without touching the two original escalated demo cases.

Reuses demo_scenarios.apply_local_state, so every transaction is tagged
with the same demo_scenario_state_applied audit event that
/dashboard/summary and execute_recovery.py select on — they appear on the
dashboard automatically after the next execution run.

Expected outcomes (per EXECUTION_POLICY.md):
  amount_above_cap_2   -> ESCALATE (amount_above_cap)   failed + network_error, Rs 6,500 > cap
  low_recoverability_2 -> ESCALATE (low_recoverability) failed + insufficient_funds (LOW tier)
  amount_above_cap_3   -> ESCALATE (amount_above_cap)   abandoned checkout, Rs 8,999 > cap

Usage:
    python demo_scenarios_extra.py
"""

import sys

from demo_scenarios import apply_local_state, execution_branch
from detect_at_risk import classify
from main import CreateTestOrderRequest, create_test_order

EXTRA_SCENARIOS = [
    {
        "name": "amount_above_cap_2",
        "amount_paise": 650000,
        "status": "failed",
        "failure_reason": "network_error",
        "previous_recovery_attempts": 0,
        "expected": "ESCALATE",
        "expected_reason": "amount_above_cap",
    },
    {
        "name": "low_recoverability_2",
        "amount_paise": 79900,
        "status": "failed",
        "failure_reason": "insufficient_funds",
        "previous_recovery_attempts": 1,
        "expected": "ESCALATE",
        "expected_reason": "low_recoverability",
    },
    {
        "name": "amount_above_cap_4",
        "amount_paise": 575000,
        "status": "failed",
        "failure_reason": "network_error",
        "previous_recovery_attempts": 0,
        "expected": "ESCALATE",
        "expected_reason": "amount_above_cap",
    },
    {
        "name": "amount_above_cap_3",
        "amount_paise": 899900,
        "status": "abandoned_checkout",
        "failure_reason": "customer_abandoned",
        "previous_recovery_attempts": 0,
        "expected": "ESCALATE",
        "expected_reason": "amount_above_cap",
    },
]


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Create escalation-demo Test Mode orders.")
    parser.add_argument("--only", metavar="NAME", default=None,
                        help="Create only the named scenario (e.g. amount_above_cap_4).")
    args = parser.parse_args()

    scenarios = EXTRA_SCENARIOS
    if args.only:
        scenarios = [s for s in EXTRA_SCENARIOS if s["name"] == args.only]
        if not scenarios:
            print(f"Unknown scenario: {args.only}")
            print("Available:", ", ".join(s["name"] for s in EXTRA_SCENARIOS))
            return 2

    print("=" * 70)
    print("  Escalation Demo Orders — 3 additional Razorpay Test Mode orders")
    print("=" * 70)
    print("All three must land in ESCALATE. No payment links will be sent.\n")

    results = []
    created_ids = []

    for idx, scenario in enumerate(scenarios, start=1):
        print(f"--- {idx}. {scenario['name']} ---")

        # Real Test Mode order via the existing endpoint logic
        response = create_test_order(CreateTestOrderRequest(amount_paise=scenario["amount_paise"]))
        print(f"  transaction_id    : {response.transaction_id}")
        print(f"  razorpay_order_id : {response.razorpay_order_id}")
        created_ids.append((scenario["name"], response.transaction_id, response.razorpay_order_id))

        # Local observed-signal state (tagged for summary + execution)
        state = apply_local_state(response.transaction_id, scenario)
        print(f"  local state       : status={state['status']!r} "
              f"reason={state['failure_reason']!r} "
              f"attempts={state['previous_recovery_attempts']} "
              f"amount=₹{state['amount_paise'] / 100:,.2f}")

        # Detector classification (same rules as the benchmark)
        detection = classify(state)
        print(f"  detector          : at_risk={detection['at_risk']} "
              f"tier={detection['recoverability']!r} ({detection['risk_reason']})")

        # Execution-policy branch (tier mapping + hard stops)
        branch, reason = execution_branch(
            detection["recoverability"],
            state["amount_paise"],
            state["previous_recovery_attempts"],
            state["status"],
        )
        ok = branch == scenario["expected"] and reason == scenario["expected_reason"]
        print(f"  execution branch  : {branch} ({reason})"
              f"   [expected: {scenario['expected']} / {scenario['expected_reason']}]  "
              f"{'PASS' if ok else 'FAIL'}")
        print()

        results.append((scenario["name"], branch, reason, ok))

    print("=" * 70)
    print("  Summary")
    print("=" * 70)
    passed = sum(1 for *_, ok in results if ok)
    for name, branch, reason, ok in results:
        print(f"  {name:22s} -> {branch:8s} ({reason})   {'PASS' if ok else 'FAIL'}")
    print(f"\n{passed}/{len(results)} scenarios landed in ESCALATE as expected.")

    print("\nCreated transactions (for tracking):")
    for name, txn_id, order_id in created_ids:
        print(f"  {name:22s} transaction_id={txn_id}  razorpay_order_id={order_id}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
