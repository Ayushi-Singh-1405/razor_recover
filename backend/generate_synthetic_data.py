#!/usr/bin/env python3
"""Generate synthetic payment events for RecoverAI evaluation.

Usage:
    python generate_synthetic_data.py --seed 42 --count 1000
"""
import argparse
import hashlib
import json
import random
import sys
import uuid
from datetime import datetime, timezone, timedelta
from collections import Counter

import psycopg2
from psycopg2.extras import execute_values

from config import DATABASE_URL

ALLOWED_STATUSES = {"succeeded", "failed", "authorized_not_captured", "abandoned_checkout"}
ALLOWED_FAILURE_REASONS = {
    None, "insufficient_funds", "card_declined",
    "network_error", "otp_timeout", "customer_abandoned",
}
ALLOWED_OUTCOMES = {"would_recover", "would_not_recover", "not_applicable"}


def _rand_hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def generate_events(seed: int, count: int) -> list[dict]:
    rng = random.Random(seed)

    base_time = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

    repeat_pool_size = max(1, int(count * 0.2))
    repeat_customers = [f"cust_repeat_{i}" for i in range(repeat_pool_size)]

    events = []
    for i in range(count):
        roll = rng.random()

        if roll < 0.35:
            status = "succeeded"
            failure_reason = None
            gt_recoverable = False
            gt_outcome = "not_applicable"
            gt_recovered_amount = 0

        elif roll < 0.60:
            status = "failed"
            failure_reason = rng.choice(["network_error", "otp_timeout"])
            gt_recoverable = True
            gt_outcome = "would_recover"
            gt_recovered_amount = 0  # set after amount_paise

        elif roll < 0.80:
            status = "failed"
            failure_reason = rng.choice(["insufficient_funds", "card_declined"])
            if rng.random() < 0.5:
                gt_recoverable = True
                gt_outcome = "would_recover"
                gt_recovered_amount = 0
            else:
                gt_recoverable = False
                gt_outcome = "would_not_recover"
                gt_recovered_amount = 0

        elif roll < 0.95:
            status = "abandoned_checkout"
            failure_reason = "customer_abandoned"
            if rng.random() < 0.8:
                gt_recoverable = True
                gt_outcome = "would_recover"
                gt_recovered_amount = 0
            else:
                gt_recoverable = False
                gt_outcome = "would_not_recover"
                gt_recovered_amount = 0

        else:
            status = rng.choice(["failed", "abandoned_checkout"])
            failure_reason = (
                rng.choice(["network_error", "otp_timeout", "insufficient_funds"])
                if status == "failed"
                else "customer_abandoned"
            )
            gt_recoverable = False
            gt_outcome = "would_not_recover"
            gt_recovered_amount = 0

        amount_paise = rng.randint(10000, 2000000)

        if gt_recoverable:
            gt_recovered_amount = amount_paise

        if rng.random() < 0.2:
            customer_ref = rng.choice(repeat_customers)
            previous_successful_payments = rng.randint(1, 10)
            previous_recovery_attempts = rng.randint(0, 2)
        else:
            customer_ref = f"cust_{_rand_hex(rng, 16)}"
            previous_successful_payments = 0
            previous_recovery_attempts = 0

        created_at = base_time - timedelta(
            seconds=rng.randint(0, 30 * 24 * 60 * 60)
        )

        event = {
            "amount_paise": amount_paise,
            "status": status,
            "failure_reason": failure_reason,
            "customer_ref": customer_ref,
            "previous_successful_payments": previous_successful_payments,
            "previous_recovery_attempts": previous_recovery_attempts,
            "created_at": created_at,
            "ground_truth_recoverable": gt_recoverable,
            "ground_truth_outcome": gt_outcome,
            "ground_truth_recovered_amount": gt_recovered_amount,
        }
        event["raw_payload"] = {
            "event": f"payment.{status}" if status != "succeeded" else "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": f"pay_{_rand_hex(rng, 14)}",
                        "order_id": f"order_{_rand_hex(rng, 14)}",
                        "amount": amount_paise,
                        "status": status,
                    }
                }
            },
        }
        events.append(event)

    exhausted_count = max(1, int(count * 0.05))
    exhausted_indices = rng.sample(range(count), exhausted_count)
    for idx in exhausted_indices:
        events[idx]["previous_recovery_attempts"] = rng.randint(3, 5)
        events[idx]["ground_truth_recoverable"] = False
        events[idx]["ground_truth_outcome"] = "would_not_recover"
        events[idx]["ground_truth_recovered_amount"] = 0

    return events


