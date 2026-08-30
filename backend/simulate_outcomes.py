#!/usr/bin/env python3
"""Simulate recovery outcomes for a set of decisions.

Compares a decision-maker's actions against ground truth to produce
business-level metrics (₹ recovered, bad interventions, net ₹), for both
the deterministic baseline (detection_results) and the AI recovery agent
(agent_decisions), and prints a side-by-side comparison.

Rules from GROUND_TRUTH_POLICY.md:
  Section 20.7 — simulated_intervention_succeeds := ground_truth_recoverable == True
  Section 20.8 — penalty_per_bad_intervention = ₹200 (20000 paise), flat

Action semantics (identical for both systems):
  recover_now / send_payment_link / wait_and_retry -> attempted recovery
  stop / escalate_to_merchant / no_action          -> excluded entirely

Usage:
    python simulate_outcomes.py
"""

import os
from collections import Counter

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


def build_agent_pairs(conn):
    """Load events joined with agent decisions, return (event, action) pairs.

    Mirror of build_baseline_pairs: same event dict shape, but the action
    comes from the agent's recorded recommended_action. Feeds the same
    simulate() function — no simulation logic is duplicated.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT "
            "  se.id, se.amount_paise, se.ground_truth_recoverable, "
            "  se.ground_truth_recovered_amount, ad.recommended_action "
            "FROM agent_decisions ad "
            "JOIN synthetic_events se ON se.id = ad.synthetic_event_id"
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    pairs = []
    for event_id, amount, gt_recoverable, gt_amount, action in rows:
        event = {
            "id": str(event_id),
            "amount_paise": amount,
            "ground_truth_recoverable": gt_recoverable,
            "ground_truth_recovered_amount": gt_amount,
        }
        pairs.append((event, action))

    return pairs


def fetch_agent_breakdowns(conn):
    """Fetch decision-path / override / targeting breakdowns for the report.

    Returns (path_counts, override_reasons, attempted_by_gt, attempted_by_action):
      path_counts          Counter over decision_path
      override_reasons     Counter over override_reason for gated_override rows
      attempted_by_gt      {True: n, False: n} — attempted-recovery actions split
                           by actual ground_truth_recoverable (targeting quality)
      attempted_by_action  per attempted action: {action: {True: n, False: n}}
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT ad.decision_path, ad.override_reason, ad.recommended_action, "
            "  se.ground_truth_recoverable "
            "FROM agent_decisions ad "
            "JOIN synthetic_events se ON se.id = ad.synthetic_event_id"
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    path_counts = Counter()
    override_reasons = Counter()
    attempted_by_gt = {True: 0, False: 0}
    attempted_by_action = {}

    for path, reason, action, gt_recoverable in rows:
        path_counts[path] += 1
        if path == "gated_override" and reason:
            override_reasons[reason] += 1
        if action in RECOVERY_ACTIONS:
            gt = bool(gt_recoverable)
            attempted_by_gt[gt] += 1
            attempted_by_action.setdefault(action, {True: 0, False: 0})[gt] += 1

    return path_counts, override_reasons, attempted_by_gt, attempted_by_action


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


