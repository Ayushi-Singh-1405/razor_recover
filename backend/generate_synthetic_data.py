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
ALLOWED_OUTCOMES = {"recovered", "not_recovered", "not_applicable"}
ALLOWED_PAYMENT_METHODS = ("card", "upi", "netbanking")

TIER_HIGH = "HIGH"
TIER_MEDIUM = "MEDIUM"
TIER_LOW = "LOW"
TIER_NONE = "NONE"

TIER_PROB = {TIER_HIGH: 0.85, TIER_MEDIUM: 0.50, TIER_LOW: 0.15, TIER_NONE: 0.00}

BASELINE_TIERS = {
    "network_error": TIER_HIGH,
    "otp_timeout": TIER_HIGH,
    "insufficient_funds": TIER_MEDIUM,
    "card_declined": TIER_MEDIUM,
    "customer_abandoned": TIER_MEDIUM,
}


def _rand_hex(rng: random.Random, n: int) -> str:
    return "".join(rng.choice("0123456789abcdef") for _ in range(n))


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _count_signals_favorable(e: dict) -> int:
    score = 0
    if e["previous_successful_payments"] >= 2:
        score += 1
    if e["previous_failed_payments"] <= 1:
        score += 1
    cd = e["checkout_duration_seconds"]
    if cd is not None and cd < 150:
        score += 1
    if cd is not None and cd < 300:
        score += 1
    avg = e["average_order_value"]
    if avg and avg > 0:
        ratio = abs(e["amount_paise"] - avg) / avg
        if ratio <= 0.30:
            score += 1
    tsp = e["time_since_last_successful_payment_hours"]
    if tsp is not None and tsp < 168:
        score += 1
    return score


def _adjust_tier(base_tier: str, favorable: int, total_signals: int) -> str:
    tier_order = [TIER_NONE, TIER_LOW, TIER_MEDIUM, TIER_HIGH]
    idx = tier_order.index(base_tier)
    ratio = favorable / total_signals if total_signals > 0 else 0.5
    if ratio >= 0.35:
        idx = min(idx + 1, 3)
    elif ratio < 0.10:
        idx = max(idx - 1, 0)
    return tier_order[idx]


def _compute_engagement_adjustments(e: dict) -> list[str]:
    notes = []
    if e["previous_failed_payments"] >= 6:
        notes.append("repeated_failures")
    if e["previous_recovery_attempts"] >= 2:
        tsp = e["time_since_last_recovery_attempt_hours"]
        if tsp is not None and tsp < 24:
            notes.append("recent_recovery")
    if e["customer_tenure_days"] < 7:
        notes.append("new_customer")
    cd = e["checkout_duration_seconds"]
    if cd is not None and cd > 500:
        notes.append("prolonged_checkout")
    tsp = e["time_since_last_successful_payment_hours"]
    if tsp is not None and tsp > 1500:
        notes.append("long_inactivity")
    return notes


