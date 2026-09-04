# Day 5 Plan — RecoverAI (Phase 4: Dashboard)
### v2 — revised after review: agent-first narrative, benchmark renamed and demoted, decision-gate made visually central

## Where You're Starting From

Phases 0-3 are done. You have real numbers, real audit trails, and real money-recovery evidence. The dashboard's job is to make that legible in 30 seconds — but the *story order* matters as much as the numbers themselves.

**Narrative correction, agreed on before building anything:** the project is not "we built a deterministic system and tried AI." It's **"we built an agentic recovery system — detect, diagnose, decide, gate, act, audit — and deliberately established a deterministic benchmark so we could measure whether agentic reasoning earns execution authority."** The benchmark is an evaluation instrument, not the product. Lead with the working agent architecture; show the benchmark only after the product has already proven itself.

**Terminology change, applied everywhere on the dashboard and in the write-up:**
- "AI Experiment" → **"Agent Evaluation"** or **"Recovery Agent Evaluation"**
- "Baseline vs AI" → **"Agent vs Deterministic Benchmark"**
- The benchmark's own name stays honest: it's a reference point, not a competing product

**One guardrail this reframing must not lose:** the system currently authorized to take *real* action (Phase 3/Day 4) runs on the **deterministic policy gate**, not the LLM agent's reasoning — the agent was evaluated and not yet granted execution authority. When you lead with "the agent works," the live-execution proof underneath it must carry its own honest label right next to the live numbers — not three sections later. A judge should never have to wonder, even for a second, whether the LLM is the thing that just created a real payment link. It isn't, yet.

## Goal for Today

Build one screen, ordered to tell the truth in the order a judge would actually want to hear it: *does it work → does it decide safely → does a human stay in control → how do we know the agent's judgment is any good.*

**Exit condition:** A judge watching for 30-60 seconds understands: RecoverAI is a working agentic recovery system with a policy gate between reasoning and money movement; it has real proof of bounded execution against Razorpay Test Mode; escalated cases go to a human, live, on screen; and — only if they ask "how do you know the agent's good" — there's a rigorous, honest benchmark answering that question, clearly separated from the live product.

---

## Explicitly Out of Scope Today

- ❌ General-purpose transaction browsing/search UI
- ❌ Real-time polling/websockets — static or refresh-on-load is fine, this is a demo, not production
- ❌ Building out every screen from the original master plan's Section 12 — one well-ordered screen beats eight
- ❌ Polishing animations/transitions before the numbers on screen are correct

---

## Step 0 — Visual Identity and Login (JWT + Google OAuth)

**Visual identity:** clean fintech aesthetic in the spirit of Razorpay/Stripe — card-based layout, generous whitespace, a confident blue/dark accent palette, clean sans-serif type — without literally cloning either company's logo or page structure. Product name: **RecoverAI**.

**Login: JWT + Google OAuth.**

