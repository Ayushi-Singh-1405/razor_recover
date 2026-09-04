# Day 3 Plan — RecoverAI (Phase 2: AI Recovery Decision Layer)
### v2 — revised after review: Phase 2 is an experiment, not "add an LLM"

## Where You're Starting From

Phase 0 (real Razorpay plumbing) and Phase 1 (synthetic dataset + deterministic detector) are done. Baseline: **Precision 0.71, Recall 1.00, F1 0.83** — but per the review, this number proves the pipeline is well-built, not that AI belongs in it yet. See `CHAT_SUMMARY.md` for full history.

## The Reframe

Yesterday's plan asked "can AI beat the F1 baseline?" That's the wrong question, for two reasons the review identified:

1. **Circularity risk.** You generated both the synthetic events *and* their ground truth from the same small signal set (`status`, `failure_reason`, `previous_recovery_attempts`, `amount`). An LLM fed those same fields could just re-derive the rules you already encoded deterministically — producing a nicer F1 without demonstrating actual judgment. A judge could reasonably ask "why do you need an LLM for this?" and right now you couldn't answer convincingly.

2. **Wrong success metric.** Track 03's actual promise is recovered ₹, not classification accuracy. A system with F1=0.84 that recovers ₹1.2L is a better hackathon submission than one with F1=0.94 that recovers ₹20K. From today onward, **₹ recovered (simulated) is the north star**, not F1.

**Today's real goal:** run an honest experiment — does an AI with richer context make measurably better recovery decisions than the deterministic baseline, on a business outcome, not a classification score? If yes, integrate it properly. If no, say so and keep the system simpler. Either outcome is a legitimate, defensible result for the "AI judgment" criterion.

---

## Explicitly Out of Scope Today

-  Dashboard / frontend — **do not touch this today, even briefly.** Per the review, this is the easiest way to burn a day polishing the wrong layer.
-  Wiring decisions back into real Razorpay actions (that's Phase 3, and only after today's experiment shows AI is worth wiring in)
-  Customer messaging / notifications
-  LangGraph or heavy agent frameworks

**Revised priority order for the rest of the week** (per the review):
```
AI decision quality → recovery simulation/evaluation → policy + stopping →
real Razorpay execution → failure scenarios → metrics → dashboard polish (last)
```

---

## Step 1 — Enrich the Synthetic Data (Before Any AI Code)

The current schema is too thin for AI reasoning to be non-trivial. Extend `synthetic_events` with temporal/contextual fields — not 30 random columns, but the ones that would actually change a human's recovery decision:

- `customer_tenure_days`
- `previous_successful_payments` (already exists)
- `previous_failed_payments` (new — distinct from recovery *attempts*)
- `average_order_value`
- `time_since_last_successful_payment_hours`
- `previous_recovery_attempts` (already exists)
- `time_since_last_recovery_attempt_hours`
- `checkout_duration_seconds` (how long between checkout start and failure — proxy for hesitation vs. technical failure)
- `payment_method` (card, upi, netbanking — recovery approach differs by method)

