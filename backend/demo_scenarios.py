#!/usr/bin/env python3
"""Create real Razorpay Test Mode orders exercising each execution-policy branch.

For each of 6 scenarios this script:
  1. creates a REAL Test Mode order by calling main.create_test_order()
     directly (the Razorpay API call is reused, not duplicated),
  2. sets local transaction state (status / failure_reason /
     previous_recovery_attempts) so the Phase 1 detector can evaluate the
     transaction — Razorpay itself does not know about this local state,
  3. classifies it with detect_at_risk.classify() (the exact detector
     rules used in the benchmark),
  4. derives the execution-policy branch from EXECUTION_POLICY.md
     (tier mapping + hard stops, using execution_config defaults),
  5. prints the created ids and whether the branch matched the expectation.

No payment links are created or sent — orders only, Test Mode only.
Live execution remains governed by execution_config.LIVE_EXECUTION_ENABLED.

Usage:
    python demo_scenarios.py
"""

import sys
import uuid

from db import SessionLocal
from detect_at_risk import classify
from execution_config import (
    LIVE_EXECUTION_ENABLED,
    MAX_ATTEMPTS,
    MAX_AUTOMATED_AMOUNT_PAISE,
)
from main import CreateTestOrderRequest, create_test_order
from models import AuditLog, Transaction

SCENARIOS = [
    {
        "name": "transient_low_amount",
        "amount_paise": 299900,
        "status": "failed",
        "failure_reason": "network_error",
        "previous_recovery_attempts": 0,
        "expected": "ACTION",
    },
    {
        "name": "checkout_abandoned",
        "amount_paise": 149900,
        "status": "abandoned_checkout",
        "failure_reason": "customer_abandoned",
        "previous_recovery_attempts": 0,
        "expected": "ACTION",
    },
    {
        "name": "attempts_exhausted",
        "amount_paise": 199900,
        "status": "failed",
        "failure_reason": "card_declined",
        "previous_recovery_attempts": 3,
        "expected": "STOP",
    },
    {
        "name": "amount_above_cap",
        "amount_paise": 750000,
        "status": "failed",
        "failure_reason": "network_error",
        "previous_recovery_attempts": 0,
        "expected": "ESCALATE",
    },
    {
        "name": "low_recoverability",
        "amount_paise": 99900,
        "status": "failed",
        "failure_reason": "insufficient_funds",
        "previous_recovery_attempts": 2,
        "expected": "ESCALATE",
    },
    {
        "name": "already_recovered",
        "amount_paise": 199900,
        "status": "recovered",
        "failure_reason": None,
        "previous_recovery_attempts": 0,
        "expected": "STOP",
    },
]


def execution_branch(recoverability: str, amount_paise: int, attempts: int, status: str):
    """Derive the EXECUTION_POLICY.md branch for one transaction.

    Hard stops first (Section 3), then the tier mapping (Section 2).
    Returns (branch, reason).
    """
    if status == "recovered":
        return "STOP", "already_recovered"
    if attempts >= MAX_ATTEMPTS:
        return "STOP", "attempts_at_cap"
    if amount_paise > MAX_AUTOMATED_AMOUNT_PAISE:
        return "ESCALATE", "amount_above_cap"
    if recoverability == "high":
        return "ACTION", "tier_high_within_limits"
    if recoverability == "low":
        return "ESCALATE", "low_recoverability"
    return "STOP", "tier_none"


def apply_local_state(transaction_id: str, scenario: dict) -> dict:
    """Set the local observed-signal state on the transactions row."""
    db = SessionLocal()
    try:
        txn = db.get(Transaction, uuid.UUID(transaction_id))
        txn.status = scenario["status"]
        txn.failure_reason = scenario["failure_reason"]
        txn.previous_recovery_attempts = scenario["previous_recovery_attempts"]
        db.add(AuditLog(
            transaction_id=txn.id,
            event="demo_scenario_state_applied",
            details={
                "scenario": scenario["name"],
                "status": scenario["status"],
                "failure_reason": scenario["failure_reason"],
                "previous_recovery_attempts": scenario["previous_recovery_attempts"],
            },
        ))
        db.commit()
        return {
            "amount_paise": txn.amount_paise,
            "status": txn.status,
            "failure_reason": txn.failure_reason,
            "previous_recovery_attempts": txn.previous_recovery_attempts,
        }
    finally:
        db.close()


def main() -> int:
    print("=" * 70)
    print("  Execution Policy Demo — 6 Razorpay Test Mode orders")
    print("=" * 70)
    print(f"Live execution enabled : {LIVE_EXECUTION_ENABLED} (no payment links will be sent)")
    print(f"Amount cap             : ₹{MAX_AUTOMATED_AMOUNT_PAISE / 100:,.0f}")
    print(f"Attempt cap            : {MAX_ATTEMPTS}")
    print()

    results = []
    created_ids = []
    for idx, scenario in enumerate(SCENARIOS, start=1):
        print(f"--- {idx}. {scenario['name']} ---")

        # 1. Real Test Mode order via the existing endpoint logic
        response = create_test_order(CreateTestOrderRequest(amount_paise=scenario["amount_paise"]))
        print(f"  transaction_id    : {response.transaction_id}")
        print(f"  razorpay_order_id : {response.razorpay_order_id}")
        created_ids.append((scenario["name"], response.transaction_id, response.razorpay_order_id))

        # 2. Local state (Razorpay does not know about this)
        state = apply_local_state(response.transaction_id, scenario)
        print(f"  local state       : status={state['status']!r} "
              f"reason={state['failure_reason']!r} "
              f"attempts={state['previous_recovery_attempts']} "
              f"amount=₹{state['amount_paise'] / 100:,.2f}")

        # 3. Detector classification (same rules as the benchmark)
        detection = classify(state)
        print(f"  detector          : at_risk={detection['at_risk']} "
              f"tier={detection['recoverability']!r} ({detection['risk_reason']})")

        # 4. Execution-policy branch (tier mapping + hard stops)
        branch, reason = execution_branch(
            detection["recoverability"],
            state["amount_paise"],
            state["previous_recovery_attempts"],
            state["status"],
        )
        ok = branch == scenario["expected"]
        print(f"  execution branch  : {branch} ({reason})"
              f"   [expected: {scenario['expected']}]  {'PASS' if ok else 'FAIL'}")
        print()

        results.append((scenario["name"], branch, scenario["expected"], ok))

    print("=" * 70)
    print("  Summary")
    print("=" * 70)
    passed = sum(1 for *_, ok in results if ok)
    for name, branch, expected, ok in results:
        print(f"  {name:22s} -> {branch:8s} (expected {expected:8s})  {'PASS' if ok else 'FAIL'}")
    print(f"\n{passed}/{len(results)} scenarios matched the execution policy.")

    # Trackable ids for the user
    print("\nCreated transactions (for tracking):")
    for name, txn_id, order_id in created_ids:
        print(f"  {name:22s} transaction_id={txn_id}  razorpay_order_id={order_id}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
