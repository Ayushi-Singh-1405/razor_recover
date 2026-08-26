#!/usr/bin/env python3
"""Evaluate detector performance against ground truth labels.

Usage:
    python evaluate.py
"""
import os
from collections import Counter

import psycopg2

from config import DATABASE_URL

REPORT_PATH = os.path.join(os.path.dirname(__file__), "reports", "day2_baseline.txt")


def main():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT "
            "  se.amount_paise, se.status, se.ground_truth_recoverable, "
            "  dr.at_risk, dr.recoverability "
            "FROM synthetic_events se "
            "JOIN detection_results dr ON dr.synthetic_event_id = se.id"
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()

    total = len(rows)

    tp = fp = tn = fn = 0
    succeeded_at_risk = 0
    total_revenue = 0
    at_risk_revenue = 0
    gt_recoverable_high = gt_recoverable_low = 0

    for amount, status, gt_recoverable, at_risk, recoverability in rows:
        total_revenue += amount
        if at_risk:
            at_risk_revenue += amount

        if status == "succeeded" and at_risk:
            succeeded_at_risk += 1

        if gt_recoverable and at_risk:
            tp += 1
        elif not gt_recoverable and at_risk:
            fp += 1
        elif not gt_recoverable and not at_risk:
            tn += 1
        elif gt_recoverable and not at_risk:
            fn += 1

        if gt_recoverable:
            if recoverability in ("high", "medium"):
                gt_recoverable_high += 1
            else:
                gt_recoverable_low += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    succeeded_ok = succeeded_at_risk == 0

    lines = []
    lines.append("=" * 50)
    lines.append("  Day 2 Baseline Evaluation Report")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"Total events evaluated: {total}")
    lines.append("")
    lines.append("--- Confusion Matrix ---")
    lines.append(f"  True Positives  (TP): {tp}")
    lines.append(f"  False Positives (FP): {fp}")
    lines.append(f"  True Negatives  (TN): {tn}")
    lines.append(f"  False Negatives (FN): {fn}")
    lines.append("")
    lines.append("--- Metrics ---")
    lines.append(f"  Precision: {precision:.4f}")
    lines.append(f"  Recall:    {recall:.4f}")
    lines.append(f"  F1 Score:  {f1:.4f}")
    lines.append("")
    lines.append("--- Sanity Check ---")
    lines.append(
        f"  status=succeeded with at_risk=True: {succeeded_at_risk} "
        f"{'PASS' if succeeded_ok else 'FAIL'}"
    )
    lines.append("")
    lines.append("--- Revenue ---")
    lines.append(f"  Total revenue:             ₹{total_revenue // 100:,}")
    lines.append(f"  Revenue (at_risk=True):    ₹{at_risk_revenue // 100:,}")
    pct = at_risk_revenue / total_revenue * 100 if total_revenue > 0 else 0
    lines.append(f"  At-risk percentage:        {pct:.1f}%")
    lines.append("")
    lines.append("--- Recoverability Tiering (ground_truth_recoverable=True only) ---")
    gt_total = gt_recoverable_high + gt_recoverable_low
    lines.append(f"  Total ground-truth recoverable: {gt_total}")
    if gt_total > 0:
        lines.append(
            f"  Assigned high/medium:  {gt_recoverable_high}  "
            f"({gt_recoverable_high / gt_total * 100:.1f}%)"
        )
        lines.append(
            f"  Assigned low/none:     {gt_recoverable_low}  "
            f"({gt_recoverable_low / gt_total * 100:.1f}%)"
        )
    lines.append("")
    lines.append("=" * 50)

    report = "\n".join(lines)
    print(report)

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(report + "\n")
    print(f"\nReport written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
