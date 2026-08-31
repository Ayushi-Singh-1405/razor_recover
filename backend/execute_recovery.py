#!/usr/bin/env python3
"""Execute recovery actions under EXECUTION_POLICY.md.

Reads the demo transactions (tagged by a demo_scenario_state_applied
audit entry), classifies each with the Phase 1 detector's classify()
(reused directly), applies the hard STOP conditions, and — only for
high-recoverability transactions within all limits — creates a real
Razorpay payment link by reusing main.create_payment_link directly.

Safety properties:
  - No Razorpay call of any kind unless LIVE_EXECUTION_ENABLED is
    explicitly "true" in the environment.
  - Hard stops (attempts cap, already recovered) fire before any action
    and are recorded as execution_stopped audits; the amount ceiling is
    NOT a hard stop - it escalates (execution_escalated) because it
    needs human judgment, matching low-recoverability handling.
  - Low recoverability escalates and is never actioned.
  - Real actions are capped at MAX_REAL_RECOVERY_ACTIONS per run.
  - Transactions that already have a payment link are never re-actioned.

Usage:
    python execute_recovery.py            # gate check only (default: disabled)
    LIVE_EXECUTION_ENABLED=true python execute_recovery.py
"""

import sys

from db import SessionLocal
from detect_at_risk import classify
from execution_config import (
    LIVE_EXECUTION_ENABLED,
    MAX_ATTEMPTS,
    MAX_AUTOMATED_AMOUNT_PAISE,
    MAX_REAL_RECOVERY_ACTIONS,
)
from main import create_payment_link
from models import AuditLog, Transaction


def write_audit(db, transaction_id, event: str, details: dict) -> None:
    """Record one execution audit entry and commit."""
    db.add(AuditLog(
        transaction_id=transaction_id,
        event=event,
        details={**details, "phase": "execution_policy"},
    ))
    db.commit()


