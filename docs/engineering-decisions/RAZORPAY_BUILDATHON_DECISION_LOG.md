# Razorpay AI Buildathon — Decision & Discussion Log

**Date:** 25 August 2026  
**Purpose:** Keep a complete study record of how we evaluated the Razorpay AI Buildathon tracks, investigated the available Razorpay APIs, and arrived at the final project direction.

---

# 1. Starting Point

The user shared the five Razorpay AI Buildathon tracks and explained that clearing the hiring hackathon is important because they are actively looking for an internship.

The initial objective was therefore not simply to choose the most interesting topic. The goal was to choose a project with the strongest combination of:

- probability of completion
- technical depth
- meaningful AI usage
- Razorpay relevance
- measurable business value
- strong demo potential
- ability to satisfy the judging criteria
- realistic API feasibility

---

# 2. The Five Tracks

## Track 01 — AI Growth & Agentic Commerce

### Goal

Grow merchant revenue or make a merchant transactable by an AI buyer end-to-end.

### Example directions

- Conversational in-app checkout
- Agent-readable catalog
- Upsell & cross-sell agent
- Campaign orchestrator

### Important judging requirement

> Every money action should be explainable, bounded and gated.

The demo should show an audit trail and at least one failure handled gracefully.

### Initial assessment

**Strengths**

- Very high "wow" factor
- Strong agentic AI potential
- Directly connected to the emerging AI-commerce ecosystem
- Could produce an impressive end-to-end demo

**Risks**

- Potentially more technically ambitious
- More moving parts around AI buyers, catalogs, checkout and payment
- Greater risk of building something that looks futuristic but is not fully functional

---

# 3. Track 02 — AI Risk Manager

## Goal

Stop merchants from losing money through fraud, returns and chargebacks.

### Example directions

- Chargeback evidence responder
- Return-risk scorer
- Fraud-spike detector
- Abuse-ring sentinel

### Judging requirement

The solution needs honest precision and recall on a held-out test set, including false-positive cost.

### Assessment

This track has strong ML depth and measurable evaluation.

However, it is harder to execute convincingly because:

- the dataset needs to be good
- precision/recall must be defensible
- false positives have a real business cost
- the solution must remain strictly defensive

It was therefore not the preferred track for our first implementation.

---

# 4. Track 03 — AI Revenue Recovery

## Goal

Find revenue that is slipping away and win it back.

The agent should:

1. Detect revenue at risk
2. Determine the appropriate intervention
3. Execute a bounded recovery workflow
4. Measure the money recovered

### Example directions

- Payment degradation → root cause → recovery action
- Checkout drop-off recovery
- Failed-subscription recovery
- B2B receivables chaser
- Mandate retry sequencer
- Hinglish voice recovery
- Promise-to-pay tracker

### Judging requirement

The project should demonstrate:

- measured money recovered across a batch
- compliant escalation
- stopping rules
- audit trail

### Why this immediately stood out

This track naturally forms a closed-loop agent:

```text
Detect
  ↓
Diagnose
  ↓
Decide
  ↓
Act
  ↓
Observe outcome
  ↓
Measure recovery
```

Unlike a simple prediction dashboard, the agent actually takes a bounded business action.

---

# 5. Track 04 — AI Finance Controller

## Goal

Run books and cash position.

The project must close one finance-operations loop across a batch of 50+ synthetic records and report:

- match rate
- unresolved exceptions

### Example directions

- Multi-source reconciliation
- Settlement Q&A agent
- Forward cash forecaster
- Tax-line matcher

### Assessment

This is a safe and practical track.

It has:

- strong data-processing potential
- clear evaluation
- relatively predictable implementation

However, Track 03 appeared to offer a stronger combination of agentic behavior and visible business impact.

---

# 6. Track 05 — Open Track

## Goal

Build anything that solves a real problem using meaningful AI.

### Assessment

This gives maximum freedom but also maximum responsibility for proving that the idea is valuable.

Because the other tracks already provide strong Razorpay-specific problems, we considered Open Track unnecessarily risky for this particular hiring objective.

---

# 7. Initial Track Ranking

Our first ranking was:

| Rank | Track | Main reason |
|---|---|---|
| 1 | Track 03 | Best balance of AI, measurability, feasibility and Razorpay relevance |
| 2 | Track 01 | Highest potential WOW factor |
| 3 | Track 04 | Safest technically |
| 4 | Track 02 | Strong but difficult to evaluate convincingly |
| 5 | Track 05 | Too open-ended and therefore riskier |

