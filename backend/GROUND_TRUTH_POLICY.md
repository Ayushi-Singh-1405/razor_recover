# RecoverAI — Ground Truth Policy

## Purpose

This document defines the business policy used to assign **synthetic ground-truth recovery outcomes** in RecoverAI.

The purpose of the policy is to create a reproducible and defensible benchmark for evaluating two recovery strategies:

1. The Phase 1 deterministic baseline, which operates on a limited set of observable transaction signals.
2. The Phase 2 AI recovery agent, which is allowed to reason over richer transaction, customer, temporal, and recovery-history context.

This policy is defined independently of both systems.

The baseline detector must not be modified to match this policy, and the AI agent must not be given access to the ground-truth fields themselves.

The ground truth represents the **synthetic business outcome** that would occur if the recovery intervention were attempted under the simulated conditions defined by this project.

---

# 1. Core Concepts

RecoverAI separates three concepts that must not be conflated:

### At Risk

A transaction is **at risk** when the original payment attempt did not successfully complete and there is potentially recoverable revenue associated with it.

This is the responsibility of the deterministic Phase 1 detector.

### Recoverability

Recoverability represents how worthwhile it is to pursue recovery for an at-risk transaction.

It is determined using richer contextual information:

- transaction context
- customer history
- temporal behavior
- recovery history

Recoverability is classified as:

- `HIGH`
- `MEDIUM`
- `LOW`
- `NONE`

### Recovery Outcome

The simulated outcome represents what happens when a recovery intervention is attempted.

A successful recovery results in the transaction amount being counted as recovered revenue.

An unsuccessful recovery results in zero recovered revenue.

---

# 2. Inputs to the Ground-Truth Policy

The policy may use the following information when determining the synthetic outcome.

## 2.1 Transaction Context

### `status`

The original payment state.

Expected values include:

- `succeeded`
- `failed`
- `abandoned_checkout`

A transaction whose original payment already succeeded is not considered recoverable.

### `failure_reason`

The reason the original payment did not complete.

Current failure categories include:

- `network_error`
- `otp_timeout`
- `insufficient_funds`
- `card_declined`

Different failure reasons imply different recovery potential.

### `amount_paise`

The transaction amount.

Amount contributes to the value at risk but does not independently determine recoverability.

A high-value transaction should not automatically be classified as more recoverable.

---

## 2.2 Customer History

### `customer_tenure_days`

Approximate age of the customer's relationship with the merchant.

Longer tenure is evidence of an established customer relationship.

Short or zero tenure represents a newer or first-time customer.

Tenure is a supporting signal, not a guarantee of recovery.

### `previous_successful_payments`

Number of previous successful payments.

A higher number indicates established payment behavior and stronger historical engagement.

### `previous_failed_payments`

Number of previous failed payments.

Repeated historical failures reduce confidence that another recovery attempt will succeed.

### `average_order_value`

Historical average transaction value for the customer.

This provides context for the current transaction amount.

A current transaction that is broadly consistent with the customer's historical behavior should generally carry more confidence than an unusually large deviation.

---

## 2.3 Temporal Behavior

### `time_since_last_successful_payment_hours`

Time since the customer's most recent successful payment.

A recent successful payment is evidence of recent customer engagement.

A long period without a successful payment weakens that signal.

### `checkout_duration_seconds`

Time between checkout initiation and the failed/abandoned event.

Checkout duration is treated as a behavioral signal rather than a direct indicator of intent.

Very short checkout failures may be consistent with a technical interruption.

Very long checkout durations can indicate hesitation or friction, particularly when combined with weak customer history.

Checkout duration must therefore be interpreted together with other signals.

---

## 2.4 Recovery History

### `previous_recovery_attempts`

Number of recovery attempts already made for the transaction.

Recovery attempts have a hard operational limit.

Transactions with exhausted recovery attempts are not eligible for further automated recovery.

### `time_since_last_recovery_attempt_hours`

Time since the most recent recovery attempt.

A recent failed recovery attempt reduces the desirability of immediately repeating the same intervention.

A sufficient cooldown period may make another attempt reasonable when other contextual signals are favorable.

---

# 3. Failure Reason Policy

Failure reason provides an initial indication of recovery potential.

## 3.1 `network_error`

