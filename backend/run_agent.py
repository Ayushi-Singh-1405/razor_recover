#!/usr/bin/env python3
"""Run the AI Recovery Decision Agent on at-risk synthetic payment events.

Reads events flagged as at-risk by the deterministic detector, applies
pre-filtering policy gates, requests structured decisions from the LLM for
eligible transactions, applies post-filtering safety gates, and records all
decisions into the agent_decisions table.

Usage:
    python run_agent.py
"""

import logging
import sys
import time
import uuid
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_values

from config import DATABASE_URL
from llm_provider import (
    get_structured_decision,
    LLMProviderError,
    LLMAPIError,
    LLMJSONDecodeError,
    LLMSchemaValidationError,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 100
LLM_CALL_DELAY = 0.5  # seconds between LLM requests to respect rate limits

ALLOWED_ACTIONS = frozenset({
    "recover_now",
    "send_payment_link",
    "wait_and_retry",
    "escalate_to_merchant",
    "stop",
})

DECISION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "diagnosis": {
            "type": "string",
            "description": "Root cause diagnosis of why this transaction failed or was abandoned.",
        },
        "recovery_probability": {
            "type": "number",
            "description": "Estimated probability of successful recovery between 0.0 and 1.0.",
        },
        "recommended_action": {
            "type": "string",
            "enum": [
                "recover_now",
                "send_payment_link",
                "wait_and_retry",
                "escalate_to_merchant",
                "stop",
            ],
            "description": "The recommended recovery action to take.",
        },
        "reason": {
            "type": "string",
            "description": "Detailed reasoning referencing customer behavior, checkout context, and history.",
        },
        "confidence": {
            "type": "number",
            "description": "Decision maker confidence score between 0.0 and 1.0.",
        },
    },
    "required": [
        "diagnosis",
        "recovery_probability",
        "recommended_action",
        "reason",
        "confidence",
    ],
}


def build_event_prompt(event: Dict[str, Any]) -> str:
    """Build context-rich prompt for the LLM without any ground_truth fields."""
    amount_inr = event["amount_paise"] / 100.0
    aov_val = event.get("average_order_value")
    aov_inr_str = f"₹{aov_val / 100:,.2f}" if aov_val and aov_val > 0 else "N/A"
    
    last_success_hrs = event.get("time_since_last_successful_payment_hours")
    last_success_str = f"{last_success_hrs} hours ago" if last_success_hrs is not None else "No prior success recorded"
    
    last_recovery_hrs = event.get("time_since_last_recovery_attempt_hours")
    last_recovery_str = f"{last_recovery_hrs} hours ago" if last_recovery_hrs is not None else "No prior recovery attempt"

    return f"""You are RecoverAI's Autonomous Revenue Recovery Decision Agent for Razorpay transactions.
Analyze the following payment event and customer context, diagnose why the transaction failed or was abandoned, and recommend the best bounded recovery action.

### Transaction Details:
- Amount: ₹{amount_inr:,.2f} ({event['amount_paise']} paise)
- Payment Status: {event['status']}
- Failure Reason: {event['failure_reason'] or 'N/A'}
- Payment Method: {event['payment_method'] or 'Unknown'}
- Checkout Duration: {event['checkout_duration_seconds']} seconds

### Customer Profile & Behavioral History:
- Customer Tenure: {event['customer_tenure_days']} days
- Previous Successful Payments: {event['previous_successful_payments']}
- Previous Failed Payments: {event['previous_failed_payments']}
- Historical Average Order Value: {aov_inr_str}
- Time Since Last Successful Payment: {last_success_str}

### Recovery Intervention History:
- Previous Recovery Attempts on this Transaction: {event['previous_recovery_attempts']}
- Time Since Last Recovery Attempt: {last_recovery_str}

### Permitted Actions:
1. 'recover_now': Immediately generate and send an urgent Razorpay recovery payment link (best for high-intent customers with transient failures like network_error or otp_timeout).
2. 'send_payment_link': Generate and send a standard recovery payment link with standard expiry (best for abandoned checkouts with established customer history).
3. 'wait_and_retry': Wait for cooldown before re-attempting without contacting customer immediately (best when a recent recovery attempt happened or temporary bank/processor glitch).
4. 'escalate_to_merchant': Escalate to merchant human review (best for ambiguous cases, conflicting signals, or high uncertainty).
5. 'stop': Cease further recovery attempts (best when customer history indicates unrecoverable failure or repeated declines without success history).

Evaluate all signals and return your structured decision JSON.
"""


