# RecoverAI — LLM Provider, Testing & Evaluation Discussion

**Project:** `razor_recover`  
**Date:** August 29–30, 2026  
**Purpose of this document:** Consolidated record of the discussion about LLM access, Puter/OpenRouter/AgentRouter issues, model testing, decision quality, and the plan to process 1,000+ synthetic payment events.

---

## 1. Project Context

RecoverAI is an AI-based payment failure and checkout recovery system.

The core pipeline is:

```text
Synthetic payment events
        ↓
Baseline deterministic detector
        ↓
At-risk events
        ↓
Pre-filter policy gates
        ↓
Recovery Decision Agent
        ↓
LLM structured decision
        ↓
Post-filter safety gates
        ↓
agent_decisions
        ↓
Ground-truth evaluation
```

The important architectural principle is that the **LLM is responsible for reasoning**, while deterministic policy gates remain responsible for safety and bounded actions.

The project also deliberately separates:

- **Baseline detector:** limited observable signals
- **Recovery agent:** richer permitted customer/transaction context
- **Ground truth:** generated independently using a wider synthetic context
- **Agent decisions:** what the LLM actually recommends

This was designed to avoid circular evaluation.

---

# 2. Original LLM Provider Setup

The existing `backend/llm_provider.py` initially used a provider chain:

```text
1. AgentRouter  → PRIMARY
2. OpenRouter   → FALLBACK
```

Later, Puter was added as another provider:

```text
1. Puter
2. AgentRouter
3. OpenRouter
```

The provider module:

- Sends OpenAI-compatible chat completion requests.
- Embeds the JSON schema into the system instruction.
- Requests JSON-object output.
- Parses the response.
- Validates it locally against the schema.
- Returns the first valid structured decision.
- Falls back to the next provider if a provider fails.

The decision schema contains:

```text
diagnosis
recovery_probability
recommended_action
reason
confidence
```

Allowed actions:

```text
recover_now
send_payment_link
wait_and_retry
escalate_to_merchant
stop
```

---

# 3. Puter Attempt

We investigated using Puter as a free DeepSeek API based on:

`https://developer.puter.com/tutorials/free-unlimited-deepseek-api/`

The expectation was that Puter could provide a free alternative to paid APIs.

The actual response was:

```text
HTTP 402
subscription_required
subscription: user_free
```

Meaning:

- The Puter token authenticated.
- The free Puter account was recognized.
- The particular OpenAI-compatible endpoint/action required a subscription.
- This was not a bug in RecoverAI's provider code.

Therefore Puter was not useful for the current backend setup.

---

# 4. AgentRouter Problem

AgentRouter was also tested.

Response:

```text
HTTP 401
Invalid API Key
```

The key in `.env` continued to be rejected.

Therefore AgentRouter was also not usable for the current run.

---

# 5. OpenRouter Problem

OpenRouter initially hit:

```text
HTTP 429
free-models-per-day
```

The API response indicated that the free-model daily limit had been exhausted.

OpenRouter suggested adding credits to unlock a larger free-model request allowance.

This led to frustration because multiple apparently free options had practical limits.

We also discussed the fact that a student hackathon should ideally not require paying for a stronger model merely to make the project work.

---

# 6. OpenRouter `openrouter/free`

The OpenRouter configuration was changed to:

```env
OPENROUTER_MODEL=openrouter/free
```

This is OpenRouter's free-model router.

It successfully produced structured decisions for some requests.

A test run showed:

```text
Puter       → 402
AgentRouter → 401
OpenRouter  → SUCCESS
```

So the actual RecoverAI LLM pipeline was proven to work using OpenRouter's free routing.

---

# 7. `.env` / Python Import Issue

A test script initially failed with:

```text
ModuleNotFoundError: No module named 'config'
```

Reason:

`config.py` is located inside `backend/`.

Running Python from:

```text
~/razor_recover
```

did not expose `config` as a top-level module.

Running from:

```text
~/razor_recover/backend
```

fixed the issue.

---

# 8. Database Schema Confirmed

The database was inspected.

## `synthetic_events`

Important columns:

```text
id
amount_paise
status
failure_reason
customer_ref
previous_successful_payments
previous_recovery_attempts
created_at
raw_payload
ground_truth_recoverable
ground_truth_outcome
ground_truth_recovered_amount
customer_tenure_days
previous_failed_payments
average_order_value
time_since_last_successful_payment_hours
time_since_last_recovery_attempt_hours
checkout_duration_seconds
payment_method
```

## `agent_decisions`

```text
id
synthetic_event_id
diagnosis
recovery_probability
recommended_action
reason
confidence
decision_path
override_reason
created_at
```