Generally considered a **transient failure**.

Baseline expectation:

- HIGH recoverability when customer engagement is strong and recovery attempts are not exhausted.
- MEDIUM recoverability when customer/context signals are mixed.
- LOW recoverability when customer history is weak or repeated recovery attempts have failed.

A network error does not imply that the customer abandoned the purchase.

---

## 3.2 `otp_timeout`

Generally considered potentially recoverable.

An OTP timeout can represent temporary friction rather than lack of customer intent.

Baseline expectation:

- HIGH when customer history is strong and checkout behavior does not indicate substantial hesitation.
- MEDIUM when contextual signals are mixed.
- LOW when repeated failures or weak engagement are present.

---

## 3.3 `insufficient_funds`

Generally has lower recovery confidence than transient technical failures.

The customer may still complete the transaction later, but an immediate recovery attempt should not automatically be considered high probability.

Baseline expectation:

- HIGH only when strong contextual evidence supports recovery.
- MEDIUM for ambiguous cases.
- LOW/NONE when customer history contains repeated failures or other negative signals.

The synthetic benchmark intentionally contains uncertainty in this category.

---

## 3.4 `card_declined`

Generally has lower immediate recovery confidence.

A card decline may be temporary, method-specific, or indicative of a condition that will not be resolved by simply repeating the same action.

Baseline expectation:

- MEDIUM in favorable contextual situations.
- LOW when the customer has repeated failures or weak engagement.
- NONE when recovery attempts are exhausted or the failure context provides no reasonable basis for another attempt.

The benchmark intentionally contains uncertain cases in this category.

---

## 3.5 `abandoned_checkout`

An abandoned checkout indicates that the customer entered the checkout process but did not complete payment.

Recoverability depends strongly on contextual evidence.

A customer with:

- established payment history,
- recent successful activity,
- reasonable checkout duration,
- and no previous recovery attempts

may have meaningful recovery potential.

A first-time customer with weak engagement and prolonged checkout hesitation should receive lower recoverability.

---

## 3.6 `succeeded`

A successful transaction is:

```text
recoverability = NONE
ground_truth_recoverable = false
ground_truth_recovered_amount = 0
```

A successful payment must never be treated as revenue requiring recovery.

This also serves as the control group for evaluating false-positive detection.

---

# 4. Customer Engagement Signals

Customer history modifies the initial failure-reason assessment.

## Strong engagement

Evidence of strong engagement includes combinations such as:

- multiple previous successful payments
- recent successful payment activity
- established customer tenure
- few previous failed payments
- transaction amount broadly consistent with historical order value

Strong engagement increases recoverability.

It does not override hard stopping conditions.

---

## Mixed engagement

Mixed engagement occurs when positive and negative signals are present.

Examples:

- several successful payments but several recent failures
- established customer but unusually large transaction
- recent success but repeated recovery attempts
- favorable history but prolonged checkout hesitation

Mixed cases should generally fall into `MEDIUM` recoverability unless another policy condition clearly lowers the outcome.

---

## Weak engagement

Evidence of weak engagement includes combinations such as:

- first-time or very new customer
- few or no previous successful payments
- repeated previous failures
- long period since the last successful payment
- unusually long checkout hesitation
- repeated failed recovery attempts

Weak engagement lowers recoverability.

---

# 5. Temporal Behavior Policy

Temporal signals modify, rather than independently determine, recovery potential.

### Recent successful activity

A recent successful payment is positive evidence that the customer is currently active and capable of completing payments.

This increases confidence in recovery when other signals are favorable.

### Long inactivity

A long period without a successful payment decreases confidence.

### Checkout duration

Checkout duration should be interpreted alongside failure reason.

For example:

```text
network_error + short/normal checkout
```

is more consistent with a technical interruption than:

```text
network_error + very long checkout + weak customer history
```

The latter should receive lower recovery confidence.

No single checkout-duration threshold should independently determine recoverability.

---

# 6. Recovery Attempt Policy

Recovery attempts are subject to a hard limit.

## Exhausted attempts

If:

```text
previous_recovery_attempts >= 3
```

then:

```text
ground_truth_recoverable = false
recoverability = NONE
```

No additional automated recovery should be considered successful under the benchmark.

This condition takes precedence over positive customer-history signals.

---

