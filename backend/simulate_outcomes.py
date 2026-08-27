#!/usr/bin/env python3
"""Simulate recovery outcomes for a set of decisions.

Compares a decision-maker's actions against ground truth to produce
business-level metrics (₹ recovered, bad interventions, net ₹).

Rules from GROUND_TRUTH_POLICY.md:
  Section 20.7 — simulated_intervention_succeeds := ground_truth_recoverable == True
  Section 20.8 — penalty_per_bad_intervention = ₹200 (20000 paise), flat

Usage (baseline):
    python simulate_outcomes.py
"""

import os

import psycopg2

from config import DATABASE_URL

REPORT_DIR = os.path.join(os.path.dirname(__file__), "reports")

# Section 20.8: flat penalty per bad intervention, fixed before comparison
PENALTY_PER_BAD_INTERVENTION_PAISE = 20_000  # ₹200

# Actions that count as "attempted recovery" — any of these triggers
# simulation success/failure accounting per Section 20.7.
# stop / escalate_to_merchant / no_action are excluded.
RECOVERY_ACTIONS = frozenset({
    "recover_now",
    "send_payment_link",
    "wait_and_retry",
})


def simulate(event_action_pairs):
    """Run simulation over (event, action_taken) pairs.

    Args:
        event_action_pairs: iterable of (event_dict, action_taken) where each
            event_dict has keys:
                id, amount_paise, ground_truth_recoverable,
                ground_truth_recovered_amount

    Returns:
        dict with summary statistics
    """
    candidate_decisions = 0
    successful_recoveries = 0
    total_recovered_paise = 0
    bad_interventions = 0

    for ev, action in event_action_pairs:
        if action not in RECOVERY_ACTIONS:
            continue

        candidate_decisions += 1

        if ev["ground_truth_recoverable"]:
            successful_recoveries += 1
            total_recovered_paise += ev["ground_truth_recovered_amount"]
        else:
            bad_interventions += 1

    total_penalty_paise = bad_interventions * PENALTY_PER_BAD_INTERVENTION_PAISE
    net_recovered_paise = total_recovered_paise - total_penalty_paise

    return {
        "candidate_decisions": candidate_decisions,
        "successful_recoveries": successful_recoveries,
        "total_recovered_paise": total_recovered_paise,
        "bad_interventions": bad_interventions,
        "total_penalty_paise": total_penalty_paise,
        "net_recovered_paise": net_recovered_paise,
    }


def build_baseline_pairs(conn):
    """Load events joined with detection results, return (event, action) pairs.

    Baseline logic: at_risk=True → "recover_now", at_risk=False → "no_action".
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT "
            "  se.id, se.amount_paise, se.ground_truth_recoverable, "
            "  se.ground_truth_recovered_amount, dr.at_risk "
            "FROM synthetic_events se "
            "JOIN detection_results dr ON dr.synthetic_event_id = se.id"
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    pairs = []
    for event_id, amount, gt_recoverable, gt_amount, at_risk in rows:
        event = {
            "id": str(event_id),
            "amount_paise": amount,
            "ground_truth_recoverable": gt_recoverable,
            "ground_truth_recovered_amount": gt_amount,
        }
        action = "recover_now" if at_risk else "no_action"
        pairs.append((event, action))

    return pairs


def format_report(stats, total_events, label):
    lines = []
    lines.append("=" * 50)
    lines.append(f"  Day 3 Baseline Simulation Report")
    lines.append("=" * 50)
    lines.append("")
    lines.append(f"Total events:           {total_events}")
    lines.append(f"Decision maker:         {label}")
    lines.append("")
    lines.append("--- Recovery Accounting (Section 20.7) ---")
    lines.append(f"  Candidate decisions:     {stats['candidate_decisions']}")
    lines.append(f"  Successful recoveries:   {stats['successful_recoveries']}")
    lines.append(
        f"  Total recovered:         ₹{stats['total_recovered_paise'] // 100:,}"
    )
    lines.append("")
    lines.append("--- Bad Intervention Accounting (Section 20.8) ---")
    lines.append(f"  Bad interventions:       {stats['bad_interventions']}")
    lines.append(
        f"  Penalty per intervention: ₹{PENALTY_PER_BAD_INTERVENTION_PAISE // 100}"
    )
    lines.append(
        f"  Total penalty cost:      ₹{stats['total_penalty_paise'] // 100:,}"
    )
    lines.append("")
    lines.append("--- Net Outcome ---")
    lines.append(
        f"  Net ₹ recovered:         ₹{stats['net_recovered_paise'] // 100:,}"
    )
    lines.append("")
    lines.append("=" * 50)

    return "\n".join(lines)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        pairs = build_baseline_pairs(conn)
    finally:
        conn.close()

    total_events = len(pairs)
    stats = simulate(pairs)
    report = format_report(stats, total_events, label="Deterministic baseline")

    print(report)

    os.makedirs(REPORT_DIR, exist_ok=True)
    report_path = os.path.join(REPORT_DIR, "day3_baseline_simulation.txt")
    with open(report_path, "w") as f:
        f.write(report + "\n")
    print(f"\nReport written to {report_path}")


if __name__ == "__main__":
    main()