---

# 8. The First Track 03 Concept

We proposed a **Payment Recovery Agent**.

Example:

```text
1,000 transactions
        ↓
137 failed
        ↓
82 potentially recoverable
        ↓
Agent diagnoses why
        ↓
Agent selects intervention
        ↓
Recovery action
        ↓
51 recovered
        ↓
₹ recovered
```

Possible interventions:

- retry where legitimately supported
- payment reminder
- payment link
- escalation
- stop after configured attempts

The dashboard would show concrete business metrics such as:

- total revenue at risk
- recoverable revenue
- recovered revenue
- recovery rate
- number of escalations
- number of stopped workflows

This seemed especially strong because the Buildathon itself asks for measured money recovered rather than merely identifying a problem.

---

# 9. Why Track 01 Remained Interesting

We then examined Track 01 more closely.

The most interesting wording was:

> Make the merchant transactable by an AI buyer end-to-end.

This suggested an **AI Buyer ↔ AI Merchant** concept.

Example:

```text
User:
"Find me a black backpack under ₹2,500
that fits a 15-inch laptop."

        ↓

AI Buyer

        ↓

Agent-readable merchant catalog

        ↓

Compare products

        ↓

Select product

        ↓

Create cart/order

        ↓

Razorpay payment flow

        ↓

Merchant receives order
```

This had enormous demo potential.

However, it was also more ambitious.

The concern was that we might spend most of the hackathon solving commerce infrastructure instead of producing a polished, measurable product.

---

# 10. Track 01 Ideas Considered

## Idea A — Merchant Growth Manager

The merchant asks the AI to increase revenue.

The agent analyzes:

- product sales
- customer behavior
- product combinations
- conversion
- inventory

It proposes and executes bounded growth actions.

### Potential strength

Very strong AI/business story.

### Concern

More complex to make the revenue impact credible.

---

## Idea B — AI Buyer ↔ Merchant Agent

AI buyer discovers products, evaluates them and completes a purchase.

### Potential strength

Extremely futuristic and memorable.

### Concern

More technically ambitious and potentially dependent on capabilities that may not be fully available through the APIs.

---

## Idea C — AI Upsell Agent

After a purchase, the agent predicts an additional relevant purchase and creates a bounded offer.

Example:

```text
Customer bought headphones
        ↓
AI detects high probability of buying case
        ↓
Bounded offer
        ↓
Customer accepts
        ↓
Razorpay payment
        ↓
Incremental revenue
```

### Potential strength

Simpler and highly measurable.

### Concern

Less differentiated than the full AI-commerce concept.

---

# 11. Track 03 Ideas Considered

## Idea A — Revenue Recovery Agent

The system detects multiple forms of revenue loss and recovers eligible transactions.

This became the strongest candidate.

---

## Idea B — Checkout Rescue Agent

Focus specifically on abandoned checkout.

Example:

```text
₹4,999 cart
    ↓
Checkout started
    ↓
Payment abandoned
    ↓
AI determines high purchase intent
    ↓
Recovery Payment Link
    ↓
Customer pays
    ↓
₹4,999 recovered
```

### Strength

Very easy for judges to understand.

### Concern

Narrower than a broader revenue recovery system.

---

## Idea C — Failed Subscription Recovery Agent

The system detects subscription payment failures and applies a bounded recovery sequence.

Example:

```text
Payment failure
    ↓
Retry/reminder
    ↓
Second intervention
    ↓
Payment Link
    ↓
Escalation
    ↓
STOP
```

### Strength

Strong agentic workflow.

### Concern

More dependency on subscription-specific APIs and Test Mode behavior.

---

# 12. API Investigation

The user then provided the Razorpay Buildathon page and later the Razorpay developer documentation.

The key documentation areas identified were:

- Orders
- Payments
- Payment Links
- Subscriptions
- Invoices
- Webhooks
- Authentication
- Test Mode

---

# 13. Important Razorpay API Finding #1 — Authentication

Razorpay APIs use authentication based on the Razorpay API credentials.

The project should use **Test Mode credentials only**.

Important security rule:

> Never share the Key Secret in chat, GitHub, screenshots or public repositories.

Only environment variables should contain credentials.

Example conceptual configuration:

```text
RAZORPAY_KEY_ID
RAZORPAY_KEY_SECRET
```

---

