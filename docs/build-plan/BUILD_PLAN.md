# Razorpay AI Buildathon — Project Plan

## 1. Goal

Build a production-style AI agent for **Track 03 — AI Revenue Recovery** that detects revenue at risk, diagnoses the likely cause, selects a bounded intervention, executes an appropriate Razorpay Test Mode action, and measures the money recovered.

**Working name:** RecoverAI
**Track:** 03 — AI Revenue Recovery

The Buildathon explicitly asks for a workflow that goes beyond detection: it should show measured money recovered across a batch, compliant escalation, stopping rules, and an audit trail.

---

## 2. Core Product

### RecoverAI — Autonomous Revenue Recovery Agent

The system ingests a batch of synthetic merchant payment/revenue events and continuously evaluates them for recoverability.

### Core loop

```text
Razorpay / synthetic event
        ↓
Revenue-at-risk detector
        ↓
Root-cause diagnosis
        ↓
Customer + transaction context
        ↓
Recovery decision
        ↓
Policy / risk gate
        ↓
Razorpay action
        ↓
Webhook / outcome
        ↓
Recovery measurement
        ↓
Audit trail
```

The agent should never have unrestricted authority over money.

Every action must pass explicit policy constraints such as:

- maximum number of attempts
- maximum discount/incentive
- maximum amount per automated action
- allowed intervention types
- cooldown between interventions
- escalation conditions
- hard STOP conditions

---

## 3. Why Track 03

### Why this track is the strongest choice

- Directly aligned with Razorpay's payment infrastructure.
- Gives us a measurable business outcome: **₹ recovered**.
- Naturally supports an agentic workflow rather than a chatbot.
- Allows real Test Mode API integration while keeping the rest of the evaluation dataset synthetic.
- The judging bar gives us clear success metrics.
- Failure handling, bounded automation and auditability can be demonstrated visibly.

### Main demo metric

> **Recovered Revenue = value of previously-at-risk transactions that successfully complete recovery.**

Supporting metrics:

- Recovery rate
- Revenue-at-risk
- Recovery precision
- Intervention success rate
- Automation rate
- Escalation rate
- Average interventions per recovered transaction
- False-intervention cost
- Stopped workflows

---

## 4. Initial Use Case

We will start with **payment failure + checkout/payment-link recovery** rather than attempting every possible revenue-loss scenario.

### Example

```text
Transaction: ₹4,999
Status: failed
Customer history: 4 previous successful payments
Failure context: transient failure
Recovery probability: high
```

Agent decides:

```text
Action: create recovery Payment Link
Reason:
- high customer value
- payment is recoverable
- no prior recovery attempt
- amount is below automation limit
```

Policy gate:

```text
✓ Amount within limit
✓ Attempts < 2
✓ No recent recovery action
✓ Customer eligible
→ APPROVE
```

Razorpay action:

```text
Create Payment Link
Set expiry
Set reference ID
Enable/disable reminders according to policy
```

Outcome:

```text
Payment successful
→ ₹4,999 recovered
→ workflow closed
```

If recovery fails repeatedly:

```text
Attempt 1 → failed
Attempt 2 → failed
STOP
→ human escalation
```

---

## 5. Razorpay Integration

Razorpay APIs are RESTful and provide Test API Keys. Most APIs use the `/v1` gateway. Orders can be created and associated with payments.

Useful APIs for our MVP:

### Orders

Use for:

- creating test orders
- retrieving order state
- linking/retrieving associated payments
- demonstrating payment context

### Payments

Use for:

- retrieving payment information
- observing payment state
- correlating payments with orders

Important: the Payments API itself is not a generic mechanism for collecting a new payment. Our recovery workflow should therefore use appropriate payment products rather than pretending the agent can arbitrarily charge a customer.

### Payment Links

This is the primary recovery action for the MVP.

Use for:

- creating recovery payment requests
- expiry
- reference IDs
- customer information
- notifications/reminders
- fetching status
- cancelling links when necessary

Razorpay currently documents a **30 Payment Link limit per business in Test Mode**, so the live API demo should use a small number of real Test Mode links while the larger evaluation batch remains synthetic.

### Subscriptions / Invoices

Phase 2 option:

- failed subscription recovery
- overdue invoice recovery
- reminder/escalation workflows

Do not build these before the core payment-recovery workflow is stable.

### Webhooks

Webhooks are important to make the system event-driven.

The system should react to events rather than continuously polling.

Test Mode webhook events can be triggered by Test Mode transactions. Webhook signatures must be verified, and duplicate event delivery must be handled using the Razorpay event ID.

---

## 6. System Architecture

```text
                    ┌─────────────────────┐
                    │ Razorpay Test Mode  │
                    └──────────┬──────────┘
                               │
                    payments / orders /
                    payment-link events
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Webhook Gateway     │
                    │ signature +         │
                    │ idempotency         │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Event Normalizer    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Revenue Risk Engine │
                    │ detect at-risk      │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Recovery Agent      │
                    │ diagnose + decide   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Policy / Guardrail  │
                    │ deterministic gate  │
                    └──────────┬──────────┘
                               │
                   ┌───────────┴───────────┐
                   ▼                       ▼
          ┌─────────────────┐      ┌────────────────┐
          │ Razorpay Action │      │ Human Review   │
          │ Payment Link    │      │ / Escalation   │
          └────────┬────────┘      └────────────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Outcome Webhook │
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Metrics + Audit │
          └─────────────────┘
```