def check_pre_filter(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Check deterministic pre-filters before calling the LLM.

    Returns dict with pre-filtered decision if triggered, else None.
    """
    # 1. Exhausted recovery attempts hard stop
    if event["previous_recovery_attempts"] >= 3:
        return {
            "diagnosis": "pre_filtered_exhausted",
            "recovery_probability": 0.0,
            "recommended_action": "stop",
            "reason": "Recovery attempt limit reached (attempts >= 3)",
            "confidence": 1.0,
            "decision_path": "pre_filtered",
            "override_reason": "attempts_exhausted",
        }

    # 2. High value threshold requires human review
    if event["amount_paise"] > 1_800_000:  # > ₹18,000
        return {
            "diagnosis": "pre_filtered_high_value",
            "recovery_probability": 0.0,
            "recommended_action": "escalate_to_merchant",
            "reason": "Amount exceeds automated recovery threshold (amount > ₹18,000)",
            "confidence": 1.0,
            "decision_path": "pre_filtered",
            "override_reason": "high_value_requires_human_review",
        }

    return None


def apply_post_filter(llm_res: Dict[str, Any]) -> Dict[str, Any]:
    """Apply deterministic safety gates to the LLM response."""
    action = llm_res.get("recommended_action")
    confidence = llm_res.get("confidence", 0.0)

    # 1. Invalid action returned
    if action not in ALLOWED_ACTIONS:
        return {
            "diagnosis": llm_res.get("diagnosis", "invalid_action"),
            "recovery_probability": float(llm_res.get("recovery_probability", 0.0)),
            "recommended_action": "escalate_to_merchant",
            "reason": f"Invalid action '{action}' overridden to escalate_to_merchant. Original reason: {llm_res.get('reason', '')}",
            "confidence": float(confidence),
            "decision_path": "gated_override",
            "override_reason": "invalid_action_returned",
        }

    # 2. Low confidence threshold
    if confidence < 0.5:
        return {
            "diagnosis": llm_res.get("diagnosis", "low_confidence_diagnosis"),
            "recovery_probability": float(llm_res.get("recovery_probability", 0.0)),
            "recommended_action": "escalate_to_merchant",
            "reason": f"Low confidence ({confidence:.2f} < 0.50) overridden to escalate_to_merchant. Original recommendation: {action}. Original reason: {llm_res.get('reason', '')}",
            "confidence": float(confidence),
            "decision_path": "gated_override",
            "override_reason": "low_confidence",
        }

    # Approved AI decision
    return {
        "diagnosis": str(llm_res.get("diagnosis", "")),
        "recovery_probability": float(llm_res.get("recovery_probability", 0.0)),
        "recommended_action": str(action),
        "reason": str(llm_res.get("reason", "")),
        "confidence": float(confidence),
        "decision_path": "ai_decision",
        "override_reason": None,
    }


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        # 1. Read at-risk synthetic events
        query = """
            SELECT 
                se.id,
                se.amount_paise,
                se.status,
                se.failure_reason,
                se.customer_ref,
                se.previous_successful_payments,
                se.previous_recovery_attempts,
                se.created_at,
                se.customer_tenure_days,
                se.previous_failed_payments,
                se.average_order_value,
                se.time_since_last_successful_payment_hours,
                se.time_since_last_recovery_attempt_hours,
                se.checkout_duration_seconds,
                se.payment_method
            FROM synthetic_events se
            JOIN detection_results dr ON dr.synthetic_event_id = se.id
            WHERE dr.at_risk = TRUE
            ORDER BY se.created_at ASC
        """
        cur.execute(query)
        events_raw = cur.fetchall()
        col_names = [
            "id", "amount_paise", "status", "failure_reason", "customer_ref",
            "previous_successful_payments", "previous_recovery_attempts", "created_at",
            "customer_tenure_days", "previous_failed_payments", "average_order_value",
            "time_since_last_successful_payment_hours", "time_since_last_recovery_attempt_hours",
            "checkout_duration_seconds", "payment_method"
        ]
        
        events = [dict(zip(col_names, row)) for row in events_raw]
        total_events = len(events)
        print(f"\n==================================================")
        print(f"  RecoverAI — Agent Decision Runner")
        print(f"==================================================")
        print(f"Loaded {total_events} at-risk events from database.")

        # 2. Clear existing agent_decisions
        cur.execute("DELETE FROM agent_decisions")
        conn.commit()
        print("Cleared existing agent_decisions table.")

        pre_filtered_count = 0
        pre_filtered_reasons = Counter()
        llm_called_count = 0
        gated_override_count = 0
        gated_override_reasons = Counter()
        ai_decision_count = 0
        final_action_counts = Counter()

        db_rows: List[Tuple] = []

        print(f"\nStarting decision processing...")
        for i, event in enumerate(events, start=1):
            pre_filter = check_pre_filter(event)
            
            if pre_filter is not None:
                decision = pre_filter
                pre_filtered_count += 1
                pre_filtered_reasons[decision["override_reason"]] += 1
            else:
                llm_called_count += 1
                prompt = build_event_prompt(event)
                
                # Rate limit delay
                if LLM_CALL_DELAY > 0 and llm_called_count > 1:
                    time.sleep(LLM_CALL_DELAY)

                try:
                    llm_response = get_structured_decision(prompt, DECISION_SCHEMA)
                    decision = apply_post_filter(llm_response)
                except (LLMProviderError, Exception) as exc:
                    logger.warning(f"Event {event['id']} LLM call failed: {exc}")
                    decision = {
                        "diagnosis": "llm_call_failed",
                        "recovery_probability": 0.0,
                        "recommended_action": "escalate_to_merchant",
                        "reason": f"LLM error: {exc}",
                        "confidence": 0.0,
                        "decision_path": "gated_override",
                        "override_reason": "llm_call_failed",
                    }

                if decision["decision_path"] == "gated_override":
                    gated_override_count += 1
                    gated_override_reasons[decision["override_reason"]] += 1
                elif decision["decision_path"] == "ai_decision":
                    ai_decision_count += 1

            final_action_counts[decision["recommended_action"]] += 1

            db_rows.append((
                str(uuid.uuid4()),
                str(event["id"]),
                decision["diagnosis"],
                decision["recovery_probability"],
                decision["recommended_action"],
                decision["reason"],
                decision["confidence"],
                decision["decision_path"],
                decision["override_reason"],
            ))

            if i % 50 == 0 or i == total_events:
                print(f"Processed {i}/{total_events} events...")

        # 3. Batch insert into agent_decisions
        print(f"\nInserting {len(db_rows)} records into agent_decisions...")
        insert_query = """
            INSERT INTO agent_decisions (
                id,
                synthetic_event_id,
                diagnosis,
                recovery_probability,
                recommended_action,
                reason,
                confidence,
                decision_path,
                override_reason
            ) VALUES %s
        """
        total_batches = (len(db_rows) + BATCH_SIZE - 1) // BATCH_SIZE
        for b_idx in range(0, len(db_rows), BATCH_SIZE):
            batch = db_rows[b_idx : b_idx + BATCH_SIZE]
            execute_values(cur, insert_query, batch, page_size=BATCH_SIZE)
            conn.commit()
            print(f"Inserted batch {b_idx // BATCH_SIZE + 1}/{total_batches} ({min(b_idx + BATCH_SIZE, len(db_rows))}/{len(db_rows)} rows)")

        cur.execute("SELECT count(*) FROM agent_decisions")
        inserted_count = cur.fetchone()[0]
        if inserted_count != total_events:
            raise RuntimeError(f"Row count mismatch: inserted {inserted_count}, expected {total_events}")

        # 4. Print Summary
        print(f"\n==================================================")
        print(f"  Agent Decision Run Summary")
        print(f"==================================================")
        print(f"Total at-risk events evaluated: {total_events}")
        print(f"")
        print(f"--- Decision Paths ---")
        print(f"  Pre-filtered (skipped LLM):     {pre_filtered_count:5d}  ({pre_filtered_count / total_events * 100:.1f}%)")
        for reason, cnt in sorted(pre_filtered_reasons.items(), key=lambda x: -x[1]):
            print(f"    - {reason:30s} {cnt:5d}")
        print(f"  Reached LLM:                   {llm_called_count:5d}  ({llm_called_count / total_events * 100:.1f}%)")
        print(f"    - Pure AI Decisions:         {ai_decision_count:5d}  ({ai_decision_count / total_events * 100:.1f}%)")
        print(f"    - Gated Overrides:           {gated_override_count:5d}  ({gated_override_count / total_events * 100:.1f}%)")
        for reason, cnt in sorted(gated_override_reasons.items(), key=lambda x: -x[1]):
            print(f"      * {reason:28s} {cnt:5d}")
        print(f"")
        print(f"--- Final Action Breakdown ---")
        for act, cnt in sorted(final_action_counts.items(), key=lambda x: -x[1]):
            print(f"  {act:30s} {cnt:5d}  ({cnt / total_events * 100:.1f}%)")
        print(f"==================================================")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