# 14. Important Razorpay API Finding #2 — Payments

A crucial correction was made during the discussion.

The Payments API should not be treated as a generic "charge this customer again" API.

It is primarily useful for:

- retrieving payment information
- checking payment state
- working with payment/order context
- capturing authorized payments where applicable

Therefore, the recovery agent should use legitimate Razorpay payment products for new collection rather than pretending that it can arbitrarily retry every failed payment.

This made the project architecture more realistic.

---

# 15. Important Razorpay API Finding #3 — Payment Links

Payment Links became particularly important.

They can support recovery workflows involving:

- amount
- customer information
- reference ID
- expiry
- reminders/notifications
- payment status
- cancellation

This creates a concrete recovery action for the agent.

The intended workflow became:

```text
Revenue at risk
      ↓
AI diagnosis
      ↓
Recovery decision
      ↓
Policy gate
      ↓
Create Payment Link
      ↓
Customer completes payment
      ↓
Webhook
      ↓
Revenue recovered
```

---

# 16. Important Razorpay API Finding #4 — Webhooks

Webhooks are important because they allow the system to become event-driven.

Instead of constantly asking Razorpay:

> "Did this payment succeed?"

the system can receive an event.

Conceptually:

```text
Razorpay
   ↓
Webhook
   ↓
Backend
   ↓
Verify signature
   ↓
Check event ID / idempotency
   ↓
Update transaction
   ↓
Update recovery workflow
```

This significantly strengthens the architecture.

It also gives us an excellent demo moment:

> Payment completed → webhook arrives → dashboard automatically changes to "Recovered".

---

# 17. Test Mode Constraint

One practical constraint identified during the investigation was the Test Mode Payment Link limit.

The documented limit is **30 Payment Links per business in Test Mode**.

This affects the architecture.

We should NOT try to create hundreds of real Payment Links for our evaluation dataset.

Instead:

### Evaluation

Use:

```text
1,000+ synthetic events
```

### Live API demo

Use a small number of real Razorpay Test Mode interactions.

This gives us both:

- statistically meaningful evaluation
- real Razorpay API integration

---

# 18. The Final Decision

After comparing the tracks, ideas and API capabilities, we selected:

# Track 03 — AI Revenue Recovery

### Working project name

**RecoverAI**

### Initial focus

**Payment failure / checkout recovery using Razorpay Test Mode, Payment Links and Webhooks.**

### Core promise

> **Recover revenue automatically — but never blindly.**

---

# 19. Why We Chose Track 03

The decision came down to five major factors.

## 1. Measurable value

We can literally report:

```text
₹12.4L revenue at risk
₹4.82L recovered
38.9% recovery rate
```

That is much stronger than saying:

> "Our AI predicts which customers might buy."

---

## 2. Strong agentic behavior

The agent does not just answer questions.

It:

```text
Detects
→ Diagnoses
→ Decides
→ Requests permission through policy
→ Acts
→ Observes outcome
→ Continues/stops
```

---

## 3. Razorpay-native

The project naturally uses:

- Orders
- Payments
- Payment Links
- Webhooks
- Test Mode

So it feels like a Razorpay product rather than a generic AI project with a payment API added at the end.

---

## 4. Bounded automation

The Buildathon explicitly cares about safe, explainable money actions.

Our design therefore separates:

### AI

Reasoning and recommendation.

### Policy engine

Deterministic safety constraints.

### Razorpay API

Actual execution.

This gives us:

```text
AI decides
Policy controls
Razorpay executes
Webhook verifies
Audit trail proves
```

---

## 5. Strong demo

The final demo can contain a complete success and failure path.

### Success

```text
Payment failure
→ AI diagnoses
→ Recovery approved
→ Payment Link created
→ Test payment succeeds
→ Webhook received
→ ₹4,999 recovered
```

### Failure

```text
Payment failure
→ Recovery attempt
→ Failure
→ Second permitted attempt
→ Failure
→ STOP RULE
→ Human escalation
```

That directly addresses the Buildathon's requested failure-handling behavior.

---

# 20. Final Product Architecture

```text
                    Razorpay Test Mode
                           │
                           ▼
                    Webhook Gateway
                           │
                           ▼
                    Event Normalizer
                           │
                           ▼
                 Revenue Risk Detector
                           │
                           ▼
                    Recovery Agent
                  ┌────────┴────────┐
                  │                 │
             Diagnosis         Intervention
                  │                 │
                  └────────┬────────┘
                           ▼
                     Policy Gate
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
        Razorpay Action         Human Escalation
                │
                ▼
          Payment Link
                │
                ▼
        Customer Payment
                │
                ▼
             Webhook
                │
                ▼
        Metrics + Audit Log
```