---

## 7. AI Responsibilities

The AI should have meaningful responsibility, not just generate text.

### AI should:

1. Diagnose the likely revenue-loss reason.
2. Estimate recovery potential.
3. Select among allowed intervention strategies.
4. Explain why the intervention was selected.
5. Generate customer-facing recovery messaging.
6. Recommend escalation when confidence is low.
7. Summarize batch-level recovery performance.

### AI should NOT:

- bypass the policy gate
- invent payment states
- directly access secrets
- decide arbitrary spending limits
- repeatedly contact customers without stopping rules
- execute actions outside the permitted tool set

---

## 8. Tool Calling

Give the agent a small, explicit toolset.

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

The policy engine sits between the agent and money-moving actions.

Example:

```text
Agent:
create_payment_link(...)

        ↓

Policy Gate:
Is action allowed?

        ↓ YES

Razorpay API
```

This makes the system explainable and bounded.

---

## 9. Recovery Policy

Initial policy:

### Automated action allowed when

- transaction amount ≤ ₹10,000
- recovery confidence ≥ 0.70
- fewer than 2 previous recovery attempts
- no recovery action in previous 24 hours
- transaction is not flagged for manual review
- customer has not opted out
- intervention is in the approved action set

### Human escalation when

- confidence < 0.70
- amount > ₹10,000
- repeated failure
- conflicting customer/payment signals
- suspected fraud/risk
- action would exceed configured limits

### STOP conditions

- successful payment
- maximum attempts reached
- link expired
- customer opted out
- policy violation
- manual escalation accepted
- transaction becomes non-recoverable

---

## 10. Synthetic Dataset

Build a dataset of **1,000+ revenue events**.

Suggested fields:

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

### Scenario distribution

Example:

- 35% successful payments
- 20% transient payment failures
- 15% repeated payment failures
- 10% checkout abandonment
- 10% overdue invoices
- 5% subscription failures
- 5% non-recoverable/manual-review cases

The exact distribution should be finalized after implementation testing.

---

## 11. Evaluation

We must separate:

### Detection metrics

- Precision
- Recall
- F1
- Confusion matrix

### Business metrics

- Total revenue at risk
- Total recoverable revenue
- Total recovered revenue
- Recovery rate
- Revenue recovery uplift
- Average recovered value

### Cost / safety metrics

- False intervention count
- False intervention cost
- Number of automated actions
- Number of escalations
- Number of workflows stopped
- Maximum actions per customer

### Important

We should evaluate against a **held-out test set** and avoid tuning on the final evaluation data.

---

## 12. Dashboard

The first screen should immediately communicate business impact.

### KPI cards

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

### Recovery funnel

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

### Agent activity

```text
Payment failed
→ diagnosed as transient
→ recovery confidence 0.86
→ Payment Link created
→ payment received
→ ₹4,999 recovered
```

### Audit panel

Show:

- timestamp
- transaction
- detected issue
- AI reasoning summary
- policy decision
- action
- API result
- outcome
- next action / STOP reason

---

## 13. Failure Demo

The final pitch MUST include one failure handled gracefully.

Example:

```text
Payment failure
      ↓
Agent recommends recovery
      ↓
Payment Link created
      ↓
Payment fails
      ↓
Agent attempts second permitted intervention
      ↓
Payment fails again
      ↓
STOP RULE TRIGGERED
      ↓
Human escalation
```

The dashboard should explicitly say:

> Automation stopped after 2 unsuccessful recovery attempts. No further automated action was permitted.

This directly demonstrates bounded behavior.

---

## 14. Tech Stack

### Frontend

- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- Recharts

### Backend

- Python
- FastAPI

### Agent

Start simple:

- Python agent orchestration
- structured tool calling
- deterministic policy engine

Optional later:

- LangGraph

### Database

- PostgreSQL
- SQLAlchemy

For the hackathon, keep infrastructure simple.

### AI

Use a model with reliable structured output/tool calling.

LLM responsibilities should remain limited to reasoning/diagnosis/selection while deterministic code controls money actions.

### Deployment

- Docker
- Vercel for frontend
- Render/Railway/Fly.io or similar for backend
- managed PostgreSQL

Do not over-engineer Kubernetes or microservices unless the MVP is already complete.

---

## 15. Build Phases

### Phase 0 — API validation

- Create Razorpay Test Mode account/keys.
- Test authentication.
- Create one order.
- Retrieve payment/order information.
- Create one Payment Link.
- Complete a Test Mode payment.
- Configure a webhook.
- Verify webhook signature.
- Handle duplicate event IDs.

**Exit condition:** one real end-to-end Razorpay Test Mode transaction works.

---

### Phase 1 — Synthetic engine

