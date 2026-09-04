# Nemotron Sample Evaluation

*Evaluates the pinned nemotron model on 5- and 15-event samples of the benchmark, with a same-events comparison against the auto-router run.*

**Model:** nvidia/nemotron-3-super-120b-a12b:free (via OpenRouter)
**Sample:** 15 of 662 at-risk events (first 15 by created_at, seed-42 dataset) + separate 5-event dry run
**Labeling era:** pre amount-above relabel (execution-layer labeling; agent decision space unchanged)
**Source:** evaluation/nemotron_15_event_sample.txt (run outputs). The `agent_decisions` rows from these runs were later overwritten by the full 662-event run — this file and the run logs are the record.
**Companion:** 5-event dry run artifact: `tests/gate_b_dry_run_5.md`

> **CAVEAT:** n=15 and n=5 — directional only. Do not mix these numbers with the 662-event openrouter/free report (`agent_performance_result.txt`).

## 1. Five-Event Dry Run (`tests/gate_b_dry_run_5.md`)

| Measure | Value |
|---|---:|
| Aligned with ground truth | 5/5 |
| Bad interventions | 0 |
| Potential net recovered | ₹36,359.61 |
| Confidence range | 0.71 – 0.81 |

## 2. Fifteen-Event Sample — Decision Paths

| Decision path | Count |
|---|---:|
| ai_decision | 11 |
| pre_filtered | 3 (high_value ×2, attempts_exhausted ×1) |
| gated_override | 1 (llm_call_failed — truncated JSON) |

LLM reached: 12 of 15. Pure AI decisions: 11. LLM format failures: 1/12 (8.3%).

## 3. Fifteen-Event Sample — Outcomes vs Ground Truth

Ground truth is evaluation-only; never shown to the agent.

| Measure | Value |
|---|---:|
| Aligned with ground truth | 11/15 |
| Misses | 4 — all missed recoverable revenue (zero false positives) |
| Recovery attempts | 8 — all on ground-truth recoverable events (precision 100% at n=8) |
| Bad interventions | 0 (all 3 non-recoverable events withheld) |
| Recovered (simulated) | ₹69,753.88 |
| Missed recoverable | ₹46,492.97 |

### Miss detail

| Event | Amount | Reason |
|---|---:|---|
| Event 3 | ₹15,575.48 | AI chose escalate_to_merchant on a recoverable abandoned checkout (vs ₹799 AOV, 2-day tenure) — defensible caution, but a miss under the benchmark convention |
| Event 6 | ₹19,074.83 | High-value pre-filter (> ₹18,000) — policy, not model error |
| Event 8 | ₹9,799.11 | LLM returned logically good reasoning but truncated JSON (missing closing brace) → gated fallback to escalate. Format robustness, not reasoning quality |
| Event 15 | ₹2,043.55 | AI chose stop on a recoverable abandoned checkout (zero successes, 2 failures) — conservative prior on new customers |

## 4. Reasoning Quality (11 pure-AI decisions)

Every pure-AI decision cites concrete enriched signals: checkout duration (all 11), AOV/amount deviation (events 3, 4, 9, 10, 12, 13, 15), prior-attempt recency (2, 4), success history (8–11 context). None rely on failure_reason alone. Closest to failure-reason-led: events 5 and 13 ("otp_timeout is transient") — both still anchor on engagement signals.

## 5. Same-Events Comparison: nemotron vs openrouter/free

Identical 15 events; router decisions from the 662-event run.

| Measure | nemotron (pinned) | openrouter/free (router) |
|---|---:|---:|
| Decision-identical events | — | 8/15 |
| Alignment (same events) | 11/15 | 14/15 |
| Attempted recovery | 8 (all recoverable) | 11 (all recoverable) |
| Bad interventions | 0 | 0 |
| Net recovered (simulated) | ₹69,753.88 | ₹97,172.02 (+₹27,418.14) |

### Decisive differences (all three favor the router)

| Event | Effect | Note |
|---|---:|---|
| Event 8 | +₹9,799.11 | Router produced a valid send_payment_link where nemotron's JSON truncated |
| Event 3 | +₹15,575.48 | Router attempted (send_payment_link) where nemotron escalated |
| Event 15 | +₹2,043.55 | Router attempted where nemotron stopped |

Events 2, 5, 12, 13 differ only in flavor (recover_now vs send_payment_link) — both aligned on all four.

## 6. Takeaways for Gate B

- Nemotron's reasoning quality is strong (no failure_reason-only decisions; correct withholding of all non-recoverable events).
- Its cost is conservatism: 3 missed recoverable events, plus one format failure that discarded good reasoning.
- On identical events, the auto-router out-earned nemotron by ₹27.4K — driven by format robustness and less conservative escalation, not by better per-attempt precision (both 0 bad interventions; router 11/11 vs nemotron 8/8 on recoverable attempts).
- Full-run economics (662 events, openrouter/free) remain the authoritative comparison: `agent_performance_result.md`.