def format_comparison_report(total_at_risk, agent_decisions_count,
                             baseline_stats, agent_stats,
                             path_counts, override_reasons,
                             attempted_by_gt, attempted_by_action):
    """Build the Day 3 experiment comparison report (baseline vs agent)."""
    lines = []
    lines.append("=" * 64)
    lines.append("  Day 3 Experiment Result — Baseline vs AI Recovery Agent")
    lines.append("=" * 64)
    lines.append("")
    lines.append(f"Total at-risk events:        {total_at_risk}")
    lines.append(f"Agent decisions recorded:    {agent_decisions_count}")
    if agent_decisions_count != total_at_risk:
        lines.append(
            f"WARNING: agent run is INCOMPLETE ({agent_decisions_count} of "
            f"{total_at_risk}) — comparison covers recorded decisions only."
        )
    lines.append("")
    lines.append("--- Side-by-Side Comparison (GROUND_TRUTH_POLICY §20.7 / §20.8) ---")
    lines.append("")
    lines.append("| System | Candidate decisions | Successful recoveries | ₹ recovered | Bad interventions | Net ₹ |")
    lines.append("|---|---|---|---|---|---|")
    for label, stats in (
        ("Deterministic baseline", baseline_stats),
        ("AI recovery agent", agent_stats),
    ):
        lines.append(
            f"| {label} | {stats['candidate_decisions']} | "
            f"{stats['successful_recoveries']} | "
            f"₹{stats['total_recovered_paise'] // 100:,} | "
            f"{stats['bad_interventions']} | "
            f"₹{stats['net_recovered_paise'] // 100:,} |"
        )
    uplift = agent_stats["net_recovered_paise"] - baseline_stats["net_recovered_paise"]
    sign = "+" if uplift >= 0 else "-"
    lines.append("")
    lines.append(f"Net ₹ uplift (agent - baseline): {sign}₹{abs(uplift) // 100:,}")
    lines.append("")

    total_agent = sum(path_counts.values())
    lines.append("--- Agent Decision Path Breakdown ---")
    if total_agent == 0:
        lines.append("  (no agent decisions recorded)")
    else:
        for path in ("ai_decision", "pre_filtered", "gated_override"):
            cnt = path_counts.get(path, 0)
            lines.append(f"  {path:20s} {cnt:5d}  ({cnt / total_agent * 100:.1f}%)")
        other = total_agent - sum(path_counts.get(p, 0) for p in ("ai_decision", "pre_filtered", "gated_override"))
        if other:
            lines.append(f"  {'(other)':20s} {other:5d}")

    lines.append("")
    lines.append("--- Gated Override Reasons ---")
    if not override_reasons:
        lines.append("  (none)")
    else:
        for reason, cnt in sorted(override_reasons.items(), key=lambda x: -x[1]):
            lines.append(f"  {reason:30s} {cnt:5d}")
        lines.append("")
        lines.append("  Note: llm_call_failed = infrastructure/provider failure;")
        lines.append("        low_confidence / invalid_action_returned = model quality issue.")

    lines.append("")
    lines.append("--- Attempted-Recovery Targeting Quality (agent) ---")
    lines.append(f"  Attempted on ground-truth recoverable (correct):  {attempted_by_gt[True]:5d}")
    lines.append(f"  Attempted on non-recoverable (bad intervention):  {attempted_by_gt[False]:5d}")
    lines.append("")
    for action in ("recover_now", "send_payment_link", "wait_and_retry"):
        split = attempted_by_action.get(action, {True: 0, False: 0})
        lines.append(
            f"    {action:20s} recoverable={split[True]:4d}  non-recoverable={split[False]:4d}"
        )
    lines.append("")
    lines.append("=" * 64)

    return "\n".join(lines)


def main():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        baseline_pairs = build_baseline_pairs(conn)
        agent_pairs = build_agent_pairs(conn)
        (path_counts, override_reasons,
         attempted_by_gt, attempted_by_action) = fetch_agent_breakdowns(conn)
        total_events = len(baseline_pairs)
    finally:
        conn.close()

    # Same simulate() function for both decision-makers — identical rules.
    baseline_stats = simulate(baseline_pairs)
    agent_stats = simulate(agent_pairs)

    # At-risk events = baseline candidate decisions (at_risk=True events)
    total_at_risk = baseline_stats["candidate_decisions"]

    # Baseline-only report (existing deliverable, unchanged format)
    baseline_report = format_report(baseline_stats, total_events, label="Deterministic baseline")
    print(baseline_report)

    os.makedirs(REPORT_DIR, exist_ok=True)
    baseline_path = os.path.join(REPORT_DIR, "day3_baseline_simulation.txt")
    with open(baseline_path, "w") as f:
        f.write(baseline_report + "\n")
    print(f"\nBaseline report written to {baseline_path}")

    # Full baseline-vs-agent comparison
    comparison = format_comparison_report(
        total_at_risk=total_at_risk,
        agent_decisions_count=len(agent_pairs),
        baseline_stats=baseline_stats,
        agent_stats=agent_stats,
        path_counts=path_counts,
        override_reasons=override_reasons,
        attempted_by_gt=attempted_by_gt,
        attempted_by_action=attempted_by_action,
    )
    print("\n" + comparison)

    result_path = os.path.join(REPORT_DIR, "day3_experiment_result.txt")
    with open(result_path, "w") as f:
        f.write(comparison + "\n")
    print(f"\nExperiment result written to {result_path}")


if __name__ == "__main__":
    main()
