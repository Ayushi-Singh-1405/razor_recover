This review is very good, and I agree with almost all of it. More importantly, it changes our immediate priority:

Do NOT start building the dashboard or AI agent yet. First prove that Razorpay Test Mode can support the exact recovery loop we want.

The reviewer has essentially identified our biggest risk: API/sandbox behavior, not AI.

I would make 3 small changes to the plan

1. Make SQLite the default for MVP.
I agree. PostgreSQL is unnecessary for a 7-day hackathon unless we need it later. We can structure the code so switching to Postgres is easy.

2. Don't commit to Anthropic specifically yet.
Use a provider-agnostic structured-output interface. That lets us switch models/API providers without rewriting the agent.

3. Phase 0 should have an even stricter exit condition.

By the end of Day 1, we need to prove:
Create Order
     ↓
Create Payment Link
     ↓
Customer/Test Payment
     ↓
Razorpay Webhook
     ↓
Verify Signature
     ↓
Update Local State
     ↓
Audit Log

If that works, we're in excellent shape.

If something doesn't work, we discover it on Day 1 rather than Day 5.

So our next task is VERY concrete
Today we build only this:

Razorpay → Backend → Webhook → Local audit log

No AI.

No fancy frontend.

No LangGraph.

No 1,000 records.

No PostgreSQL.

No dashboard.

Just prove the money-flow plumbing.

Once that works, then we build the intelligence on top of it.

And honestly, I like this approach much more. We're now treating this like an actual engineering sprint rather than jumping straight into "let's build an AI agent." 😭

Day 1 target

By tonight, we should be able to show something like:

[RAZORPAY TEST MODE]

Order: order_xxxxx
Amount: ₹4,999
Payment Link: plink_xxxxx

        ↓

[Test Payment]

        ↓

Webhook received
Event: payment_link.paid

        ↓

Signature ✓

        ↓

Local database

        ↓

AUDIT LOG

11:42:01 Order created
11:42:04 Payment Link created
11:43:17 Payment received
11:43:18 Webhook verified
11:43:18 Revenue recovered: ₹4,999

If we get this working, Phase 0 is DONE.

Then tomorrow we can start generating the 1,000-event synthetic world around this real API behavior.

And yes — I would follow the reviewer's 7-day schedule. It's realistic and, importantly, it leaves us a full day for evaluation/demo instead of discovering integration problems at the end.

Yes — Neon is actually a good choice, but I would use it carefully.

For this hackathon, I'd choose:

Neon PostgreSQL from Day 1, but keep the schema extremely small.

Why I'd use Neon

You already need persistent state for:

transactions
recovery attempts
agent decisions
policy decisions
webhook events
audit logs
evaluation results

And Neon gives us PostgreSQL without spending time managing a database server.

It also makes the architecture look more credible than:

"We stored everything in a JSON file." 😭

The key is: don't over-engineer it.

For MVP, I'd start with 5–6 tables:

transactions
customers
recovery_attempts
webhook_events
audit_logs
evaluation_results

That's enough.

Proposed architecture

Razorpay
    │
    ▼
FastAPI
    │
    ├──────────────► Neon PostgreSQL
    │                    │
    │                    ├── transactions
    │                    ├── recovery_attempts
    │                    ├── webhook_events
    │                    └── audit_logs
    │
    ▼
Recovery Agent
    │
    ▼
Policy Engine
    │
    ▼
Razorpay API

One important thing

Don't make Neon part of the critical Razorpay webhook path in a complicated way.

Keep the webhook handler simple:

Webhook arrives
 ↓
Verify signature
 ↓
Check event ID
 ↓
Persist event
 ↓
Update transaction
 ↓
Return 200

Then the agent can process the event separately.

That gives us resilience if the AI/model/API is slow.

My recommendation
Use:

Frontend
→ Next.js + TypeScript + Tailwind/shadcn

Backend
→ FastAPI

Database
→ Neon PostgreSQL

ORM
→ SQLAlchemy

Migrations
→ Alembic

AI
→ Provider-agnostic structured-output LLM

Payments
→ Razorpay Test Mode

Agent
→ Simple Python orchestration initially

Deployment
→ Vercel + a simple Python backend host + Neon

One change to the original plan