- [ ] **Manual setup first, before any code:** register an OAuth client in [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Create OAuth Client ID (type: Web application). Add your local dev callback URL (e.g. `http://localhost:8000/auth/google/callback`) to authorized redirect URIs. Note the Client ID and Client Secret. Do this first, separately from writing code — it has propagation delay and its own failure modes.
- [ ] Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env` / `.env.example`
- [ ] Build the OAuth flow: `GET /auth/google/login` → Google consent → `GET /auth/google/callback` exchanges the code for the user's profile, creates/looks up a local `merchants` row, issues a signed JWT (httpOnly cookie or bearer token, your choice)
- [ ] JWT verification middleware on all dashboard and escalation-action routes
- [ ] Frontend: "Sign in with Google" landing screen → redirect to dashboard on success
- [ ] Test the full flow with your own account once, before it's demo material

---

## Step 1 — Decide What Actually Goes on Screen, in What Order

Four data sources, kept distinct, but now ordered by narrative priority rather than build order:

1. **Real execution** (Day 4 — 6 real Test Mode scenarios, actual Razorpay API calls, ₹4,498 recovered) — **leads**
2. **Human oversight / escalation approval** (Section E — live, clickable) — **second**
3. **Detection scale** (Day 2 — 1,000 events, ₹65.4L at risk) — **framing context, brief**
4. **Agent Evaluation / Benchmark** (Day 3 — renamed per above, demoted to the bottom) — **last, answers "how do you know it's good"**

- [ ] Write one sentence per number, same discipline as before, but now also tag each with a provenance label the UI will actually show: `SIMULATED · Day 2/3` or `REAL · Razorpay Test Mode · Day 4`
- [ ] Decide the exact section order for the page (Step 3 below reflects the recommended order — confirm you're building in this sequence, not KPIs-then-benchmark-then-execution as originally planned)

## Step 2 — Backend: One Endpoint, Same Shape, Renamed Fields

- [ ] Create `GET /dashboard/summary` in `main.py` that returns:
```json
{
  "detection": {
    "total_events": 1000,
    "at_risk": 662,
    "revenue_at_risk_paise": 6538889,
    "provenance": "simulated"
  },
  "real_execution": {
    "decision_engine": "deterministic_policy_gate",
    "llm_execution_authority": false,
    "scenarios_run": 6,
    "actions_taken": 2,
    "stopped": 2,
    "escalated": 2,
    "real_paise_recovered": 449800,
    "transactions": [ /* the 6 scenarios with decisions, for the live section + audit chain */ ]
  },
  "agent_evaluation": {
    "label": "Agent vs Deterministic Benchmark",
    "agent": {
      "candidate_decisions": 408,
      "successful_recoveries": 298,
      "recovered_paise": 2576773,
      "bad_interventions": 110,
      "net_recovered_paise": 2554773,
      "targeting_precision": 0.73
    },
    "benchmark": {
      "candidate_decisions": 662,
      "successful_recoveries": 438,
      "recovered_paise": 4288918,
      "bad_interventions": 224,
      "net_recovered_paise": 4244118,
      "targeting_precision": 0.662
    },
    "verdict": "benchmark_retained_for_execution",
    "verdict_text": "The recovery agent showed higher per-attempt targeting precision (73% vs 66%) but was more conservative economically. Under current evaluation economics, the deterministic benchmark is retained for real execution; the agent's reasoning is evaluated, not yet execution-authorized.",
    "provenance": "simulated"
  }
}
```
Note the field rename: `ai_experiment` → `agent_evaluation`, its internal `baseline`/`ai` keys → `benchmark`/`agent`. `real_execution` gets an explicit `decision_engine` and `llm_execution_authority: false` field — this is what powers the live-section provenance tag from the guardrail above.
- [ ] Parse from existing report files/tables, don't recompute
- [ ] Basic test confirming numbers match source reports exactly

## Step 3 — Frontend: Five Sections, Agent-First Order

**Section 1 — Hero: The Working System**
```
RECOVERAI
Agentic Payment Recovery

₹65.4L at risk · 1,000 transactions          SIMULATED
        ↓
Detect → Diagnose → Decide → Policy Gate → Act → Audit
```
Small, brief — this is context, not the headline. One line, no charts yet.

**Section 2 — Live Execution (the hero moment)**
```
LIVE EXECUTION                    REAL · Razorpay Test Mode
Decision engine: Deterministic Policy Gate
LLM execution authority: Not yet granted (see Agent Evaluation ↓)

6 scenarios │ 2 actions │ 2 stopped │ 2 escalated │ ₹4,498 recovered

✓ ACTION     ₹2,999   Payment Link created → Recovered
✓ ACTION     ₹1,499   Payment Link created → Recovered
⛔ STOP      —        Attempt limit reached · API call: NOT EXECUTED
⛔ STOP      —        Already recovered · API call: NOT EXECUTED
⚠ ESCALATE  ₹7,500   Above automated cap · API call: NOT EXECUTED
⚠ ESCALATE  ₹999     Low recoverability · API call: NOT EXECUTED
```
- [ ] For each row, show the decision-chain as a short sequence (reuse actual `audit_logs` timestamps), e.g.: `Detection → Policy evaluated → ACTION approved → Razorpay called → Link created → Recovered` for the two real recoveries, and `Detection → Policy evaluated → STOP → No API call → Audit logged` for the refusals
- [ ] The "API call: NOT EXECUTED" label on every STOP/ESCALATE row is small but important — it's the proof the gate prevents action, not just logs a decision after the fact

**Section 3 — Human Oversight (this is Section E from the original plan, now promoted, unchanged in function)**
```
ESCALATED
₹7,500 — Above automated recovery cap
[ APPROVE ]   [ DISMISS ]
```
On Approve: real payment link created live, row updates to show `✓ MERCHANT APPROVED → Payment Link Created → triggered_by: merchant_manual_approval`. On Dismiss: row updates to show the dismissal, audited, no Razorpay call.
- [ ] Backend/frontend work here is unchanged from the original Section E spec — only its position on the page moved up

**Section 4 — System Status (small, honest, easy to skim)**
```
● Razorpay Test Mode         Connected
● Policy Gate                 Active
● Audit Logging               Active
● LLM Execution Authority     Disabled — benchmark did not justify autonomous authority
```
- [ ] Small widget, a few lines, no chart needed — this is the single clearest place a judge can see the honest state of the system at a glance

**Section 5 — Agent Evaluation (the benchmark, demoted and renamed)**
```
AGENT EVALUATION                                    SIMULATED · Day 3
How do we know the agent's decisions are any good?

                Recovery Agent      Deterministic Benchmark
₹ Recovered     ₹25.6L              ₹42.9L
Precision       73%                 66%
Bad interventions  110              224

"The recovery agent showed higher per-attempt targeting precision but
was more conservative economically. Under current evaluation economics,
the deterministic benchmark is retained for real execution. This is a
deliberate engineering decision based on measured evidence, not a
limitation of the agent's reasoning."
```
- [ ] This section is the last thing on the page, visually smaller/quieter than Sections 1-3
- [ ] Keep the honest verdict text — don't let the reframing turn into spin. The agent didn't win the benchmark; say so plainly, just not as the headline.

## Step 4 — Build It

- [ ] Fastest stack that gets this done today — framework choice doesn't matter to judges, correct numbers and clean ordering do
- [ ] Build Section 2 (Live Execution) and Section 3 (Human Oversight) first — these are the actual proof points and the interactive moment. Section 1 (hero framing) and Section 4 (status widget) are quick once 2-3 exist. Section 5 (evaluation) last.
- [ ] No fake loading states, no placeholder data

---

## Definition of Done — Today

- [ ] `GET /dashboard/summary` returns real numbers with explicit provenance/decision-engine fields
- [ ] Page opens on the live execution proof, not the benchmark
- [ ] Every STOP/ESCALATE row explicitly states the Razorpay API call was not executed
- [ ] System Status widget honestly states LLM execution authority is disabled, and why
- [ ] Approve/Dismiss buttons are real — live payment link creation, live audit entries
- [ ] Agent Evaluation section is present, honest, and visually secondary — not hidden, not the headline
- [ ] A judge watching for 30-60 seconds understands: this is a working agentic system, bounded by a real policy gate, with human oversight and a rigorous (not favorable) self-evaluation

**Target end-of-day milestone:** *"I can open one page, lead with real proof the system works and stays bounded, click Approve on a live escalated case, and — only when asked how we know the agent's judgment is good — show the benchmark that answers that question honestly."* That ordering is the whole point of today's rework: the product comes first, the evidence for the product comes second.