def generate_events(seed: int, count: int) -> list[dict]:
    rng = random.Random(seed)

    base_time = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

    repeat_pool_size = max(1, int(count * 0.2))
    repeat_customers = [f"cust_repeat_{i}" for i in range(repeat_pool_size)]

    tier_counts = Counter()

    events = []
    for i in range(count):
        roll = rng.random()

        if roll < 0.35:
            status = "succeeded"
            failure_reason = None
        elif roll < 0.60:
            status = "failed"
            failure_reason = rng.choice(["network_error", "otp_timeout"])
        elif roll < 0.80:
            status = "failed"
            failure_reason = rng.choice(["insufficient_funds", "card_declined"])
        elif roll < 0.95:
            status = "abandoned_checkout"
            failure_reason = "customer_abandoned"
        else:
            status = rng.choice(["failed", "abandoned_checkout"])
            failure_reason = (
                rng.choice(["network_error", "otp_timeout", "insufficient_funds"])
                if status == "failed"
                else "customer_abandoned"
            )

        amount_paise = rng.randint(10000, 2000000)

        is_repeat = rng.random() < 0.2
        if is_repeat:
            customer_ref = rng.choice(repeat_customers)
            previous_successful_payments = rng.randint(1, 10)
            previous_recovery_attempts = rng.randint(0, 2)
        else:
            customer_ref = f"cust_{_rand_hex(rng, 16)}"
            previous_successful_payments = 0
            previous_recovery_attempts = 0

        previous_failed_payments = (
            rng.randint(0, 2)
            if previous_successful_payments <= 1
            else rng.randint(0, previous_successful_payments + 3)
        )

        if previous_successful_payments >= 5:
            customer_tenure_days = rng.randint(180, 1200)
        elif previous_successful_payments >= 2:
            customer_tenure_days = rng.randint(30, 400)
        else:
            customer_tenure_days = rng.randint(0, 60)

        if previous_successful_payments >= 5:
            average_order_value = rng.randint(20000, 800000)
        elif previous_successful_payments >= 2:
            average_order_value = rng.randint(15000, 500000)
        else:
            average_order_value = rng.randint(10000, 300000)

        if previous_successful_payments >= 5:
            time_since_last_successful_payment_hours = rng.randint(1, 200)
        elif previous_successful_payments >= 2:
            time_since_last_successful_payment_hours = rng.randint(24, 500)
        elif previous_successful_payments == 1:
            time_since_last_successful_payment_hours = rng.randint(72, 1500)
        else:
            time_since_last_successful_payment_hours = None

        if previous_recovery_attempts >= 1:
            time_since_last_recovery_attempt_hours = rng.randint(1, 168)
        else:
            time_since_last_recovery_attempt_hours = None

        if status == "succeeded":
            checkout_duration_seconds = rng.randint(30, 180)
        elif status == "abandoned_checkout":
            checkout_duration_seconds = rng.randint(60, 600)
        else:
            checkout_duration_seconds = rng.randint(20, 400)

        payment_method = rng.choice(ALLOWED_PAYMENT_METHODS)

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
            "customer_tenure_days": customer_tenure_days,
            "previous_failed_payments": previous_failed_payments,
            "average_order_value": average_order_value,
            "time_since_last_successful_payment_hours": time_since_last_successful_payment_hours,
            "time_since_last_recovery_attempt_hours": time_since_last_recovery_attempt_hours,
            "checkout_duration_seconds": checkout_duration_seconds,
            "payment_method": payment_method,
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

    for e in events:
        if e["status"] == "succeeded":
            tier = TIER_NONE
        elif e["previous_recovery_attempts"] >= 3:
            tier = TIER_NONE
        else:
            base_tier = BASELINE_TIERS.get(e["failure_reason"], TIER_MEDIUM)
            favorable = _count_signals_favorable(e)
            total = 6
            tier = _adjust_tier(base_tier, favorable, total)
            negative = _compute_engagement_adjustments(e)
            tier_order = [TIER_NONE, TIER_LOW, TIER_MEDIUM, TIER_HIGH]
            idx = tier_order.index(tier)
            if len(negative) >= 4:
                idx = max(idx - 1, 0)
            elif len(negative) >= 3 and idx == 3:
                idx = 2
            tier = tier_order[idx]

        tier_counts[tier] += 1
        prob = TIER_PROB[tier]
        e["ground_truth_recoverable"] = rng.random() < prob
        if e["ground_truth_recoverable"]:
            e["ground_truth_outcome"] = "recovered"
            e["ground_truth_recovered_amount"] = e["amount_paise"]
        else:
            e["ground_truth_outcome"] = "not_recovered"
            e["ground_truth_recovered_amount"] = 0

    print("\nRecoverability tier breakdown (before probability draw):")
    for t in (TIER_HIGH, TIER_MEDIUM, TIER_LOW, TIER_NONE):
        cnt = tier_counts[t]
        print(f"  {t:10s} {cnt:5d}  ({cnt / count * 100:.1f}%)")

    gt_true = sum(1 for e in events if e["ground_truth_recoverable"])
    gt_false = count - gt_true
    print(f"\nground_truth_recoverable breakdown:")
    print(f"  True   {gt_true:5d}  ({gt_true / count * 100:.1f}%)")
    print(f"  False  {gt_false:5d}  ({gt_false / count * 100:.1f}%)")

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

        if e["previous_recovery_attempts"] >= 3 and e["ground_truth_recoverable"]:
            raise ValueError(
                f"Event {i}: previous_recovery_attempts={e['previous_recovery_attempts']} "
                f"but ground_truth_recoverable=true"
            )

        if e["ground_truth_outcome"] not in ALLOWED_OUTCOMES:
            raise ValueError(
                f"Event {i}: invalid ground_truth_outcome '{e['ground_truth_outcome']}'"
            )

        if e["checkout_duration_seconds"] is None or e["checkout_duration_seconds"] <= 0:
            raise ValueError(
                f"Event {i}: checkout_duration_seconds={e['checkout_duration_seconds']} invalid"
            )

        if e["customer_tenure_days"] is None or e["customer_tenure_days"] < 0:
            raise ValueError(
                f"Event {i}: customer_tenure_days={e['customer_tenure_days']} invalid"
            )

        if e["payment_method"] not in ALLOWED_PAYMENT_METHODS:
            raise ValueError(
                f"Event {i}: invalid payment_method '{e['payment_method']}'"
            )

        if e["previous_failed_payments"] < 0:
            raise ValueError(
                f"Event {i}: previous_failed_payments={e['previous_failed_payments']} < 0"
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
                e["customer_tenure_days"],
                e["previous_failed_payments"],
                e["average_order_value"],
                e["time_since_last_successful_payment_hours"],
                e["time_since_last_recovery_attempt_hours"],
                e["checkout_duration_seconds"],
                e["payment_method"],
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
                "ground_truth_outcome, ground_truth_recovered_amount, "
                "customer_tenure_days, previous_failed_payments, "
                "average_order_value, time_since_last_successful_payment_hours, "
                "time_since_last_recovery_attempt_hours, "
                "checkout_duration_seconds, payment_method) "
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
