# Gate B Dry Run — 5-Event Agent Decision Test

**Purpose:** Verify the Phase 2 AI recovery decision agent end-to-end on a small sample before the full Gate B run.

**No application code, database schema, prompts, or configuration were changed for this test.** The run used `backend/run_agent.py --limit 5` against the existing benchmark dataset.

---

## Run Metadata

| Field | Value |
|---|---|
| Date/time of run | 2026-08-28 15:27 UTC (20:57 IST) |
| Model | `nvidia/nemotron-3-super-120b-a12b:free` (via OpenRouter) |
| Dataset | 1,000 synthetic events, seed 42 |
| At-risk events available | 662 |
| Events evaluated | 5 (`--limit 5`) |
| LLM reached | 5/5 (100%) |
| Pure AI decisions | 5/5 (100%) |
| Gated overrides | 0 |
| LLM failures | 0 |

## Decision Summary

### Final actions

| Action | Count |
|---|---:|
| `recover_now` | 3 |
| `send_payment_link` | 1 |
| `stop` | 1 |

### Confidence range

0.71 – 0.81 (all above the 0.5 post-filter gate, so no gated overrides occurred).

### Pre-filter / post-filter activity

- No event triggered a pre-filter (none had `previous_recovery_attempts >= 3`; no amount exceeded ₹18,000).
- No post-filter override fired: all 5 recommended actions were valid enum values and all confidences were >= 0.5.
- Every decision recorded `decision_path = ai_decision`, `override_reason = NULL`.

---

## Per-Event Results

> **Evaluation-only notice:** the two rightmost columns (`Ground-truth outcome`, `Aligned?`) come from the benchmark's pre-generated ground-truth fields. This information was **NOT shown to the agent** — it is recorded here solely for offline evaluation per `GROUND_TRUTH_POLICY.md` §11.

| # | Failure reason | Payment method | Amount | Relevant enriched context | Recommended action | Recovery prob. | Confidence | Ground-truth outcome *(eval-only)* | Aligned? *(eval-only)* |
|---|---|---|---:|---|---|---:|---:|---|---|
| 1 | `network_error` | upi | ₹2,564.31 | tenure 13d · 0 succ / 1 failed · AOV ₹2,378.93 · checkout 148s · 0 prior attempts | `recover_now` | 0.72 | 0.81 | `recovered` (recoverable) | Yes |
| 2 | `network_error` | netbanking | ₹7,221.62 | tenure 10d · 0 succ / 1 failed · AOV ₹2,577.52 · checkout 399s · 1 prior attempt, 159h ago | `recover_now` | 0.62 | 0.71 | `recovered` (recoverable) | Yes |
| 3 | `customer_abandoned` | netbanking | ₹15,575.48 | tenure 2d · 0 succ / 2 failed · AOV ₹799.24 · checkout 162s · 0 prior attempts | `send_payment_link` | 0.38 | 0.71 | `recovered` (recoverable) | Yes |
| 4 | `customer_abandoned` | upi | ₹4,096.72 | tenure 38d · 0 succ / 2 failed · AOV ₹1,787.38 · checkout 453s · 2 prior attempts, last 130h ago | `stop` | 0.12 | 0.78 | `not_recovered` (not recoverable) | Yes |
| 5 | `otp_timeout` | card | ₹10,998.20 | tenure 54d · 0 succ / 1 failed · AOV ₹783.02 · checkout 118s · 0 prior attempts | `recover_now` | 0.62 | 0.71 | `recovered` (recoverable) | Yes |

### Observations

- **Ground-truth alignment observed: 5/5.** The agent attempted recovery on all 4 ground-truth-recoverable events and correctly withheld intervention (`stop`) on the single non-recoverable event.
- **Bad interventions observed: 0.** The only non-recoverable event was stopped, so no wasted intervention and no ₹200 penalty applies.
- **Potential recovered revenue (if simulated):** ₹36,359.61 (events 1, 2, 3, 5) with 0 penalty → net ₹36,359.61 on this sample. This is a 5-event sample and is **not** a Gate B verdict.
- The agent's reasoning referenced the enriched context (amount vs. historical AOV deviation, checkout duration, tenure, prior attempts) — e.g., event 3 flagged the ₹15,575 order as a ~19× deviation from the ₹799 AOV, and event 4 weighted two prior failed attempts toward `stop`.

---

## Caveats

- Sample size is 5 of 662 eligible events (first 5 by `created_at ASC`); results are directional only.
- Ground-truth alignment here does not establish agent superiority — the full baseline-vs-AI comparison (all 662 events, same simulation rules) is still required for the Gate B verdict.
- The `--limit 5` run cleared and repopulated `agent_decisions`; the full-run table now contains only these 5 decisions until the next full run.