- Add these columns via a new Alembic migration to `synthetic_events` (additive, don't break Phase 1's existing rows — you'll regenerate the dataset anyway, but keep the migration clean)
- Update `generate_synthetic_data.py` to populate these with **correlated, realistic** values — e.g. a customer with 12 successful payments and a network-error failure should look different from a customer with 4 recent failures and 2 exhausted recovery attempts. Don't randomize independently; the whole point is that context should be informative.

## Step 2 — Write Down the Ground-Truth Policy Explicitly (Kill the Circularity Risk)

Important nuance from review round 2: don't make the ground truth *artificially inaccessible* to the baseline just to engineer an AI win. Instead — define ground truth as a rich, defensible business policy first, on its own terms. Separately, and deliberately, scope the baseline detector down to the smaller signal set it would realistically use in production (which it already does — `status`/`failure_reason`/`amount`/`previous_recovery_attempts`). The gap between the two isn't a rigged handicap; it's the honest difference between a simple rules engine and a system with more context available to it.

```
GROUND TRUTH POLICY
        │
        ├── transaction context
        ├── customer history
        ├── temporal behavior
        ├── recovery history
        └── outcome assumptions
                 │
                 ↓
        Actual synthetic outcome

Baseline detector  → sees limited observable signals (unchanged from Phase 1)
AI agent           → sees richer permitted context (Step 1's new fields)
```

The question this sets up: *does access to contextual reasoning let the AI make better recovery decisions* — not *can an LLM reproduce my ground-truth rules*.

- Create `backend/GROUND_TRUTH_POLICY.md` — plain-language rules like: *"A transient failure (network_error, otp_timeout) on a customer with 3+ prior successful payments and no exhausted attempts is recoverable with high probability. A transient failure on a first-time customer with a long checkout hesitation is recoverable with only moderate probability, reflecting real-world uncertainty about intent."* Write these as if defending them to a skeptical reviewer, because that's effectively what's happening. Base this on the full enriched signal set from Step 1, written independently of what any detector or AI will later be given — this is the policy, not a description of either system.
- Add a short note in the same file: *"This is an intentionally recovery-heavy benchmark (~45-50% of events ground-truth recoverable) to ensure sufficient positive cases during development. The distribution is fixed by seed and not tuned against model performance."* — document the 66.9%-at-risk number honestly instead of hiding it, per the review.

## Step 3 — Define a Real Decision Space for the AI

Per the review, the action set needs to be genuinely non-trivial, not a relabeled version of the detector's `risk_reason`.

- Actions: `recover_now` (immediate payment link), `send_payment_link` (lower urgency), `wait_and_retry` (transient issue, retry later without contacting customer), `escalate_to_merchant`, `stop` (not worth pursuing)
- The AI's prompt must include the enriched context from Step 1 — tenure, failure history, checkout duration, payment method — not just the fields the deterministic detector already used. If the AI can't distinguish two events using only detector-visible fields, that's fine — the point is it has strictly more to reason about now.

## Step 4 — LLM Provider Setup

Same as before, unchanged:
- OpenRouter account, buy $5 credit, **turn off auto-recharge**, set a **hard per-key spending limit**
- `backend/llm_provider.py` — provider-agnostic wrapper, structured output, tested standalone before wiring into anything

## Step 5 — Deterministic Policy Gate (Unchanged Structure, Same as Before)

Per the review's refined model:
```
Event → Deterministic Risk Detector → candidates → AI Recovery Decision Maker →
proposed action → Deterministic Policy Gate → approved? → Razorpay / escalation
```

- Pre-filters before the LLM: high `amount_paise` → auto-escalate, skip AI; `previous_recovery_attempts >= 3` → `stop`, skip AI; `at_risk == False` → never reaches agent
- Post-filters after the LLM: action must be in the allowed enum; low confidence → downgrade to `escalate_to_merchant`; hard cap on attempts per transaction
- Log every decision's path (`ai_decision`, `gated_override`, `pre_filtered`)

## Step 6 — Define "What Counts as a Successful Recovery" Before Simulating Anything

Do this explicitly, in writing, before any simulation code exists — otherwise "₹ recovered" becomes just another number that's easy to quietly manipulate.

```
attempt intervention
        ↓
simulated outcome
        ↓
payment succeeds?
        ↓
YES → recovered_amount = transaction amount
NO  → recovered_amount = 0
```

- Add a short section to `GROUND_TRUTH_POLICY.md` (or a new `backend/SIMULATION_RULES.md`) defining: what makes a simulated intervention count as successful; what `recovered_amount` is credited when it does; and — if you're modeling it — the **cost/penalty of an unnecessary intervention** (e.g. a `recover_now` action on an event that was never actually recoverable isn't free — it's a wasted attempt, possibly an annoyed customer). Even a simple flat penalty per bad intervention is enough; the point is that it's decided upfront, not tuned after seeing which system looks better.

## Step 7 — Simulated Outcome Evaluation, in Two Gates

Structure today's remaining work into two gates so a time crunch doesn't sacrifice the wrong part. **If you're running late, protect Gate A — a clean experimental foundation with no AI is more valuable than a rushed, unverified agent.**

**Gate A — required, do this first:**
1. Enriched synthetic data (Step 1)
2. `GROUND_TRUTH_POLICY.md` (Step 2)
3. Regenerate + validate the dataset against the new schema
4. Establish the **baseline outcome simulation** — run the existing deterministic detector's implicit action (act on everything flagged `at_risk`) through the Step 6 simulation rules, and answer: *what would happen if we used only the deterministic detector?* Get a real ₹ number here before writing any agent code.

**Gate B — the AI experiment, only after Gate A is solid:**
5. Define the AI decision schema (Step 3 below, if not already done)
6. Run the AI-gated agent through the same Step 6 simulation rules
7. Compare ₹ recovered between the two systems
8. Decide whether AI actually earns its place

- Write `backend/simulate_outcomes.py`, used identically for both the baseline and the AI-gated agent — same simulation rules, same penalty logic, so the comparison is apples-to-apples
- Produce a comparison table, not just a single number:

| System | Candidate decisions | Successful recoveries | ₹ recovered | Bad interventions |
|---|---|---|---|---|
| Deterministic baseline | | | | |
| AI recovery agent | | | | |

- Report the `ai_decision` vs `gated_override` vs `pre_filtered` breakdown — this is your "right tool in the right place, and where you chose not to use one" evidence

## Step 8 — The Actual Decision Point

- If the AI-gated agent's simulated ₹ recovered meaningfully beats the baseline **and** the reasoning in its `agent_decisions.reason` field looks genuinely contextual (references tenure, checkout duration, payment method — not just restating `failure_reason`) → integrate it, move to Phase 3 with confidence
- If it doesn't clearly beat the baseline, or the reasoning is just re-deriving the same detector-visible signals → **say so honestly.** Document why, keep the deterministic system as the core, and position the AI's role more narrowly (e.g. only for the genuinely ambiguous `LOW_RECOVERY_PROBABILITY` tier, where the deterministic system already admits uncertainty) rather than forcing it everywhere
- Either outcome gets written up plainly in `backend/reports/day3_experiment_result.md` — this write-up itself, showing you tested rather than assumed, is strong material for the demo regardless of which way it goes

---

## Definition of Done — Today

**Gate A (non-negotiable, protect this if time is short):**
- `synthetic_events` enriched with correlated temporal/contextual fields, regenerated (new seed run, re-validated)
- `GROUND_TRUTH_POLICY.md` written — ground truth is a defensible business policy on its own terms, not reverse-engineered to make either system look good
- "What counts as a successful recovery" + intervention penalty defined in writing, before any simulation code
- Distribution/realism choices documented honestly, not hidden
- Baseline outcome simulation run — a real ₹-recovered number for "just the deterministic detector," established before any agent code exists

**Gate B (the experiment, only after Gate A is solid):**
- AI decision space includes at least 5 meaningfully different actions
- Policy gate implemented with logged decision paths
- AI-gated agent run through the same simulation rules as the baseline
- Comparison table (candidate decisions, successful recoveries, ₹ recovered, bad interventions) for both systems
- An honest, written verdict on whether the AI demonstrably helps — with the reasoning shown, not just the score. "AI did not outperform the deterministic strategy under these conditions, so we retained the simpler strategy" is a legitimate, strong conclusion, not a failure.

**Target end-of-day milestone:** *"I ran a real experiment: does an AI with richer context make better recovery decisions than the deterministic baseline, measured in simulated ₹ recovered? Here's the answer, and here's why I believe it."* That sentence, delivered honestly either way, is worth more to the judges than a manufactured F1 improvement.