---

# 21. AI's Role

The AI should meaningfully contribute to:

1. Diagnosing the likely cause of revenue loss.
2. Estimating recovery potential.
3. Selecting among approved interventions.
4. Generating recovery messaging.
5. Explaining the selected intervention.
6. Deciding when confidence is too low and human escalation is appropriate.

The AI must NOT:

- bypass safety policies
- access secrets
- invent transaction states
- make unrestricted money decisions
- endlessly retry
- contact customers without stopping rules

---

# 22. Tool Set

The agent should have a small explicit set of tools.

```text
get_transaction(transaction_id)
get_customer_context(customer_id)
get_recovery_history(transaction_id)
create_payment_link(amount, reference_id, expiry)
send_payment_link_reminder(link_id)
get_payment_link(link_id)
cancel_payment_link(link_id)
escalate_to_human(transaction_id, reason)
```

The policy engine must sit between the agent and money-moving actions.

---

# 23. Initial Safety Policy

Automated action is allowed when:

- transaction amount ≤ ₹10,000
- recovery confidence ≥ 0.70
- fewer than 2 previous recovery attempts
- no recovery action occurred in the previous 24 hours
- transaction is not flagged for manual review
- customer has not opted out
- intervention is in the approved action set

Human escalation occurs when:

- confidence < 0.70
- amount > ₹10,000
- repeated failure
- conflicting signals
- suspected risk
- action exceeds configured limits

STOP conditions:

- payment succeeds
- maximum attempts reached
- link expires
- customer opts out
- policy violation
- manual escalation accepted
- transaction becomes non-recoverable

---

# 24. Synthetic Dataset Plan

We decided to build a dataset of at least **1,000 revenue events**.

Potential fields:

```text
transaction_id
customer_id
timestamp
amount
currency
payment_status
failure_reason
payment_method
customer_tenure_days
customer_previous_payments
customer_previous_failures
average_order_value
checkout_started
checkout_completed
subscription_status
days_overdue
previous_recovery_attempts
last_recovery_action
ground_truth_recoverable
ground_truth_recovery_outcome
ground_truth_recovered_amount
```

The dataset will allow us to measure performance honestly instead of demonstrating only hand-picked examples.

---

# 25. Evaluation Plan

### Model/detection metrics

- Precision
- Recall
- F1
- Confusion matrix

### Business metrics

- Revenue at risk
- Recoverable revenue
- Recovered revenue
- Recovery rate
- Average recovered amount

### Safety/cost metrics

- False intervention count
- False intervention cost
- Automation rate
- Escalation rate
- Number of stopped workflows
- Average interventions per recovery

A held-out test set should be maintained.

---

# 26. Dashboard Plan

The dashboard should immediately show business impact.

Example:

```text
₹12.4L
Revenue at Risk

₹4.82L
Recovered

38.9%
Recovery Rate

1,000
Events Analyzed
```

Then a recovery funnel:

```text
1,000 events
    ↓
143 at risk
    ↓
91 recoverable
    ↓
74 interventions
    ↓
63 recovered
```

A transaction detail screen should show:

- detected problem
- relevant customer context
- AI diagnosis
- confidence
- alternatives considered
- policy decision
- Razorpay action
- webhook outcome
- final recovery state

---

# 27. Planned Demo

## 0:00–0:30

Explain the problem:

> Revenue leakage isn't one problem. Payments fail, customers abandon checkout, and merchants often have to recover each case manually.

## 0:30–1:15

Run the batch.

Show:

```text
₹12.4L at risk
143 events detected
```

## 1:15–2:15

Open one case.

Show why the agent chose its intervention.

## 2:15–3:15

Execute a real Razorpay Test Mode recovery action.

Show:

```text
Payment Link
→ Test payment
→ Webhook
→ ₹4,999 recovered
```

## 3:15–4:00

Demonstrate failure.

Show:

```text
Attempt 1 → failed
Attempt 2 → failed
STOP
→ Human escalation
```

## 4:00–4:40

Show batch metrics.

## 4:40–5:00

Show architecture and close with:

> **AI decides. Policy controls. Razorpay executes. Webhooks verify. Audit trail proves what happened.**

