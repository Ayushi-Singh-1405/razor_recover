#!/usr/bin/env python3
"""Export the benchmark tables to CSV snapshots in /reports/data.

Regeneratable at any time: connect, select explicit columns, write UTF-8
CSVs with headers, print row counts and SHA-256 checksums. The CSVs are a
snapshot of the current database state — if the dataset is regenerated
with a different seed, re-run this script to refresh them.

Excluded on purpose: audit_logs / webhook_events / merchants (operational
tables, not benchmark data) and synthetic_events.raw_payload (JSONB bloat).

Usage:
    python export_datasets.py
"""

import csv
import hashlib
import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATABASE_URL  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reports", "data")

TABLES = {
    "synthetic_events.csv": """
        SELECT id, amount_paise, status, failure_reason, customer_ref,
               previous_successful_payments, previous_recovery_attempts,
               customer_tenure_days, previous_failed_payments,
               average_order_value,
               time_since_last_successful_payment_hours,
               time_since_last_recovery_attempt_hours,
               checkout_duration_seconds, payment_method,
               ground_truth_recoverable, ground_truth_outcome,
               ground_truth_recovered_amount, created_at
        FROM synthetic_events
        ORDER BY created_at
    """,
    "detection_results.csv": """
        SELECT dr.id, dr.synthetic_event_id, dr.at_risk, dr.recoverability,
               dr.risk_reason, dr.detected_at,
               se.ground_truth_recoverable, se.ground_truth_outcome
        FROM detection_results dr
        JOIN synthetic_events se ON se.id = dr.synthetic_event_id
        ORDER BY dr.detected_at
    """,
    "agent_decisions.csv": """
        SELECT ad.id, ad.synthetic_event_id, ad.diagnosis,
               ad.recovery_probability, ad.recommended_action, ad.reason,
               ad.confidence, ad.decision_path, ad.override_reason,
               ad.created_at,
               se.ground_truth_recoverable, se.ground_truth_outcome,
               se.ground_truth_recovered_amount
        FROM agent_decisions ad
        JOIN synthetic_events se ON se.id = ad.synthetic_event_id
        ORDER BY ad.created_at
    """,
}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

    print(f"Exporting benchmark tables to {os.path.abspath(OUT_DIR)}\n")
    with engine.connect() as conn:
        for filename, sql in TABLES.items():
            result = conn.execute(text(sql))
            rows = result.mappings().all()
            out_path = os.path.join(OUT_DIR, filename)
            if rows:
                with open(out_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                open(out_path, "w").close()

            digest = sha256_file(out_path) if os.path.getsize(out_path) else "(empty)"
            print(f"{filename:28s} {len(rows):5d} rows  sha256:{digest}")

    print("\nDone. Record the row counts and checksums in reports/data/README.md.")


if __name__ == "__main__":
    main()
