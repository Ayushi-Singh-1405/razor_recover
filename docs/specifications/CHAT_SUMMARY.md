# RecoverAI — Razorpay Hackathon — Session Summary

## Context

Ayu is building for Razorpay's Intern Hiring Hackathon, competing for an internship. Track chosen: **Track 03 — AI Revenue Recovery** (detect revenue at risk → diagnose → intervene → recover, with audit trail, bounded actions, and honest metrics). Timeline: 7 days.

Judging criteria:
- **Problem taste** — did you pick something that matters
- **Build quality** — does it run, is it structured, would you trust it
- **AI judgment** — the right tool in the right place, and where you chose not to use one
- **Failure recovery** — what broke, and what you did about it

## Track & Plan Decisions

- Track 03 chosen over Tracks 01/02/04/05 — best fit for reusing prior agentic-workflow experience (ClauseChain-style bounded loops, audit trails).
- A prior `RAZORPAY_BUILDATHON_PLAN.md` was reviewed and revised (`review_discuss.md`) before Day 1 started. Key changes from that review:
  1. **Neon PostgreSQL from Day 1** (not SQLite) — more credible architecture, still lightweight schema (4-6 tables).
  2. **Provider-agnostic LLM interface** — no AI provider committed yet; OpenRouter planned for Phase 2, not purchased yet.
  3. **Stricter Phase 0 exit condition** — prove the full money-flow loop (order → payment link → payment → webhook → DB → audit log) before writing any AI or dashboard code.

## Stack Locked In

- Frontend: Next.js + TypeScript + Tailwind/shadcn (not yet built)
- Backend: FastAPI + Python
- Database: Neon PostgreSQL
- ORM: SQLAlchemy + Alembic (migrations)
- Payments: Razorpay Test Mode
- AI: Provider-agnostic interface, OpenRouter planned for Phase 2 (not started)
- Agent: Simple Python orchestration (no LangGraph)

## Day 1 (Phase 0) — What Was Built

Repo: `razor_recover`, coded via opencode following a sequential prompt list.

**Prompts executed:**
1. FastAPI project scaffold (`main.py`, `db.py`, `models.py`, `config.py`, `.env.example`, health check)
2. Database models — 4 tables: `transactions`, `recovery_attempts`, `webhook_events`, `audit_logs`. Alembic configured against Neon, hand-written initial migration (JSONB via postgres dialect, UUID PKs).
3. Orders API integration — `POST /transactions/create-test-order` creates a real Razorpay Test Mode order, inserts a `transactions` row, writes `order_created` audit log.
4. Payment Links API integration — `POST /transactions/{id}/create-payment-link` creates a real payment link, updates the transaction, writes `payment_link_created` audit log.
5. Webhook handler — `POST /webhook`, signature verification, idempotency check, DB writes, audit logging.
6. Audit trail viewer — `GET /audit/{transaction_id}`, UUID-typed path param, returns `200 []` when empty (not 404).
7. Regression test script — `test_phase0.py`, checks idempotency, signature rejection, UUID validation, empty audit trail.

**Environment setup completed:**
- Razorpay Test Mode account + API keys
- Neon project + connection string
- ngrok tunnel + Razorpay webhook registered (URL + secret + 3 active events: `payment.failed`, `payment.captured`, `payment_link.paid`)
- Migration applied and verified (`alembic upgrade head`, tables confirmed in Neon)

## Real Bugs Found and Fixed (Day 1)

These are genuine "failure recovery" material for the hackathon submission:

1. **Silent signature-verification bypass.** The webhook handler's `except Exception: return {"status": "ignored"}` around `verify_webhook_signature` meant an invalid/forged signature returned 200 OK instead of being rejected. Fixed to `raise HTTPException(status_code=401, ...)`, with a `webhook_signature_rejected` audit log entry added for security-relevant traceability.

2. **Wrong event-ID source.** Code was reading `payload.get("id", "")` from the JSON body, but Razorpay does not send a top-level `id` in the webhook body — the actual unique identifier is in the `X-Razorpay-Event-Id` HTTP header. This caused every real webhook to silently no-op (`{"status": "ignored"}` with 200 OK) despite passing signature verification. Confirmed via a temporary debug dump of raw payload + headers, then fixed to read `request.headers.get("X-Razorpay-Event-Id", "")`.

Also fixed along the way:
- `create-test-order` / `create-payment-link` had a `500` when a literal placeholder (`{transaction_id}`) was sent instead of a real UUID — this was user error, not a code bug, but it surfaced that the UUID path param wasn't typed. Fixing the `/audit/{transaction_id}` route to use a proper `uuid.UUID` type param turned raw Postgres errors into clean `422` responses.
- Razorpay test card gotcha: the commonly-cited generic test number `4111 1111 1111 1111` was rejected as an unsupported international card. A working domestic Mastercard test number (`5267 3181 8797 5449`) was used successfully instead. Test OTP for card auth: `1234` (worked). Test mobile-number OTP is a real SMS in Test Mode (not simulated).

## End-to-End Verification (Confirmed Working)

Full loop proven live with a real payment (`pay_TUKTg0SaVCeCWG`, ₹4,999):

```
order_created → payment_link_created → revenue_recovered
```

- `transactions.status` correctly flips to `recovered`
- `webhook_events` correctly stores the event once (idempotent — Razorpay's duplicate delivery was deduplicated)
- `audit_logs` shows a clean, ordered trail
- `/audit/{transaction_id}` returns proper JSON, handles missing/invalid UUIDs cleanly, returns `200 []` for no data
- Signature rejection returns a real `401`

**Phase 0 exit condition met. Day 1 complete, on schedule.**

## Open Threads / Notes for Later

- `payment_link.entity.reference_id` in the real webhook payload did not match the transaction's actual UUID in one observed case — noted but not yet investigated; worth double-checking the matching logic in `_find_transaction_for_payload` doesn't rely on `reference_id` in a way that could silently mismatch.
- `webhook_verified` audit log entries are written with `transaction_id=None` by design (they fire before a transaction match is found), so they won't appear in `/audit/{transaction_id}` filtered results — this is expected behavior, not a bug.
- Debug logging (`webhook_debug.json` file writes, extra print statements) was added temporarily to diagnose the event-ID bug and was removed once the fix was confirmed.
