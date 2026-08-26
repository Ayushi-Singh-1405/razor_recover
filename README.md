# RecoverAI

AI-powered revenue recovery for failed Razorpay transactions.

## Problem

Incomplete or failed payments cost businesses significant revenue. When a user abandons a payment link or a transaction fails silently, there's no automated system to detect, follow up, and recover that revenue.

## Solution

RecoverAI monitors Razorpay webhooks in real-time, detects failed/abandoned payments, and orchestrates recovery through intelligent payment link re-sends, escalating to human intervention when needed.

## Architecture

```
Razorpay Webhook → /webhook (signature verified, idempotent)
                          ↓
                   webhook_events table (deduplication)
                          ↓
                   Transaction status update (→ recovered)
                          ↓
                   Audit log entry (webhook_verified + revenue_recovered)
```

## Tech Stack

- **Backend:** FastAPI + SQLAlchemy + PostgreSQL (Neon)
- **Payments:** Razorpay SDK (orders, payment links, webhooks)
- **Migrations:** Alembic
- **Deployment:** (TBD)

## Project Structure

```
RecoverAI/
├── backend/           FastAPI application, DB models, migrations
├── frontend/          Dashboard UI (planned)
├── docs/              Architecture, specs, workflow, Razorpay docs
├── tests/             Smoke and integration tests
├── evaluation/        Datasets, metrics, failure analysis
├── pitch/             Buildathon pitch deck
├── demo/              Demo video
├── CHANGELOG.md       Release history
├── FAILURE_LOG.md     Bug and misconfiguration tracker
└── LICENSE            MIT
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/transactions/create-test-order` | Create test Razorpay order (₹4,999) |
| `POST` | `/transactions/{id}/create-payment-link` | Generate payment link for a transaction |
| `POST` | `/webhook` | Razorpay webhook receiver (verified, idempotent) |
| `GET` | `/audit/{transaction_id}` | Audit trail for a transaction |

## Setup

```bash
# 1. Clone and enter project
git clone <repo-url> && cd RecoverAI

# 2. Backend setup
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your Razorpay keys and DATABASE_URL

# 4. Run migrations
alembic upgrade head

# 5. Start server
uvicorn main:app --reload --port 8000

# 6. Run tests (in separate terminal)
cd ../tests
python3 test_phase0.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RAZORPAY_KEY_ID` | Razorpay API key ID |
| `RAZORPAY_KEY_SECRET` | Razorpay API key secret |
| `RAZORPAY_WEBHOOK_SECRET` | Webhook signature verification secret |
| `DATABASE_URL` | PostgreSQL connection string |

## License

MIT — see [LICENSE](LICENSE)