## Previous attempts with remaining capacity

When fewer than three attempts have occurred:

- previous failed attempts reduce confidence,
- the time since the previous attempt affects whether another attempt is reasonable,
- strong customer/context signals may still justify another recovery attempt.

A recent failed attempt should generally produce lower recoverability than an otherwise identical transaction with no recent recovery attempt.

---

# 7. Recoverability Tiers

The policy produces one of four tiers.

## HIGH

A transaction is `HIGH` recoverability when there is strong contextual evidence that the customer is likely to complete payment if an appropriate recovery intervention is attempted.

Typical characteristics:

- transient or plausibly recoverable failure
- strong historical engagement
- recent customer activity
- few previous failures
- no exhausted recovery attempts
- no strong evidence of checkout hesitation
- reasonable transaction amount relative to historical behavior

HIGH does not guarantee successful recovery.

It represents the strongest synthetic probability class.

---

## MEDIUM

A transaction is `MEDIUM` recoverability when recovery is plausible but the available evidence is mixed.

Typical characteristics:

- some positive customer history
- some negative signals
- ambiguous failure reason
- moderate checkout hesitation
- unusual but not extreme transaction amount
- limited previous recovery history

MEDIUM cases are intentionally important for evaluating contextual AI judgment.

---

## LOW

A transaction is `LOW` recoverability when recovery is possible but unlikely to justify aggressive intervention.

Typical characteristics:

- weak customer engagement
- repeated previous failures
- prolonged checkout hesitation
- long inactivity
- recent unsuccessful recovery attempt
- ambiguous failure reason with insufficient positive evidence

LOW cases may still occasionally recover in the synthetic simulation.

This uncertainty is intentional.

---

## NONE

A transaction is `NONE` recoverability when recovery should not be pursued.

Examples include:

- original payment already succeeded
- recovery attempts exhausted
- clearly non-recoverable synthetic outcome
- conditions where another automated attempt is explicitly disallowed

`NONE` maps to:

```text
ground_truth_recoverable = false
ground_truth_recovered_amount = 0
```

---

# 8. Ground-Truth Outcome Generation

The recoverability tier is used to generate the synthetic recovery outcome.

The outcome must be generated **before evaluating either the baseline detector or the AI agent**.

The outcome must not depend on:

- baseline detector output
- AI decision
- AI confidence
- AI reasoning
- evaluation results

This prevents the benchmark from being tuned to favor either system.

The synthetic outcome should contain:

```text
ground_truth_recoverable
ground_truth_outcome
ground_truth_recovered_amount
```

For a successful simulated recovery:

```text
ground_truth_outcome = "recovered"
ground_truth_recovered_amount = amount_paise
```

For an unsuccessful recovery:

```text
ground_truth_outcome = "not_recovered"
ground_truth_recovered_amount = 0
```

---

# 9. Recovery Probability Model

The benchmark should preserve uncertainty.

Recoverability is not equivalent to certainty.

The intended interpretation is:

```text
HIGH   → strong probability of recovery
MEDIUM → meaningful but uncertain probability
LOW    → low probability of recovery
NONE   → no recovery should be pursued
```

The exact outcome probabilities must be defined before comparing the baseline and AI systems.

They must remain fixed across both evaluations.

The probability rules must not be changed after observing which system performs better.

---

# 10. Baseline Detector Boundary

The Phase 1 deterministic detector intentionally remains unchanged.

It uses its existing observable signals:

- `status`
- `failure_reason`
- `amount`
- `previous_successful_payments`
- `previous_recovery_attempts`

The baseline does **not** gain access to the enriched contextual fields introduced for Phase 2.

This is not intended as an artificial handicap.

It represents the difference between:

> a simple deterministic production rule set

and:

> a recovery system capable of reasoning over richer customer and temporal context.

The baseline remains the control system against which the AI recovery layer is evaluated.

---

# 11. AI Agent Boundary

The AI recovery agent may use the enriched contextual fields available at decision time.

These include:

- customer tenure
- previous successful payments
- previous failed payments
- average order value
- time since last successful payment
- previous recovery attempts
- time since last recovery attempt
- checkout duration
- payment method
- original transaction/failure context

The AI must **not** receive:

- `ground_truth_recoverable`
- `ground_truth_outcome`
- `ground_truth_recovered_amount`
- any post-intervention outcome
- any evaluation metric

The AI therefore has to make its decision using information that would realistically be available before recovery.

---

# 12. Deterministic Safety Overrides

Ground truth describes the synthetic business outcome.

It does not override operational safety rules.

Regardless of AI reasoning:

```text
previous_recovery_attempts >= 3
        → STOP
```

and transactions that are not at risk do not enter the recovery agent.

The deterministic policy gate remains responsible for enforcing hard operational constraints.

This means the AI can recommend an action, but it cannot bypass:

- attempt limits
- amount limits
- confidence requirements
- allowed action types
- escalation requirements

---

# 13. Simulation Success Definition

A recovery intervention is considered successful when the simulated payment succeeds.

The accounting rule is:

```text
intervention
     ↓
simulated outcome
     ↓
payment succeeds?
     ├── YES → recovered_amount = transaction amount
     └── NO  → recovered_amount = 0
```

Recovered revenue must be counted identically for both the deterministic baseline and the AI system.

The simulation engine must use the same outcome rules for both systems.

---

# 14. Intervention Cost / Penalty

An unnecessary recovery intervention is not treated as free.

For the benchmark, an intervention that is attempted against a transaction whose synthetic outcome is not recoverable is considered a **bad intervention**.

At minimum, the evaluation must count:

```text
bad_interventions
```

A bad intervention represents wasted recovery effort and potential customer friction.

If a numerical penalty is introduced, the value must be defined before running the baseline-vs-AI comparison and must remain fixed for both systems.

No penalty value may be tuned after observing the results.

---

# 15. Benchmark Distribution

The synthetic dataset is intentionally recovery-heavy.

Approximately:

```text
45–50%
```

of generated events are expected to be ground-truth recoverable.

This provides enough positive cases to evaluate recovery behavior during development.

The distribution is fixed by the dataset seed and is **not tuned against model performance**.

The Phase 1 baseline produced approximately:

```text
1,000 events
472 ground-truth recoverable events
```

and approximately:

```text
₹10.05M total transaction value
₹6.72M revenue identified as at risk
```

The high at-risk proportion is therefore documented rather than hidden.

These figures describe the development benchmark and should not be presented as representative of Razorpay's real-world transaction distribution.

---

# 16. Evaluation Principles

The benchmark is designed to answer a business question:

> **Does richer contextual reasoning lead to better recovery decisions and more recovered revenue?**

Classification metrics remain useful for understanding the detector, but they are not the primary success criterion for Phase 2.

The primary comparison is:

| Metric | Deterministic Baseline | AI Recovery Agent |
|---|---:|---:|
| Candidate decisions | | |
| Successful recoveries | | |
| ₹ recovered | | |
| Bad interventions | | |

Additional evaluation should include:

- AI decisions
- gated overrides
- pre-filtered events
- escalation count
- stopping-rule compliance
- action distribution

The AI should not be considered successful merely because it improves F1.

The AI earns its place only if it demonstrates a meaningful improvement in recovery outcomes while respecting the deterministic safety boundaries.

---

# 17. Reproducibility Rules

The ground-truth benchmark must be reproducible.

The following must remain fixed for a given evaluation run:

- dataset seed
- synthetic-data generation logic
- ground-truth policy
- outcome probability rules
- simulation rules
- intervention penalty
- evaluation methodology

If any of these change, the benchmark version should be changed and the reason documented.

Results from different benchmark definitions must not be presented as a direct improvement.

---

# 18. What This Policy Is Intended to Prove

The goal of this benchmark is **not** to prove that an LLM is inherently better than deterministic rules.

The goal is to test whether AI is useful for the specific part of the revenue-recovery problem where contextual judgment is difficult to encode cleanly as fixed rules.

The intended experiment is:

```text
                 Same synthetic events
                         │
              ┌──────────┴──────────┐
              │                     │
              ▼                     ▼
       Deterministic            AI Agent
         Baseline             Rich Context
              │                     │
              ▼                     ▼
          Decision              Decision
              │                     │
              └──────────┬──────────┘
                         ↓
                Same simulation
                         ↓
                 Same ground truth
                         ↓
              Business outcomes
                         ↓
             ₹ recovered comparison
```

