# RecoverAI — Full Project Handoff (Day 1–3, Gate A complete, Gate B in progress)

## Context

Ayu is building for Razorpay's Intern Hiring Hackathon, competing for an internship. Track: **Track 03 — AI Revenue Recovery**. Timeline: 7 days total, currently on Day 3.

Judging criteria: **Problem taste**, **Build quality**, **AI judgment** (right tool in the right place, and where you chose not to use one), **Failure recovery** (what broke, and what you did about it).

**Repo:** `~/razor_recover/`, all code lives under `backend/` (not repo root). Virtualenv at `~/razor_recover/venv/`, activate from inside `backend/` with `source ../venv/bin/activate`.

**Coding agent:** Was using OpenCode ("Big Pickle"), hit free-tier exhaustion (10h+ cooldown). OpenCode Go ($10/mo) purchase stuck on an Alipay redirect loop, unresolved. **Currently using Antigravity + Gemini as the coding agent instead** — this is fine, all prompts below are agent-agnostic.

---

## Tech Stack (Locked In)

- Backend: FastAPI + Python
- Database: Neon PostgreSQL
- ORM: SQLAlchemy + Alembic (migrations)
- Payments: Razorpay Test Mode
- AI: OpenRouter (provider-agnostic wrapper), model configurable via `OPENROUTER_MODEL` env var
- Agent: Plain Python orchestration, no LangGraph
- Frontend: **Not started — deliberately deprioritized.** Multiple reviews explicitly flagged dashboard work as the easiest way to waste a day polishing the wrong layer. Priority order locked in: AI decision quality → recovery simulation → policy/stopping → real Razorpay execution → failure scenarios → metrics → dashboard (last).

---

## Day 1 (Phase 0) — Razorpay Plumbing — COMPLETE

Built: FastAPI scaffold, 4 tables (`transactions`, `recovery_attempts`, `webhook_events`, `audit_logs`), real Razorpay Test Mode order → payment link → payment → webhook → DB update → audit trail, end to end, verified live.

**Real bugs found and fixed:**
1. Webhook signature verification failures were silently returning `200 {"status": "ignored"}` instead of `401`. Fixed to raise `HTTPException(401)`, added `webhook_signature_rejected` audit log entry.
2. Wrong event-ID source: code read `payload.get("id", "")` from the JSON body, but Razorpay sends the unique event ID in the `X-Razorpay-Event-Id` **header**, not the body. This caused every real webhook to silently no-op. Confirmed via temporary debug logging of raw payload + headers, then fixed.

Also fixed: UUID path params weren't typed (raw Postgres errors → now clean 422s); found the correct Razorpay Test Mode card (`5267 3181 8797 5449`, not the commonly-cited `4111 1111 1111 1111` which is rejected as international; OTP `1234`).

**Regression test script:** `backend/test_phase0.py` — checks idempotency, signature rejection, UUID validation, empty audit trail.

---

## Day 2 (Phase 1) — Synthetic Dataset + Deterministic Detector — COMPLETE

Before starting, an external review recommended 5 improvements, all adopted: ground truth fields baked into synthetic data, separate `at_risk` from `recoverability` (not one merged flag), pre-insert dataset validation, controlled `risk_reason` enum (not free-form strings), baseline evaluation report.

**Built:**
- `backend/generate_synthetic_data.py` — seeded (`--seed 42` default), ~1,000 events, ground truth baked in, validates before persisting, batched inserts (`psycopg2.extras.execute_values`)
- `backend/detect_at_risk.py` — deterministic rule-based detector, reads only observed fields (never ground truth)
- `backend/evaluate.py` — precision/recall/F1 against ground truth, false-positive check on the `succeeded` control group, writes `backend/reports/day2_baseline.txt`