- Generate 1,000+ events.
- Build revenue-at-risk detector.
- Define ground truth.
- Build evaluation script.
- Produce baseline metrics.

**Exit condition:** we can calculate precision/recall and ₹ at risk/recovered.

---

### Phase 2 — Recovery Agent

Implement:

- diagnosis
- recovery scoring
- tool calling
- intervention selection
- policy gate
- stopping rules
- escalation

**Exit condition:** agent can process a batch without unrestricted API access.

---

### Phase 3 — Razorpay integration

Connect:

- Orders
- Payments
- Payment Links
- Webhooks

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

**Exit condition:** real Test Mode recovery loop demonstrated.

---

### Phase 4 — Dashboard

Build:

- overview
- recovery funnel
- transaction detail
- agent reasoning
- audit trail
- intervention history
- metrics
- failure/escalation view

**Exit condition:** judge can understand the product within 30 seconds.

---

### Phase 5 — Evaluation

Run the held-out dataset.

Record:

- precision
- recall
- F1
- recovery rate
- ₹ recovered
- false intervention cost
- automation rate
- escalation rate

Do not cherry-pick successful examples.

---

### Phase 6 — Polish

- error states
- loading states
- empty states
- retry handling
- webhook idempotency
- API timeout handling
- secret management
- README
- architecture diagram
- demo dataset
- 5-minute pitch

---

## 16. What NOT to Build

Avoid scope creep.

### Do not initially build:

- voice recovery
- WhatsApp integration
- full CRM
- complex customer segmentation
- multi-agent architecture
- custom ML model
- subscription recovery
- invoice recovery
- fraud detection
- production-grade notification infrastructure

These can be mentioned as future extensions.

The MVP should be one **deep, reliable revenue-recovery loop**.

---

## 17. Target Demo Flow

### 0:00–0:30 — Problem

Show:

> Merchants don't lose revenue in one obvious place. Payments fail, customers abandon checkout, and recovery is often manual.

### 0:30–1:15 — Detect

Upload/run the 1,000-event batch.

Show:

> ₹12.4L at risk
> 143 events detected

### 1:15–2:15 — Agent reasoning

Open one transaction.

Show:

> Why did the agent choose this intervention?

Display:

- context
- confidence
- alternatives rejected
- policy decision

### 2:15–3:15 — Real Razorpay action

Agent creates a Payment Link in Test Mode.

Complete the test payment.

Webhook arrives.

Dashboard updates:

> ₹4,999 recovered

### 3:15–4:00 — Failure

Trigger second failure.

Show:

> Maximum recovery attempts reached → STOP → Human escalation

### 4:00–4:40 — Batch metrics

Show:

- recovered revenue
- recovery rate
- precision/recall
- false intervention cost
- escalation rate

### 4:40–5:00 — Architecture + close

Show architecture and emphasize:

> AI decides.
> Policy controls.
> Razorpay executes.
> Webhooks verify.
> Audit trail proves what happened.

---

## 18. Definition of Done

The project is submission-ready only when all of these are true:

- 1,000+ synthetic events processed
- Held-out evaluation set exists
- Revenue-at-risk detection has measured metrics
- Agent diagnoses revenue-loss cases
- Agent selects an intervention
- Deterministic policy gate controls money actions
- Razorpay Test Mode is integrated
- At least one real Test Mode recovery action works
- Webhook is received and verified
- Duplicate webhook handling exists
- Successful recovery updates revenue metrics
- Failure path stops safely
- Human escalation is demonstrated
- Audit trail is visible
- Dashboard is polished
- Public GitHub repository is ready
- Architecture diagram is ready
- 5-minute pitch is recorded
- README contains setup + architecture + evaluation methodology

---

## 19. Current Decision

**Track 03 — AI Revenue Recovery**

**Working product:** RecoverAI

**Initial focus:** Payment failure / checkout recovery using Razorpay Test Mode + Payment Links + Webhooks.

**Core promise:**

> Recover revenue automatically — but never blindly.

---

## 20. Immediate Next Steps

1. Create Razorpay Test Mode account.
2. Generate Test API credentials.
3. Validate Orders API.
4. Validate Payment Link API.
5. Configure a webhook endpoint.
6. Run one successful Test Mode payment.
7. Run one failed/recovery scenario.
8. Build the 1,000-event synthetic dataset.
9. Implement the deterministic recovery baseline.
10. Add the AI decision layer.
11. Build the dashboard.
12. Run held-out evaluation.
13. Record the demo.
14. Submit.

## References

- Razorpay AI Buildathon: https://razorpay.com/buildathon/
- Razorpay API Reference: https://razorpay.com/docs/api/
- Orders API: https://razorpay.com/docs/api/orders/
- Payments API: https://razorpay.com/docs/api/payments/
- Payment Links API: https://razorpay.com/docs/api/payments/payment-links/
- Payment Link creation: https://razorpay.com/docs/api/payments/payment-links/create-standard/
- Subscriptions API: https://razorpay.com/docs/api/payments/subscriptions/
- Invoices API: https://razorpay.com/docs/api/payments/invoices/
- Webhook validation/testing: https://razorpay.com/docs/webhooks/validate-test/
