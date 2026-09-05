# Revoco — Recorded Demo Script (~5 minutes)

Every number and row name below is real and currently in the system. Read the
[SCREEN] lines as camera directions; the quoted lines are narration.

## Pre-demo checklist (do NOT skip)

1. Server running: `cd backend && ../venv/bin/uvicorn main:app --port 8000`
   with `LIVE_EXECUTION_ENABLED=true` in the environment (needed for the
   live Approve beat).
2. Open the dashboard once before recording and expand one row — this warms
   the Neon connection and the 30s summary cache.
3. Decide the Approve beat: all current escalations are already resolved
   (approved and paid). For a fresh on-camera Approve, add one more
   over-cap order first: `cd backend && ../venv/bin/python demo_scenarios_extra.py`
   after adding a scenario to its list, or re-use the audit trail of
   `amount_above_cap` and narrate the approval from its chain instead.
4. Browser: signed in, on `http://localhost:8000/dashboard`, zoom ~110%.
5. Terminal visible in a second window (for the STOP beat, showing that no
   Razorpay call is logged).

---

## 1. [0:00-0:15] OPEN — Landing page

[SCREEN: http://localhost:8000/ — hero + pipeline chips]

> "Merchants lose money to failed and abandoned checkouts every day — and
> payment gateways only tell you that a payment failed. Revoco is an agentic
> recovery system: it detects the failures, reasons about which ones are
> worth recovering, and executes the recovery — through a policy gate that
> never lets the AI move money on its own."

Click **Sign in with Google** and complete the login.

## 2. [0:15-0:35] DASHBOARD — Detection benchmark

[SCREEN: hero section — REPECHAGE · stats · pipeline chips]

> "This is the live dashboard. The numbers on top are from a 1,000-transaction
> simulated benchmark: 65.4 lakh rupees at risk across 662 at-risk payments.
> The detector that produced this uses only observed signals — status,
> failure reason, attempt history. Below this, the Live Execution section is
> real: actual Razorpay Test Mode orders, actually recovered."

## 3. [0:35-1:00] LIVE EXECUTION — Summary row

[SCREEN: Live Execution card — summary strip]

> "Nine recovery scenarios ran through the policy gate. Six were executed,
> two were hard-stopped, one was escalated — and 29,295 rupees has been
> webhook-confirmed as recovered. Every rupee you'll see on this page has an
> audit entry behind it."

## 4. [1:00-1:40] LIVE EXECUTION — ACTION row with agent reasoning

[SCREEN: expand the `amount_above_cap_3` row (₹8,999 · ACTION · recovered)]

> "Let me open one. This was an eight-thousand-nine-hundred-rupee abandoned
> checkout. Here's the agent's actual decision block — its diagnosis, its
> reasoning, its confidence. Notice the agent was actually cautious on this
> one — it leaned stop because the customer had no payment history. The
> merchant reviewed it and approved. And the result: payment link created,
> customer paid, webhook confirmed — recovered."

[POINT: the Agent decision block — diagnosis, reasoning, probability,
confidence, and the model attribution line]

> "And that's the honest version of human-in-the-loop: the AI's caution is
> preserved in the record, the human's override is preserved too, and the
> outcome is measured."

## 5. [1:40-2:10] LIVE EXECUTION — STOP row

[SCREEN: `attempts_exhausted` row (₹1,999 · STOP)]

> "This one hit its attempt cap. The system stopped — and I mean actually
> stopped, no Razorpay call was made. That's not just a log message, it's
> enforced before the API is ever touched."

> "And notice the audit chain under it: multiple verification runs, same
> decision every time. Consistent, not flaky."

## 6. [2:10-2:50] LIVE EXECUTION — ESCALATE row + live Approve

[SCREEN: the remaining ESCALATE row — click Approve, live]

> "And this one — above our automated spending limit — got escalated to a
> human instead of guessing. Watch what happens when I approve it."

[click Approve, confirm, wait for it to complete]

> "That's a real payment link, created live, right now, because a person
> authorized it — not the AI."

[POINT: the updated row — MERCHANT APPROVED, the real payment-link URL]

> "The approval is audited with my identity on it, and the money trail
> continues: the customer pays, the webhook confirms, the dashboard shows
> it recovered."

## 7. [2:50-3:15] LIVE EXECUTION — System Status

[SCREEN: System Status widget]

★ "And notice this: LLM execution authority is disabled. The AI doesn't get
to move money on its own yet — and that's on purpose. I'll show you why in
a minute."

## 8. [3:15-4:00] ANALYTICS — the honest evaluation

[SCREEN: /analytics — tiles, then scroll through the charts]

> "So how do we know the agent's decisions are any good? We didn't trust it
> — we measured it. We ran the agent and a deterministic benchmark over the
> same 662 at-risk events, with identical economics, and ground truth the
> agent never saw."

> "The result, honestly: the agent is more precise per attempt — 73 percent
> versus 66 — with fewer bad interventions. But it's too conservative: it
> recovered 25.5 lakh net against the benchmark's 42.4. So today, the
> deterministic system handles execution, and the agent earns authority
> through evaluation — that trade-off is the actual finding, and we report
> it instead of hiding it."

[POINT: the comparison chart — agent bars vs benchmark bars]

## 9. [4:00-4:25] AUDIT — the receipts

[SCREEN: /audit — filter by scenario, scroll the chronological trail]

> "Everything I showed you is in here — every decision, every gate override,
> every approval, every recovery — with timestamps, identities, and the
> exact policy reason. Filterable by scenario and event type."

## 10. [4:25-4:45] CLOSE — architecture + tagline

[SCREEN: /developers or the pipeline diagram — Detect → Diagnose → Decide →
Policy Gate → Act → Audit]

> "Five stages, one gate, one audit trail. The agent reasons, the policy
> decides, and the money moves only when both agree."

[hold 2 seconds]

> "Revoco. Every failed payment, detected. Every recovery, decided and
> audited."

---

## Timing summary

| Beat | Segment | Duration |
|---|---|---|
| 1 | Open (landing) | 0:15 |
| 2 | Dashboard hero | 0:20 |
| 3 | Live Execution summary | 0:25 |
| 4 | ACTION row + agent reasoning | 0:40 |
| 5 | STOP row | 0:30 |
| 6 | ESCALATE + live Approve | 0:40 |
| 7 | System Status | 0:25 |
| 8 | Analytics (honest evaluation) | 0:45 |
| 9 | Audit | 0:25 |
| 10 | Close | 0:20 |
| | **Total** | **~5:05** |

## Contingencies

- **If a load takes >3s on camera:** say "this is a cross-region database
  call — in production the app deploys beside the database" and move on.
- **If the Approve button errors:** the row shows the failure in red with
  the reason — narrate it: "and that failure is audited too." Then use the
  already-approved `amount_above_cap` audit chain for the approval beat.
- **If asked "why did the agent say stop for a paid transaction?":** the
  recommendation pass ran after the webhook — the agent correctly sees the
  recovered status and refuses to re-contact the customer. That's the
  stopping rule working.
- **Never claim:** customer counts, uptime, certifications, or that the AI
  executes autonomously. It doesn't — that's the point.