**Real bugs found and fixed:**
1. Bulk insert of 1,000 rows timed out against Neon (`executemany` doing individual round-trips over Neon's latency). Fixed with `psycopg2.extras.execute_values` — single multi-row `INSERT ... VALUES`, ~4.2s for 1,000 rows.
2. Rule-priority bug: `EXHAUSTED_ATTEMPTS` (`previous_recovery_attempts >= 3`) was checked before `status == "succeeded"`, so a payment that succeeded after 3+ prior attempts was misclassified as `at_risk=True`. Caught via a metric discrepancy (`NOT_AT_RISK` count didn't match generator's `succeeded` count). Fixed by making the `succeeded` check short-circuit first.

**Original Day 2 baseline (superseded by Day 3's richer regeneration — kept here for history):**
```
Confusion Matrix: TP=472, FP=196, TN=332, FN=0
Precision: 0.7066, Recall: 1.0000, F1: 0.8281
```

---

## Day 3 (Phase 2) — AI Recovery Decision Layer

### The Reframe (from external review)

Original plan asked "can AI beat the F1 baseline?" — wrong question, for two reasons:
1. **Circularity risk**: ground truth and the detector both drew from the same small signal set, so an LLM could just re-derive the deterministic rules without demonstrating real judgment.
2. **Wrong success metric**: Track 03's actual promise is recovered ₹, not classification accuracy. From Day 3 onward, **simulated ₹ recovered is the north star, not F1**.

**Reframed goal:** run an honest experiment — does an AI with richer context make measurably better recovery decisions than the deterministic baseline, on a business outcome? If yes, integrate it. If no, say so honestly and keep the system simpler. Both are legitimate outcomes for the "AI judgment" criterion.

Work was structured into **two gates**:
```
Gate A (required, no AI) → Gate B (the AI experiment, only after Gate A is solid)
```

### Gate A — COMPLETE

**Step 0 — Verified Phase 0 transaction matching.** Confirmed `_find_transaction_for_payload()` matches on `razorpay_payment_link_id` / `razorpay_order_id`, does not rely on the unreliable `reference_id` field. No fix needed.

**Step 1 — Enriched synthetic data.** Added columns to `synthetic_events` via new Alembic migration: `customer_tenure_days`, `previous_failed_payments`, `average_order_value`, `time_since_last_successful_payment_hours`, `time_since_last_recovery_attempt_hours`, `checkout_duration_seconds`, `payment_method`. Populated with correlated (not independently randomized) values.

**Step 2 — `backend/GROUND_TRUTH_POLICY.md` written.** This is the single most important artifact from Day 3. ~900 lines, 20 sections. Key structure:
- Sections 1-12: qualitative business policy (at risk vs. recoverability vs. outcome; failure-reason-by-failure-reason recoverability expectations; safety boundaries)
- Section 13: simulation success definition (payment succeeds → recovered_amount = transaction amount, else 0)
- Section 14: intervention cost/penalty (requires a fixed value, defined before comparison)
- Section 15: benchmark distribution disclosure (~45-50% ground-truth recoverable, documented honestly, not hidden)
- Section 16: evaluation principles (₹ recovered is primary, not F1)
- Section 18: what this policy is intended to prove (AI must earn its place, not be assumed useful)
- Section 19: policy integrity (never tune the policy after seeing results)
- **Section 20 (numeric appendix, added after a second review pass)**: closes every "must be defined" gap left by Sections 1-19 with actual numbers:
  - 20.1: Recovery probability by tier — HIGH=0.85, MEDIUM=0.50, LOW=0.15, NONE=0.00
  - 20.2-20.5: concrete thresholds for "established," "recent," "prolonged," etc.
  - 20.6: exact order of operations for combining signals into a tier, then a boolean
  - **20.7**: explicit wiring — `simulated_intervention_succeeds := ground_truth_recoverable == True`, no re-randomization at simulation time
  - **20.8**: concrete penalty — **₹200 flat per bad intervention** (not percentage-based; models fixed ops overhead)

**Step 3 — Regenerated dataset against the full policy** (`generate_synthetic_data.py` updated). Caught and fixed a regression during this step: `previous_recovery_attempts` briefly stopped producing any values ≥3 (0 `EXHAUSTED_ATTEMPTS` events), traced to the correlated-field rewrite. Fixed, restored to a realistic ~5.4% at ≥3.

**Final Day 3 Gate A baseline numbers (current, authoritative):**
```
1,000 events, seed 42
ground_truth_recoverable: 438 True / 562 False

detect_at_risk.py risk reasons:
  NOT_AT_RISK: 338, TRANSIENT_FAILURE: 264, LOW_RECOVERY_PROBABILITY: 204,
  CHECKOUT_ABANDONMENT: 162, EXHAUSTED_ATTEMPTS: 32  (sums to 1000)

evaluate.py:
  Precision: 0.6616, Recall: 1.0000, F1: 0.7964
  False positives on succeeded control group: 0 (PASS)
  Total revenue: ₹9,824,112 | Revenue at risk: ₹6,538,889 (66.6%)
```

**Step 4 — Baseline outcome simulation (`backend/simulate_outcomes.py`), Gate A's actual deliverable:**
```
==================================================
  Day 3 Baseline Simulation Report — Deterministic Baseline
==================================================
Candidate decisions:     662  (all at_risk=True events)
Successful recoveries:   438
Total recovered:         ₹4,288,918

Bad interventions:       224
Penalty per intervention: ₹200
Total penalty cost:      ₹44,800

Net ₹ recovered:         ₹4,244,118
==================================================
```

**This ₹42.44L net figure is the number Gate B's AI-gated agent must beat.** The `simulate_outcomes.py` core logic is written generically (reusable function taking `(event, action_taken)` pairs) so it can be reused for the AI agent without rewriting.

### Gate B — IN PROGRESS

**Prompt B2 — `agent_decisions` table.** DONE. New Alembic migration, columns: `id`, `synthetic_event_id` (fk), `diagnosis`, `recovery_probability`, `recommended_action`, `reason`, `confidence`, `decision_path` (`ai_decision`/`gated_override`/`pre_filtered`), `override_reason`, `created_at`. Applied, confirmed (`alembic current` → `004 (head)`).

**Prompt B1 — `backend/llm_provider.py`.** DONE. Key design:
- `get_structured_decision(prompt, schema) -> dict`, calls OpenRouter's OpenAI-compatible endpoint
- Exception hierarchy: `LLMProviderError` (base), `LLMAPIError` (network/auth/timeout), `LLMJSONDecodeError` (invalid JSON), `LLMSchemaValidationError` (schema mismatch) — each fails loud and specific
- Reads `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` (default: `google/gemini-2.0-flash-001`) from env
- Standalone test (`if __name__ == "__main__"`) validates schema-checking logic offline even without a live API key — confirmed working before any spend

**Prompt B3 — `backend/run_agent.py`.** DONE, one bug found and fixed:
- Pre-filters: `previous_recovery_attempts >= 3` → `stop`; `amount_paise > <threshold>` → `escalate_to_merchant`
- **Bug found**: initial high-value threshold was ₹5,000 — but the at-risk population's *median* transaction is ₹9,895, so this pre-filtered 471/662 events (71%!) before they ever reached the AI, defeating the point of the experiment. Diagnosed via a direct percentile query (`min: ₹110, max: ₹19,965, median: ₹9,895, p90: ₹17,986`). **Fixed threshold to ₹18,000** (~p90) → now correctly pre-filters only 62/662 (9.4%).
- Post-filters: invalid action → `escalate_to_merchant`; confidence < 0.5 → `escalate_to_merchant`; any LLM exception caught → `escalate_to_merchant`, logged with `override_reason="llm_call_failed"`
- **Current confirmed-correct run summary (with OPENROUTER_API_KEY unset, so all LLM-reaching events correctly failed-safe):**
```
Total at-risk events: 662
Pre-filtered: 94 (14.2%) — high_value: 62 (9.4%), attempts_exhausted: 32 (4.8%)
Reached LLM: 568 (85.8%) — all currently gated_override/llm_call_failed since no API key is set yet
```

**BLOCKER — resolved via workaround, not yet executed:**
- OpenCode free quota exhausted (10h+ cooldown), Go subscription stuck on Alipay redirect → switched to Antigravity, no impact on code quality since prompts are agent-agnostic
- OpenRouter $5 credit purchase pending settlement (showed `-$0.16` balance, HDFC alert for $5.80 debit dated 29/08/2026) — **decision made: do NOT wait**, switch `OPENROUTER_MODEL` to a free-tier OpenRouter model (e.g. a `:free`-suffixed Llama model) to unblock today's work. Free-tier models typically don't draw from the pending paid balance. Plan is to complete the full experiment on the free model now, and **optionally re-run later on a paid model once the balance clears**, since the whole pipeline is a one-line env var swap — no code changes needed to switch models.

---

## Immediate Next Steps (Pick Up Here)

1. **Confirm a free OpenRouter model is available** (check OpenRouter's models page for current `:free` options), set `OPENROUTER_MODEL=<that model>` in `.env`
2. **Run `llm_provider.py`'s standalone test** to confirm `OPENROUTER_API_KEY set: True` and a real structured response comes back
3. **Add a `--limit N` CLI flag to `run_agent.py`** (not yet built — see prompt below) and do a small dry run (10-15 events) before spending on the full 568-event batch. Specifically check: does `agent_decisions.reason` genuinely reference the enriched context (tenure, checkout duration, payment method), or does it just restate `failure_reason`? This is the single most important quality check for the whole Day 3 experiment.
4. **If the dry run looks genuinely contextual**, run the full batch: `python3 run_agent.py`
5. **Prompt B4** — extend `simulate_outcomes.py` to run the same reusable simulation function against `agent_decisions` instead of `detection_results`, produce the final comparison table (see prompt below)
6. **Step 8, the decision point**: if AI's net ₹ meaningfully beats ₹42.44L *and* reasoning is genuinely contextual → integrate, move to Phase 3. If not → document honestly, keep the deterministic system as the core. Either outcome gets written to `backend/reports/day3_experiment_result.md`.
7. **Only after Gate B concludes**: Phase 3 (wire the winning decision system to real Razorpay actions), then dashboard (explicitly last).

---

## Ready-to-Use Prompts for Continuation

### Add `--limit` flag to `run_agent.py` (not yet sent)
```
Add an optional --limit N CLI argument to run_agent.py. When provided, only process the first N at-risk events (after pre-filtering is still applied to the full set, but only the first N post-pre-filter events actually reach the LLM) — this lets me do a cheap dry run before spending on the full batch. Default: no limit, process everything. Print a note at the top of the run indicating the limit is active if one was passed.
```

### Prompt B4 — extend simulation to the AI agent (not yet sent)
```
Extend backend/simulate_outcomes.py (reuse the existing reusable simulation function from the baseline run, don't duplicate logic) to also run against backend/agent_decisions instead of detection_results:

- recover_now / send_payment_link / wait_and_retry all count as "attempted recovery" for simulation purposes (apply the same GROUND_TRUTH_POLICY.md Section 20.7/20.8 rules: success = ground_truth_recoverable==True credits ground_truth_recovered_amount, failure = bad intervention, ₹200 flat penalty)
- escalate_to_merchant and stop count as "no automated action taken" — excluded from success/failure accounting entirely, same as at_risk=False events in the baseline

Print a final side-by-side comparison table:

| System | Candidate decisions | Successful recoveries | ₹ recovered | Bad interventions | Net ₹ |
|---|---|---|---|---|---|
| Deterministic baseline | 662 | 438 | ₹4,288,918 | 224 | ₹4,244,118 |
| AI recovery agent | ... | ... | ... | ... | ... |

Also print the decision_path breakdown (pre_filtered / gated_override / ai_decision counts, with gated_override broken down by override_reason) from agent_decisions.

Write the full output to backend/reports/day3_experiment_result.txt
```

---

## Open Threads / Notes for Later

- `webhook_verified` audit log entries are written with `transaction_id=None` by design (fire before transaction match) — won't show in filtered `/audit/{id}` results, expected behavior not a bug.
- Day 2's generator distribution is slightly `failed`-heavy (~48-49% vs. an intended ~45%) — cosmetic, not revisited.
- The Day 3-enriched `ground_truth_recoverable` distribution (43.8% True) is close to but not exactly the policy's stated 45-50% target — within reasonable tolerance, not adjusted (adjusting now would violate Section 19's policy-integrity rule since baseline results have already been observed).
- If/when re-running on a paid model later for the final submission, re-run the *entire* Gate B chain (run_agent.py → simulate_outcomes.py) fresh rather than mixing free-model and paid-model decisions in the same `agent_decisions` table — the table is cleared on each run, so this happens naturally, just don't forget to actually do it before finalizing numbers for the demo.