This separation is important because the ground truth is stored on `synthetic_events`, while the agent's output is stored independently in `agent_decisions`.

The LLM does not receive the ground-truth fields.

---

# 9. First 5-Event OpenRouter Test

A 5-event test was run.

Summary:

```text
Total at-risk events: 5

Pre-filtered: 0
Reached LLM: 5

Pure AI decisions: 4
Gated overrides: 1
  - llm_call_failed: 1
```

Final actions:

```text
stop                 2
escalate_to_merchant 1
send_payment_link    1
recover_now          1
```

The provider chain worked as designed:

```text
Puter → failed
AgentRouter → failed
OpenRouter → succeeded on several requests
```

One event eventually failed all providers and safely became a gated escalation.

---

# 10. First 5 OpenRouter Decisions

### Event 1

```text
Amount: ₹2,564.31
Failure: network_error
Ground truth: recoverable=True
Outcome: recovered
AI: escalate_to_merchant
Path: gated_override
```

This was **not a model-quality failure** because the LLM call itself failed.

The safety system escalated instead.

---

### Event 2

```text
Amount: ₹7,221.62
Failure: network_error
Ground truth: recoverable=True
Outcome: recovered
AI: send_payment_link
Probability: 0.65
Confidence: 0.65
```

Reasonable recovery decision.

---

### Event 3

```text
Amount: ₹15,575.48
Failure: customer_abandoned
Ground truth: recoverable=True
Outcome: recovered
AI: stop
Probability: 0.15
Confidence: 0.82
```

This was the most concerning decision.

The transaction was actually recovered, but the model decided to stop.

---

### Event 4

```text
Amount: ₹4,096.72
Failure: customer_abandoned
Ground truth: recoverable=False
Outcome: not_recovered
AI: stop
Probability: 0.15
Confidence: 0.82
```

Correct conservative decision.

---

### Event 5

```text
Amount: ₹10,998.20
Failure: otp_timeout
Ground truth: recoverable=True
Outcome: recovered
AI: recover_now
Probability: 0.62
Confidence: 0.68
```

Good decision.

---

# 11. NVIDIA Model Comparison

Earlier, the same 5 events had been processed using an NVIDIA model.

The NVIDIA model produced:

### Event 1

```text
network_error
GT: recoverable
AI: recover_now
Probability: 0.72
Confidence: 0.81
```

### Event 2

```text
network_error
GT: recoverable
AI: recover_now
Probability: 0.62
Confidence: 0.71
```

### Event 3

```text
customer_abandoned
GT: recoverable
AI: send_payment_link
Probability: 0.38
Confidence: 0.71
```

### Event 4

```text
customer_abandoned
GT: not recoverable
AI: stop
Probability: 0.12
Confidence: 0.78
```

### Event 5

```text
otp_timeout
GT: recoverable
AI: recover_now
Probability: 0.62
Confidence: 0.71
```

NVIDIA therefore looked very strong on this tiny sample.

Most importantly, on Event 3:

```text
₹15,575 recoverable

NVIDIA → send_payment_link
OpenRouter → stop
```

That represented a potentially meaningful missed recovery opportunity.

However, 5 events are far too few to claim one model is definitively better.

---

# 12. Important Evaluation Distinction

A key conclusion was reached:

**Do not treat ground-truth recoverability as exactly equivalent to the optimal action.**

Ground truth tells us:

```text
recoverable=True/False
outcome=recovered/not_recovered
ground_truth_recovered_amount
```

The AI chooses among:

```text
recover_now
send_payment_link
wait_and_retry
escalate_to_merchant
stop
```

Therefore:

```text
GT recoverable=True
```

does not automatically mean every possible recovery action would be equally good.

The proper evaluation should eventually distinguish:

- correct recovery targeting
- correct stopping
- useful escalation
- unnecessary recovery attempts
- missed recoverable opportunities
- economic recovery value

The most important business metric is expected/recovered **₹ value**, not merely classification accuracy.

---

# 13. Why Event-Level Provider Failures Must Be Separated

The first OpenRouter 5-event test contained a provider failure.

That event ended as:

```text
decision_path = gated_override
override_reason = llm_call_failed
```

It should not be interpreted as a poor LLM decision.

We should report separately:

```text
MODEL QUALITY
```

and

```text
PROVIDER RELIABILITY
```

For example:

```text
AI decisions
LLM failures
Policy-filtered events
Safe fallback escalations
```

This prevents infrastructure problems from being incorrectly attributed to the model.

---

# 14. 20-Event OpenRouter Run

A 20-event run was performed using `openrouter/free`.

Summary:

```text
Total at-risk events: 20

Pre-filtered: 3 (15%)
  high_value_requires_human_review: 2
  attempts_exhausted: 1

Reached LLM: 17 (85%)

Pure AI decisions: 14 (70%)
Gated overrides: 3 (15%)
  llm_call_failed: 3
```

Final action breakdown:

```text
send_payment_link      10 (50%)
escalate_to_merchant    6 (30%)
recover_now             3 (15%)
stop                    1 (5%)
```

This confirmed the system can process a larger sample and safely handle failures.

---

# 15. 20-Event OpenRouter Decision Observations

The 20-event sample contained:

```text
3 policy-filtered
3 LLM failures
14 successful AI decisions
```

Therefore only 14 events were actual model decisions.

Among those 14:

- Most recoverable transactions received some form of recovery action.
- One non-recoverable transaction was correctly stopped.
- At least one non-recoverable transaction received a recovery action.
- Some recoverable transactions were escalated or assigned relatively low recovery probabilities.
- The model showed a tendency toward conservative decisions in uncertain cases.

Examples:

```text
Event 12
GT: recoverable
AI: escalate_to_merchant
P = 0.38
C = 0.62
```

```text
Event 16
GT: recoverable
AI: send_payment_link
P = 0.35
C = 0.78
```

```text
Event 15
GT: recoverable
AI: send_payment_link
P = 0.48
C = 0.72
```

The model often appeared uncertain even when the synthetic ground truth eventually showed recovery.

This does not necessarily mean the model is bad, but it is worth measuring systematically.

---

# 16. Friend's Perspective About Paid APIs

A friend suggested using a credit card to obtain OpenRouter credits.

The discussion considered whether this was appropriate for a student hackathon.

The conclusion:

- Paying for an API is not automatically cheating if the hackathon rules allow it.
- However, paying for a significantly stronger model could introduce a fairness/perception concern.
- Other students may not have the financial resources to pay.
- The project can have a stronger engineering story if it remains model/provider agnostic.
- The free-model approach demonstrates robustness under real-world infrastructure constraints.

The preferred direction was therefore:

**Do not immediately pay for a better model.**

If a professor can suggest:

- university credits
- academic API access
- research resources
- student programs
- free compute/API alternatives

those would be preferable.

---

# 17. Professor Email Discussion

A draft email was prepared asking a professor for guidance.

The email explained that:

- the baseline is already completed
- the recovery pipeline is already built
- the baseline will be compared against the AI agent
- multiple LLM providers were tested
- free-tier limits are making large-scale testing difficult
- free models are currently being used in rotation as a workaround
- model inconsistency is a concern
- advice on academic resources/API credits/alternative approaches would be appreciated

The important framing was:

> The project is already substantially built; the problem is practical LLM access for sufficiently large-scale execution.

---

# 18. Shift in Project Goal

A major clarification was made.

The immediate objective is **not primarily to benchmark models**.

The main end-product requirement is:

> RecoverAI should be able to synthesize/process approximately 1,000+ payment processes/events for the demo.

Therefore, the focus shifted from:

```text
Which single model is best?
```

to:

```text
How do we reliably process 1,000+ events using available free models?
```

---

# 19. Proposed Batch Strategy

The proposed approach is to process events in batches of 100.

For approximately 1,000 events:

```text
1,000 events
    ↓
10 batches × 100 events
```

Possible rotation:

```text
Batch 1 → Model A
Batch 2 → Model B
Batch 3 → Model C
Batch 4 → Model D
Batch 5 → Model E
Batch 6 → Model A
Batch 7 → Model B
...
```

Important:

**Do not randomly switch models inside a batch.**

Each batch should use one model so that:

- behavior is consistent within the batch
- logs remain understandable
- provider/model failures can be isolated
- model usage can be tracked

The batch strategy is intended primarily for **operational throughput**, not as a claim that five models are one identical model.

---

# 20. Important Caveat About Rotation

Rotating five models does not magically eliminate free-tier limits.

If a provider has:

```text
N requests/day
```

then the total capacity still depends on:

- per-model limits
- account-level limits
- provider limits
- OpenRouter free-model limits
- model availability
- rate limits

Therefore, the rotation must be tested rather than assumed to be unlimited.

---

# 21. Why Explicit Model Rotation May Be Better Than `openrouter/free`

`openrouter/free` automatically routes among available free models.

This is convenient but less reproducible.

For a hackathon demo, explicit rotation can be easier to explain:

```text
Batch 1 → Model A
Batch 2 → Model B
Batch 3 → Model C
...
```

The system can log the selected model for every batch.

This makes the demo transparent.