def main() -> int:
    # Gate: no Razorpay calls of any kind unless explicitly enabled.
    if not LIVE_EXECUTION_ENABLED:
        print("Live execution is DISABLED (LIVE_EXECUTION_ENABLED is not 'true').")
        print("No Razorpay calls were made. Exiting.")
        print("To enable: LIVE_EXECUTION_ENABLED=true python execute_recovery.py")
        return 1

    print("=" * 70)
    print("  Recovery Execution Run (EXECUTION_POLICY.md)")
    print("=" * 70)
    print(f"Live execution         : ENABLED")
    print(f"Amount cap             : ₹{MAX_AUTOMATED_AMOUNT_PAISE / 100:,.0f}")
    print(f"Attempt cap            : {MAX_ATTEMPTS}")
    print(f"Max real actions (run) : {MAX_REAL_RECOVERY_ACTIONS}")
    print()

    db = SessionLocal()
    counters = {
        "processed": 0, "actions": 0, "stopped": 0,
        "escalated": 0, "capped": 0, "skipped": 0, "failed": 0,
    }

    try:
        tagged = (
            db.query(AuditLog.transaction_id)
            .filter(AuditLog.event == "demo_scenario_state_applied")
            .distinct()
            .all()
        )
        txn_ids = [row[0] for row in tagged]
        txns = (
            db.query(Transaction)
            .filter(Transaction.id.in_(txn_ids))
            .order_by(Transaction.created_at.asc())
            .all()
        )
        print(f"Found {len(txns)} demo transactions tagged for execution.\n")

        for txn in txns:
            counters["processed"] += 1
            short = f"{str(txn.id)[:8]}..."

            # (a) Detector classification — reused directly, observed fields only
            detection = classify({
                "status": txn.status,
                "failure_reason": txn.failure_reason,
                "previous_recovery_attempts": txn.previous_recovery_attempts,
            })

            # (c) Policy gates first, regardless of tier:
            #     hard stops (§3), then the amount escalation (§4)
            if txn.previous_recovery_attempts >= MAX_ATTEMPTS:
                write_audit(db, txn.id, "execution_stopped", {
                    "reason": "attempts_at_cap",
                    "previous_recovery_attempts": txn.previous_recovery_attempts,
                    "max_attempts": MAX_ATTEMPTS,
                })
                print(f"{short} → STOP (attempts_at_cap)")
                counters["stopped"] += 1
                continue

            if txn.amount_paise > MAX_AUTOMATED_AMOUNT_PAISE:
                write_audit(db, txn.id, "execution_escalated", {
                    "reason": "amount_above_cap",
                })
                print(f"{short} → ESCALATE (amount_above_cap)")
                counters["escalated"] += 1
                continue

            if txn.status == "recovered":
                # A transaction that was already actioned and then paid via
                # webhook has a complete, fully-audited lifecycle. Re-running
                # the gate must not append duplicate already_recovered entries
                # — that would flip its recorded decision on the dashboard.
                prior_action = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.transaction_id == txn.id,
                        AuditLog.event == "execution_action_taken",
                    )
                    .first()
                )
                if prior_action:
                    print(f"{short} → SKIP (already recovered following an executed action)")
                    counters["skipped"] += 1
                    continue
                write_audit(db, txn.id, "execution_stopped", {
                    "reason": "already_recovered",
                    "status": txn.status,
                })
                print(f"{short} → STOP (already_recovered)")
                counters["stopped"] += 1
                continue

            # (b) Not at risk -> log and skip
            if not detection["at_risk"]:
                print(f"{short} → SKIP (not_at_risk, tier={detection['recoverability']})")
                counters["skipped"] += 1
                continue

            # (d) Low recoverability -> escalate, never action
            if detection["recoverability"] == "low":
                write_audit(db, txn.id, "execution_escalated", {
                    "reason": "low_recoverability",
                })
                print(f"{short} → ESCALATE (low_recoverability)")
                counters["escalated"] += 1
                continue

            # (e) High recoverability -> real action, subject to the volume cap
            if detection["recoverability"] == "high":
                if counters["actions"] >= MAX_REAL_RECOVERY_ACTIONS:
                    write_audit(db, txn.id, "execution_capped", {
                        "reason": "max_real_recovery_actions_reached",
                        "actions_taken": counters["actions"],
                        "max_real_recovery_actions": MAX_REAL_RECOVERY_ACTIONS,
                    })
                    print(f"{short} → CAPPED (max_real_recovery_actions)")
                    counters["capped"] += 1
                    continue

                if txn.razorpay_payment_link_id:
                    # Never re-intervene on a transaction we already linked.
                    print(f"{short} → SKIP (payment link already exists: "
                          f"{txn.razorpay_payment_link_id})")
                    counters["skipped"] += 1
                    continue

                try:
                    response = create_payment_link(transaction_id=str(txn.id))
                except Exception as exc:
                    write_audit(db, txn.id, "execution_action_failed", {
                        "reason": "payment_link_creation_failed",
                        "error": str(exc),
                    })
                    print(f"{short} → FAILED (payment link creation: {exc})")
                    counters["failed"] += 1
                    continue

                counters["actions"] += 1
                write_audit(db, txn.id, "execution_action_taken", {
                    "payment_link_id": response.payment_link_id,
                    "razorpay_order_id": txn.razorpay_order_id,
                    "amount_paise": txn.amount_paise,
                })
                print(f"{short} → ACTION (payment_link_id={response.payment_link_id})")
                continue

            # Defensive: at_risk but tier none (e.g. detector raised its own
            # exhaustion flag) -> STOP per Section 2.3.
            write_audit(db, txn.id, "execution_stopped", {
                "reason": "tier_none",
                "risk_reason": detection["risk_reason"],
            })
            print(f"{short} → STOP (tier_none: {detection['risk_reason']})")
            counters["stopped"] += 1

        print()
        print("=" * 70)
        print("  Execution Summary")
        print("=" * 70)
        print(f"Transactions processed : {counters['processed']}")
        print(f"Actions taken          : {counters['actions']}")
        print(f"Stopped                : {counters['stopped']}")
        print(f"Escalated              : {counters['escalated']}")
        print(f"Capped                 : {counters['capped']}")
        print(f"Skipped                : {counters['skipped']}")
        print(f"Failed                 : {counters['failed']}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
