#!/usr/bin/env python3
"""Read-only agent reasoning pass for demo transactions.

For each demo transaction (tagged with demo_scenario_state_applied), asks
the recovery agent for its structured recommendation using the SAME decision
schema and retry logic as the benchmark runner, and records the result as an
agent_recommendation audit entry — this is what the dashboard's Agent Decision
viewer renders.

Safety properties:
  - Read-only: no Razorpay calls, no execution, no policy decisions.
    The execution layer and policy gates are completely untouched.
  - Idempotent: transactions that already have an agent_recommendation
    entry are skipped, so re-runs (e.g. during a recorded demo) never
    burn duplicate LLM calls.
  - 429 rate limits are retried with exponential backoff (same policy as
    the benchmark runner); hard failures are logged and reported.

Usage:
    python agent_recommendations.py            # all demo transactions
    python agent_recommendations.py --limit 3  # first 3 only
"""

import argparse
import os
import sys
import time

from db import SessionLocal
from llm_provider import get_structured_decision
from models import AuditLog, Transaction
from run_agent import call_llm_with_rate_limit_retry, DECISION_SCHEMA

LLM_CALL_DELAY = 1.0  # seconds between calls — be polite to free-tier quotas


def build_demo_prompt(txn) -> str:
    """Prompt for a demo transaction.

    Demo transactions carry the observed signals the execution layer sees
    (amount, status, failure reason, attempt count) — no enriched customer
    history exists for real orders, and none is fabricated.
    """
    amount = txn["amount_paise"] / 100
    return f"""You are Revoco's payment recovery decision agent for a Razorpay merchant.
Analyze the following failed/abandoned payment and recommend the best bounded recovery action.

### Transaction details:
- Amount: ₹{amount:,.2f} ({txn['amount_paise']} paise)
- Payment status: {txn['status']}
- Failure reason: {txn['failure_reason'] or 'N/A'}
- Previous recovery attempts on this transaction: {txn['previous_recovery_attempts']}

### Permitted actions:
1. 'recover_now': immediately generate and send an urgent recovery payment link (best for
   high-intent customers with transient failures like network_error or otp_timeout).
2. 'send_payment_link': generate and send a standard recovery payment link (best for
   abandoned checkouts where the customer may simply need another opportunity).
3. 'wait_and_retry': wait before re-attempting without contacting the customer immediately.
4. 'escalate_to_merchant': escalate for human review (best for ambiguous cases, high-value
   transactions, or conflicting signals).
5. 'stop': cease further recovery attempts (best when history indicates the payment is
   unrecoverable or repeated attempts have already failed).

Evaluate the available context and return your structured decision JSON."""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only agent reasoning pass over demo transactions.")
    parser.add_argument("--limit", type=int, default=None, metavar="N",
                        help="Only process the first N demo transactions without a recommendation.")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        print("Error: --limit must be a positive integer.")
        return 2

    db = SessionLocal()
    recommended = skipped = failed = 0

    try:
        tagged = db.query(AuditLog).filter(
            AuditLog.event == "demo_scenario_state_applied").all()
        ids = [a.transaction_id for a in tagged]
        txns = (
            db.query(Transaction)
            .filter(Transaction.id.in_(ids))
            .order_by(Transaction.created_at.asc())
            .all()
        )

        already = {
            a.transaction_id
            for a in db.query(AuditLog).filter(
                AuditLog.event == "agent_recommendation",
                AuditLog.transaction_id.in_(ids)).all()
        }

        print("=" * 70)
        print("  Agent Recommendation Pass (read-only — no Razorpay calls)")
        print("=" * 70)
        print(f"Demo transactions : {len(txns)}")
        print(f"Already have rec. : {len(already & set(ids))}")
        print()

        processed = 0
        for idx, txn in enumerate(txns, start=1):
            short = f"{str(txn.id)[:8]}..."
            if txn.id in already:
                print(f"{short} → SKIP (recommendation already recorded)")
                skipped += 1
                continue
            if args.limit is not None and processed >= args.limit:
                print(f"{short} → skipped (--limit {args.limit} reached)")
                continue

            row = {
                "amount_paise": txn.amount_paise,
                "status": txn.status,
                "failure_reason": txn.failure_reason,
                "previous_recovery_attempts": txn.previous_recovery_attempts,
            }
            prompt = build_demo_prompt(row)

            if processed > 0:
                time.sleep(LLM_CALL_DELAY)

            response, retries, err = call_llm_with_rate_limit_retry(
                str(txn.id), prompt, DECISION_SCHEMA)

            if response is None:
                print(f"{short} → FAILED ({err})")
                failed += 1
                continue

            details = {
                "phase": "agent_reasoning",
                "diagnosis": response["diagnosis"],
                "recommended_action": response["recommended_action"],
                "recovery_probability": response["recovery_probability"],
                "confidence": response["confidence"],
                "reason": response["reason"],
                "model": os.getenv("OPENROUTER_MODEL", "openrouter/free"),
                "rate_limit_retries": retries,
            }
            db.add(AuditLog(
                transaction_id=txn.id,
                event="agent_recommendation",
                details=details,
            ))
            db.commit()
            processed += 1

            extra = f" ({retries} rate-limit retries)" if retries else ""
            print(f"{short} → {response['recommended_action']} "
                  f"(confidence {response['confidence']}){extra}")

        print()
        print("=" * 70)
        print("  Summary")
        print("=" * 70)
        print(f"Recommendations recorded : {processed}")
        print(f"Already recorded (skipped): {skipped}")
        print(f"Failed                   : {failed}")
        print("\nThe dashboard's Agent Decision viewer reads these from the audit trail.")
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