However, if the explicit models become unavailable, `openrouter/free` remains a useful fallback.

---

# 22. Current NVIDIA Free-Model Investigation

OpenRouter's NVIDIA catalog was checked to identify current free NVIDIA models.

Relevant general-purpose candidates discussed:

### Nemotron 3 Ultra

```text
nvidia/nemotron-3-ultra-550b-a55b:free
```

Large reasoning/agentic model.

### Nemotron 3.5 Lightning

```text
nvidia/nemotron-3.5-lightning:free
```

Lightweight/high-throughput agentic model.

### Nemotron 3 Super

```text
nvidia/nemotron-3-super-120b-a12b:free
```

Large model designed for complex reasoning/agentic workloads.

### Nemotron 3 Nano 30B A3B

A smaller general-purpose NVIDIA model that may also be usable.

### Nemotron 3 Nano Omni

Multimodal model; likely unnecessary for this text-only transaction task.

Other NVIDIA models such as:

- content safety models
- embedding models

are not appropriate replacements for the main decision-making LLM.

---

# 23. Important Conclusion About "Five NVIDIA Models"

There may not be five NVIDIA free **general-purpose decision models** that are appropriate for RecoverAI.

Therefore:

**Do not artificially select five NVIDIA models just to get five models.**

A better design is:

```text
NVIDIA free models
        +
Other high-quality free OpenRouter models
        ↓
Free model pool
        ↓
Batch rotation
```

This is more technically honest and gives better diversity.

---

# 24. Current Recommended Direction

At this point, the recommended project path is:

## Phase A — Stop API debugging

The core LLM pipeline has been proven to work.

Do not spend excessive time chasing:

```text
Puter
AgentRouter
paid API credits
```

unless a practical new resource becomes available.

---

## Phase B — Build the evaluation layer

Create an evaluation script that can report:

```text
Total events
AI decisions
Policy-filtered events
LLM failures

Ground-truth recoverable
Ground-truth not recoverable

Recovery targeting quality
Correct stop decisions
Unnecessary recovery attempts
Missed recoverable opportunities
Escalations

Ground-truth recovery value
Targeted recovery value
Missed recovery value
```

The economic metric should be emphasized:

```text
₹ recovery value
```

rather than simply accuracy.

---

## Phase C — Establish model pool

Find approximately 5 strong free models that:

- are currently available
- support structured JSON reasonably well
- can follow the RecoverAI decision schema
- are capable enough for the transaction reasoning task

NVIDIA models should be included where genuinely appropriate.

Other free models can fill remaining slots.

---

## Phase D — Implement batch processing

Target:

```text
batch_size = 100
```

with:

```text
model rotation
rate-limit handling
provider failure handling
logging
retry logic
safe escalation
```

Example:

```text
for each batch:
    select next available model
    process up to 100 events
    log model + batch + success/failure
    move to next model
```

---

# 25. What Should NOT Change

The following should remain stable:

### Ground Truth Policy

Do not modify it to make any particular model look better.

### Baseline detector

Do not modify it merely because an LLM makes a poor decision.

### Policy gates

Keep deterministic safety constraints.

### Decision schema

Keep the structured decision contract stable unless there is a real design reason to change it.

### Database separation

Keep:

```text
ground truth → synthetic_events
AI decision   → agent_decisions
```

This preserves experimental integrity.

---

# 26. Current Overall Status

RecoverAI has successfully reached the point where the complete core loop is functioning:

```text
Synthetic data
      ↓
Baseline detection
      ↓
At-risk transactions
      ↓
Ground-truth outcome
      ↓
Recovery agent
      ↓
LLM structured reasoning
      ↓
Policy safety gates
      ↓
Agent decisions stored in DB
      ↓
Evaluation
```

The remaining challenge is primarily **LLM availability/throughput**, not core application architecture.

---

# 27. Final Decision From This Discussion

The current plan is:

> **Move forward rather than continuing to chase a perfect free API.**

Use free LLMs through OpenRouter where available.

Use explicit batches of approximately 100 events.

Use a rotating pool of strong free models.

Prefer NVIDIA models where they are genuinely suitable, but do not force the pool to contain five NVIDIA models if five suitable free NVIDIA models are not available.

Keep the ground-truth policy and safety architecture independent of model choice.

The final demo should emphasize:

```text
1,000+ synthetic payment processes
        ↓
baseline detection
        ↓
AI recovery reasoning
        ↓
bounded policy-controlled actions
        ↓
measurable recovery outcomes
        ↓
₹ recovery impact
```

The key engineering story is **model-agnostic recovery intelligence with deterministic safety controls**, not simply access to an expensive LLM.