---

# 28. Scope Control

We explicitly decided NOT to build everything.

Initial MVP will NOT include:

- voice recovery
- WhatsApp integration
- full CRM
- complex segmentation
- multi-agent architecture
- custom ML model
- subscription recovery
- invoice recovery
- fraud detection
- large notification infrastructure

These can become future extensions.

The priority is:

> **One deep, reliable revenue-recovery loop.**

---

# 29. Implementation Sequence

The planned build sequence is:

### Phase 0 — API validation

- Set up Razorpay Test Mode.
- Create test credentials.
- Validate authentication.
- Create an order.
- Retrieve payment/order information.
- Create a Payment Link.
- Complete a Test Mode payment.
- Configure a webhook.
- Verify webhook signatures.
- Test duplicate event handling.

### Phase 1 — Synthetic engine

- Generate 1,000+ events.
- Define ground truth.
- Implement detector.
- Build evaluation scripts.

### Phase 2 — Recovery Agent

- Diagnosis
- Recovery scoring
- Tool calling
- Intervention selection
- Policy gate
- Stopping rules
- Escalation

### Phase 3 — Razorpay integration

Implement:

```text
failure
→ agent
→ policy
→ Payment Link
→ payment
→ webhook
→ recovered
```

### Phase 4 — Dashboard

Build:

- Overview
- Recovery funnel
- Transaction details
- Agent reasoning
- Audit trail
- Metrics
- Failure/escalation view

### Phase 5 — Evaluation

Run the held-out dataset and record all metrics honestly.

### Phase 6 — Polish

- Error states
- Loading states
- API timeout handling
- Idempotency
- Secret management
- README
- Architecture diagram
- Demo dataset
- 5-minute pitch

---

# 30. Current Final Decision

## Selected Track

**Track 03 — AI Revenue Recovery**

## Product

**RecoverAI**

## Initial Use Case

**Payment failure / checkout recovery**

## Core Razorpay Components

**Test Mode + Payment Links + Orders + Payments + Webhooks**

## Core AI Capability

**Diagnose revenue loss and select the best bounded recovery intervention.**

## Core Business Metric

**Actual revenue recovered across a batch.**

## Core Safety Principle

**The AI recommends and reasons; deterministic policy controls financial actions.**

---

# 31. Key Lesson From the Decision

The main lesson from this discussion is that the strongest hackathon idea isn't necessarily the most futuristic one.

We compared:

```text
Track 01:
Highest WOW
        vs.
Track 03:
Best balance of WOW + feasibility + measurable value
```

Track 01's AI Buyer ↔ Merchant idea was extremely attractive, but its larger implementation surface created more execution risk.

Track 03 lets us demonstrate a complete closed-loop system with real Razorpay Test Mode interactions while still showing sophisticated agentic behavior.

Therefore:

> **We chose depth and proof over breadth and hype.**

---

# 32. Reference Links

- Razorpay Buildathon: https://razorpay.com/buildathon/
- Razorpay Developer Documentation: https://razorpay.com/docs/
- Razorpay API Reference: https://razorpay.com/docs/api/
- Authentication: https://razorpay.com/docs/api/authentication/
- Orders API: https://razorpay.com/docs/api/orders/
- Payments API: https://razorpay.com/docs/api/payments/
- Payment Links API: https://razorpay.com/docs/api/payments/payment-links/
- Payment Link Creation: https://razorpay.com/docs/api/payments/payment-links/create-standard/
- Subscriptions API: https://razorpay.com/docs/api/payments/subscriptions/
- Webhooks: https://razorpay.com/docs/webhooks/
- Webhook Test/Validation: https://razorpay.com/docs/webhooks/validate-test/

---

# 33. Files Created During This Process

## Main implementation plan

`RAZORPAY_BUILDATHON_PLAN.md`

Contains:

- project architecture
- implementation phases
- dataset plan
- evaluation metrics
- API strategy
- dashboard plan
- demo flow
- definition of done

## This file

`RAZORPAY_BUILDATHON_DECISION_LOG.md`

Contains:

- original track descriptions
- track comparison
- ideas considered
- API discoveries
- reasoning behind rejected alternatives
- final decision
- lessons from the decision process

---

# Final Status

**Decision:** Made

**Track:** 03 — AI Revenue Recovery

**Project:** RecoverAI

**Next milestone:** Validate the Razorpay Test Mode API end-to-end before writing the full application.

