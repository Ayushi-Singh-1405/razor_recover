#!/usr/bin/env python3
"""Detect at-risk synthetic payment events.

Usage:
    python detect_at_risk.py
"""
import uuid
from collections import Counter

import psycopg2
from psycopg2.extras import execute_values

from config import DATABASE_URL

BATCH_SIZE = 100


def classify(row: dict) -> dict:
    attempts = row["previous_recovery_attempts"]
    status = row["status"]
    reason = row["failure_reason"]

    if status == "succeeded":
        return {"at_risk": False, "recoverability": "none", "risk_reason": "NOT_AT_RISK"}

    if attempts >= 3:
        return {"at_risk": True, "recoverability": "none", "risk_reason": "EXHAUSTED_ATTEMPTS"}

    if status == "failed" and reason in ("network_error", "otp_timeout"):
        return {"at_risk": True, "recoverability": "high", "risk_reason": "TRANSIENT_FAILURE"}

    if status == "failed" and reason in ("insufficient_funds", "card_declined"):
        return {"at_risk": True, "recoverability": "low", "risk_reason": "LOW_RECOVERY_PROBABILITY"}

    if status == "abandoned_checkout":
        return {"at_risk": True, "recoverability": "high", "risk_reason": "CHECKOUT_ABANDONMENT"}

    return {"at_risk": False, "recoverability": "none", "risk_reason": "NOT_AT_RISK"}


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, amount_paise, status, failure_reason, "
            "previous_recovery_attempts, previous_successful_payments "
            "FROM synthetic_events ORDER BY created_at"
        )
        events = cur.fetchall()
        col_names = [
            "id", "amount_paise", "status", "failure_reason",
            "previous_recovery_attempts", "previous_successful_payments",
        ]
        total = len(events)
        print(f"Read {total} events from synthetic_events.")

        cur.execute("DELETE FROM detection_results")
        conn.commit()
        print("Cleared existing detection_results.")

        risk_reason_counts = Counter()
        recoverability_counts = Counter()
        rows = []
        for ev in events:
            ev_dict = dict(zip(col_names, ev))
            result = classify(ev_dict)
            risk_reason_counts[result["risk_reason"]] += 1
            recoverability_counts[result["recoverability"]] += 1
            rows.append((
                str(uuid.uuid4()),
                str(ev_dict["id"]),
                result["at_risk"],
                result["recoverability"],
                result["risk_reason"],
            ))

        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        for i in range(0, total, BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            execute_values(
                cur,
                "INSERT INTO detection_results "
                "(id, synthetic_event_id, at_risk, recoverability, risk_reason) "
                "VALUES %s",
                batch,
                page_size=BATCH_SIZE,
            )
            conn.commit()
            print(
                f"Inserted batch {batch_num}/{total_batches} "
                f"({min(i + BATCH_SIZE, total)}/{total} rows)"
            )

        cur.execute("SELECT count(*) FROM detection_results")
        actual = cur.fetchone()[0]
        if actual != total:
            raise RuntimeError(
                f"Row count mismatch: detection_results={actual}, synthetic_events={total}"
            )

        print(f"\nVerified: {actual} rows in detection_results.")
        print(f"\nRisk reason breakdown:")
        for reason, cnt in sorted(risk_reason_counts.items(), key=lambda x: -x[1]):
            print(f"  {reason:35s} {cnt:5d}  ({cnt / total * 100:.1f}%)")
        print(f"\nRecoverability breakdown:")
        for tier, cnt in sorted(recoverability_counts.items(), key=lambda x: -x[1]):
            print(f"  {tier:35s} {cnt:5d}  ({cnt / total * 100:.1f}%)")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