def validate(events: list[dict], count: int) -> None:
    if len(events) != count:
        raise ValueError(f"Expected {count} events, generated {len(events)}")

    status_counts = Counter()
    reason_counts = Counter()
    for i, e in enumerate(events):
        if e["status"] not in ALLOWED_STATUSES:
            raise ValueError(f"Event {i}: invalid status '{e['status']}'")

        if e["failure_reason"] not in ALLOWED_FAILURE_REASONS:
            raise ValueError(f"Event {i}: invalid failure_reason '{e['failure_reason']}'")

        if e["failure_reason"] is None and e["status"] != "succeeded":
            raise ValueError(
                f"Event {i}: failure_reason is null but status is '{e['status']}'"
            )

        if e["failure_reason"] is not None and e["status"] == "succeeded":
            raise ValueError(
                f"Event {i}: failure_reason is '{e['failure_reason']}' but status is 'succeeded'"
            )

        if e["amount_paise"] <= 0:
            raise ValueError(f"Event {i}: amount_paise={e['amount_paise']} is not > 0")

        if e["status"] == "succeeded" and e["ground_truth_recoverable"]:
            raise ValueError(
                f"Event {i}: status='succeeded' but ground_truth_recoverable=true"
            )

        if e["ground_truth_outcome"] not in ALLOWED_OUTCOMES:
            raise ValueError(
                f"Event {i}: invalid ground_truth_outcome '{e['ground_truth_outcome']}'"
            )

        status_counts[e["status"]] += 1
        reason_counts[e["failure_reason"] or "null"] += 1

    print("\nValidation passed.")
    print(f"\nStatus breakdown ({len(events)} total):")
    for status, cnt in sorted(status_counts.items()):
        print(f"  {status:30s} {cnt:5d}  ({cnt / len(events) * 100:.1f}%)")

    print(f"\nFailure reason breakdown:")
    for reason, cnt in sorted(reason_counts.items()):
        print(f"  {reason:30s} {cnt:5d}  ({cnt / len(events) * 100:.1f}%)")


def checksum(events: list[dict]) -> str:
    blob = json.dumps(events, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def insert_events(events: list[dict], expected_count: int) -> None:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    batch_size = 100
    try:
        cur.execute("DELETE FROM detection_results")
        cur.execute("DELETE FROM synthetic_events")
        conn.commit()
        print("Cleared existing rows from detection_results and synthetic_events.")

        rows = []
        for e in events:
            rows.append((
                str(uuid.uuid4()),
                e["amount_paise"],
                e["status"],
                e["failure_reason"],
                e["customer_ref"],
                e["previous_successful_payments"],
                e["previous_recovery_attempts"],
                e["created_at"].isoformat(),
                json.dumps(e["raw_payload"]),
                e["ground_truth_recoverable"],
                e["ground_truth_outcome"],
                e["ground_truth_recovered_amount"],
            ))

        total_batches = (len(rows) + batch_size - 1) // batch_size
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            batch_num = i // batch_size + 1
            execute_values(
                cur,
                "INSERT INTO synthetic_events "
                "(id, amount_paise, status, failure_reason, customer_ref, "
                "previous_successful_payments, previous_recovery_attempts, "
                "created_at, raw_payload, ground_truth_recoverable, "
                "ground_truth_outcome, ground_truth_recovered_amount) "
                "VALUES %s",
                batch,
                page_size=batch_size,
            )
            conn.commit()
            print(
                f"Inserted batch {batch_num}/{total_batches} "
                f"({min(i + batch_size, len(rows))}/{len(rows)} rows)"
            )

        cur.execute("SELECT count(*) FROM synthetic_events")
        actual = cur.fetchone()[0]
        if actual != expected_count:
            raise RuntimeError(
                f"Row count mismatch: inserted {actual}, expected {expected_count}"
            )
        print(f"Verified: {actual} rows in synthetic_events.")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic payment events")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument("--count", type=int, default=1000, help="Number of events (default: 1000)")
    args = parser.parse_args()

    print(f"Generating {args.count} events with seed={args.seed}...")
    events = generate_events(args.seed, args.count)

    validate(events, args.count)

    h1 = checksum(events)
    print(f"\nChecksum (run 1): {h1}")

    events2 = generate_events(args.seed, args.count)
    h2 = checksum(events2)
    print(f"Checksum (run 2): {h2}")

    if h1 == h2:
        print("Reproducibility confirmed: both runs produced identical data.")
    else:
        print("ERROR: checksums differ — reproducibility broken!")
        sys.exit(1)

    insert_events(events, args.count)


if __name__ == "__main__":
    main()