If the AI materially improves recovery outcomes:

> AI has demonstrated a useful role in RecoverAI.

If the AI does not materially improve outcomes:

> The deterministic strategy remains the preferred strategy under this benchmark, and the AI should be narrowed or removed rather than being included merely for appearance.

Both are valid experimental outcomes.

---

# 19. Policy Integrity

This document must be treated as a **pre-evaluation specification**.

After baseline or AI results are observed, the policy must not be modified simply to improve either system's performance.

If a policy flaw, unrealistic assumption, or data-generation error is discovered:

1. document the issue,
2. record the reason for the change,
3. version the policy,
4. regenerate the affected benchmark,
5. rerun both systems under the same new policy.

This preserves the credibility of the evaluation.

---

## Final Principle

RecoverAI should not claim:

> "AI works because the LLM produced a higher score."

It should be able to demonstrate:

> **"We defined the business outcome independently, established a deterministic baseline, gave the AI additional contextual information that is available before intervention, evaluated both systems under identical recovery conditions, and measured whether the AI actually recovered more revenue without violating our safety constraints."**

That is the standard this ground-truth policy is designed to support.

---

# 20. Numeric Reference Values (Appendix)

The qualitative bands in Sections 3–9 describe the *reasoning* behind the policy. This appendix pins down the *numbers* — without them, the generator implementation would have to invent its own thresholds and probabilities, which would silently make those numbers the real policy instead of this document.

These values are authoritative for implementation. If the generator code and this appendix ever disagree, this appendix wins, and the disagreement must be logged as a policy version change per Section 19. These numbers must not be changed after observing baseline or AI results, per Section 19's policy integrity rule.

## 20.1 Recovery Probability by Tier

The recoverability tier determines the probability that `ground_truth_recoverable = true` for a given event (Section 9 requires this be fixed before evaluation):

```text
HIGH   → 0.85
MEDIUM → 0.50
LOW    → 0.15
NONE   → 0.00
```

`ground_truth_recoverable` is assigned via a seeded random draw against these probabilities — not a hard cutoff — so that, per Section 7, "HIGH does not guarantee successful recovery" and "LOW cases may still occasionally recover" hold true in the generated data.

## 20.2 Customer Engagement Thresholds

```text
"Established" customer tenure          → customer_tenure_days >= 180
"New / first-time" customer            → customer_tenure_days < 30
"Strong" previous_successful_payments  → >= 5
"Weak" previous_successful_payments    → <= 1
"Repeated" previous_failed_payments    → >= 3
```

## 20.3 Temporal Thresholds

```text
"Recent" successful payment            → time_since_last_successful_payment_hours < 72
"Long inactivity"                      → time_since_last_successful_payment_hours > 720  (30 days)
"Recent" failed recovery attempt       → time_since_last_recovery_attempt_hours < 24
"Sufficient cooldown"                  → time_since_last_recovery_attempt_hours >= 24
```

## 20.4 Checkout Duration Bands

Per Section 5, checkout duration is interpreted alongside failure reason and customer history — not as a standalone cutoff. These bands are inputs to that combined judgment, not independent rules:

```text
"Short / normal" checkout    → checkout_duration_seconds < 120
"Prolonged / hesitant"       → checkout_duration_seconds > 300
(120–300s is the ambiguous middle band, weighted by other signals)
```

## 20.5 Amount Consistency

```text
"Broadly consistent" with average_order_value  → within ±40% of average_order_value
"Unusual deviation"                            → beyond ±40% of average_order_value
```

## 20.6 How These Combine

For a given event, the generator should:
1. Start from the failure-reason baseline tier (Section 3)
2. Adjust up/down based on how many engagement signals (20.2), temporal signals (20.3), and amount consistency (20.5) fall in the favorable vs. unfavorable band — "mixed engagement" (Section 4) is the expected outcome when signals split roughly evenly
3. Apply hard overrides last: `previous_recovery_attempts >= 3` → forces `NONE` (Section 6) regardless of any other signal; `status == "succeeded"` → forces `NONE` (Section 3.6) regardless of any other signal
4. Convert the final tier to a `ground_truth_recoverable` boolean via the Section 20.1 probability draw
5. Set `ground_truth_recovered_amount = amount_paise` if recoverable, else `0`, per Section 8