I would not wait until later to add migrations.

Set up:

FastAPI
+
SQLAlchemy
+
Alembic
+
Neon

during Phase 0, because database schema changes become annoying once we have the agent and webhook logic built.

But keep the schema tiny.

Neon = yes. PostgreSQL architecture astronautics = absolutely not. 😂

If we're committing to Neon, I would update the plan accordingly and make Neon + SQLAlchemy + Alembic our official stack from Day 1.

No — you do not need a paid AI API for this part, and for a 7-day hackathon I would actually avoid committing to one immediately.

Best approach for us

Build an abstraction like:

Recovery Agent
      ↓
LLM Provider Interface
      ↓
┌───────────────┬───────────────┐
│ Gemini        │ OpenRouter    │ Local Model   │
│ API           │ API           │ (fallback)    │
└───────────────┴───────────────┘

Then we can start with a free/cheap option and swap providers if necessary.

What does the AI actually need to do?

Not huge amounts of generation. It mainly needs to return structured decisions like:

{
  "diagnosis": "transient_payment_failure",
  "recovery_probability": 0.86,
  "recommended_action": "create_payment_link",
  "reason": "Customer has successful payment history and no previous recovery attempt",
  "confidence": 0.91
}

That's a relatively lightweight LLM task.

More importantly: don't use the LLM for things that don't need it.

For example:

Deterministic code:

amount > ₹10,000 → reject automation
attempts >= 2 → STOP
customer opted out → STOP

AI:

"What is probably causing this revenue loss?"
"Which allowed intervention makes the most sense?"
"Why?"

This keeps API usage low and makes the system safer.

What I'd recommend

For development, we can use a free-tier model/API if available, then switch if we hit limits.

And because we're building a hackathon project, I'd structure the code so changing:

GEMINI

to:

OPENROUTER

or another provider is basically a configuration change.

Do NOT buy an API subscription yet.

Let's first get the Razorpay integration working. Once that's done, we'll choose the AI provider based on what free-tier access you have and how well it handles structured tool calls.

Yes — the $5 OpenRouter credit is actually a very reasonable option for this project, especially once we reach the AI phase.

I checked OpenRouter's current pricing. The minimum credit purchase is currently $5, and those credits can be used across its available models/providers. OpenRouter also has free models, but the free tier is limited to 50 requests/day, so I wouldn't rely on that for the final demo.

What I'd do

Don't buy it today. Finish today's Razorpay/API work first.

When we reach Phase 2:

Day 1       → Razorpay API + Neon + Webhooks
Day 2–3     → Synthetic dataset + detection
Day 4       → AI integration
              ↓
           OpenRouter
              ↓
         structured output
              ↓
        Recovery decision

At that point, $5 is plenty to get started, because our agent isn't going to generate huge amounts of text. We're primarily asking for compact structured decisions such as:

{
  "diagnosis": "transient_payment_failure",
  "recovery_probability": 0.86,
  "recommended_action": "create_payment_link",
  "reason": "High-value returning customer with no previous recovery attempt"
}
And OpenRouter is particularly convenient for us

It supports an OpenAI-compatible API, and its models can support tool calling and structured outputs.

So we can write our agent around a generic interface:

RecoveryAgent
      ↓
LLMProvider
      ↓
OpenRouter
      ↓
[chosen model]

If we later decide another model performs better, we don't have to rewrite the whole agent.

One thing I'd definitely do

When you eventually buy the $5 credit, turn off Auto Recharge unless you specifically want it. OpenRouter supports automatic recharge, so we don't want an accidental charge during a frantic hackathon week.

And we can put a hard spending limit on the API key as an additional safety measure; OpenRouter supports per-key credit limits.

So our plan is now:

Today:
🟢 Razorpay Test Mode
🟢 Neon
🟢 FastAPI
🟢 Webhooks
🔴 No paid AI yet

When Phase 2 starts:
🟢 OpenRouter
🟢 Start with an inexpensive/free model
🟢 If quality is insufficient → use the $5 credits for a stronger model
🟢 Keep the LLM provider abstracted

I would absolutely be comfortable spending $5 on OpenRouter for the final build if we reach that point. It's a tiny cost relative to the potential value of getting this internship, and we can control the spend.
