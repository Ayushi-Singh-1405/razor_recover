# Day 1 Plan — RecoverAI (Phase 0 Sprint)

## Goal for Today

Prove the money-flow plumbing works end-to-end in Razorpay Test Mode, before writing a single line of AI or dashboard code.

**Exit condition:** One real recovery scenario runs start to finish and produces a clean audit log.

```text
Order created → Payment Link created → Test payment completed →
Webhook received → Signature verified → Event stored (idempotent) →
Transaction marked recovered → Audit log complete
```

If this works tonight, Phase 0 is DONE and the rest of the week builds on a proven foundation.

---

## Explicitly Out of Scope Today

- ❌ Dashboard / frontend
- ❌ Recovery agent / LLM integration
- ❌ Synthetic dataset (1,000 events)
- ❌ LangGraph or any agent framework
- ❌ Buying AI API credits
- ❌ Anything beyond the 4-table schema below

Today is plumbing only.

---

## Stack for Today

| Layer | Choice |
|---|---|
| Backend | FastAPI + Python |
| Database | Neon PostgreSQL (free tier) |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Payments | Razorpay Test Mode |
| Tunneling (for webhooks) | ngrok (or similar) |

---

## Database Schema (Today's Version)

Only 4 tables — nothing more.

```sql
CREATE TABLE transactions (
    id UUID PRIMARY KEY,
    razorpay_order_id VARCHAR,
    razorpay_payment_link_id VARCHAR,
    amount_paise INTEGER,
    status VARCHAR,          -- created, at_risk, recovered, escalated
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE recovery_attempts (
    id UUID PRIMARY KEY,
    transaction_id UUID REFERENCES transactions(id),
    action VARCHAR,          -- create_payment_link, escalate
    status VARCHAR,          -- pending, success, failed
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE webhook_events (
    id VARCHAR PRIMARY KEY,  -- Razorpay event id (idempotency key)
    event_type VARCHAR,
    payload JSONB,
    processed_at TIMESTAMP DEFAULT now()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    transaction_id UUID,
    event VARCHAR,
    details JSONB,
    timestamp TIMESTAMP DEFAULT now()
);
```

---

## Step-by-Step Checklist

### 1. Environment Setup
- [ ] Create Razorpay account, switch to Test Mode
- [ ] Generate Test API Key ID + Secret
- [ ] Create Neon project, get connection string
- [ ] Init FastAPI project (`main.py`, `models.py`, `db.py`)
- [ ] Install: `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `razorpay`, `python-dotenv`
- [ ] `.env` for `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `DATABASE_URL`

### 2. Database
- [ ] Define SQLAlchemy models for the 4 tables above
- [ ] Set up Alembic, run first migration against Neon
- [ ] Confirm tables exist in Neon dashboard

### 3. Orders API
- [ ] `POST /v1/orders` → create a ₹4,999 test order
- [ ] Store resulting `order_id` in `transactions` table (status = `created`)
- [ ] Confirm via `GET /v1/orders/{id}`

### 4. Payment Links API
- [ ] `POST /v1/payment_links` → create a recovery link referencing the order/transaction
- [ ] Store `payment_link_id` on the transaction row
- [ ] Set expiry + reference_id per the plan's policy fields

### 5. Test Payment
- [ ] Open the Payment Link, pay using Razorpay's documented test card
- [ ] Confirm payment shows as captured in Razorpay Test Mode dashboard

### 6. Webhook Setup
- [ ] Expose local FastAPI via ngrok
- [ ] Register webhook URL in Razorpay dashboard, subscribe to `payment_link.paid` (and `payment.failed` for later)
- [ ] Set webhook secret in `.env`

### 7. Webhook Handler
- [ ] `POST /webhook` endpoint:
  - [ ] Verify `X-Razorpay-Signature`
  - [ ] Parse payload, extract `event.id`
  - [ ] Idempotency check against `webhook_events` — if seen, return 200 immediately
  - [ ] Persist raw event to `webhook_events`
  - [ ] Update matching `transactions.status` → `recovered`
  - [ ] Write entries to `audit_logs`
  - [ ] Return 200 fast (no blocking work)

### 8. Audit Trail Output
- [ ] Simple script or endpoint (`GET /audit/{transaction_id}`) that prints the timeline:
```text
11:42:01 Order created
11:42:04 Payment Link created
11:43:17 Payment received
11:43:18 Webhook verified
11:43:18 Revenue recovered: ₹4,999
```

### 9. Sanity Checks
- [ ] Re-send the same webhook payload manually — confirm no duplicate processing
- [ ] Try an invalid signature — confirm it's rejected
- [ ] Confirm transaction status transitions are correct in the DB

---

## Definition of Done — Today

- [ ] Real order created via Razorpay Test Mode API
- [ ] Real Payment Link created and paid
- [ ] Webhook received and signature-verified
- [ ] Duplicate webhook delivery handled safely
- [ ] Transaction status updates correctly in Neon
- [ ] Full audit log visible for one transaction, end to end

If every box above is checked, Phase 0 is complete and tomorrow starts Phase 1 (synthetic dataset + detection) on a foundation that's already proven to work.
