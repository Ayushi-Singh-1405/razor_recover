# RecoverAI (razor_recover) — Architecture

> **Status legend used throughout this document**
>
> - **IMPLEMENTED** — present and functional in the repository today
> - **PARTIALLY IMPLEMENTED** — present but incomplete or wired to only part of the pipeline
> - **PLANNED** — design-stage / discussed; **no supporting code exists yet**
>
> Every claim below was verified against the source code on 2026-08-28. File paths are given for each component.

---

## 1. What RecoverAI Is

RecoverAI is an AI-powered payment failure and checkout recovery system built for the Razorpay buildathon.

**Core problem:** payment failures do not all mean the same thing. Some failed or abandoned checkouts are genuinely recoverable; others should never receive further automated intervention (exhausted attempts, high-value transactions requiring human review, customers with no viable payment path). Treating every failure identically either wastes interventions and annoys customers, or leaves recoverable revenue on the table.

**Core idea:** split the problem into three roles with deliberately different information sets:

1. A **deterministic baseline detector** that flags at-risk transactions using a *limited* observable signal set (the control system).
2. A **Recovery Agent** (LLM) that receives *richer, permitted* transaction/customer context, reasons about *why* the payment failed, and recommends a bounded recovery action.
3. A **deterministic Policy Gate** that has final authority over which recommended actions are actually allowed.

Because no real recovery outcomes exist in a buildathon setting, outcomes are produced by a **synthetic ground-truth policy** that is defined *before* either system runs, uses a *wider* signal set than either system sees, and is never exposed to either system at decision time. The primary evaluation is economic — **₹ recovered** — not classification accuracy.

### Conceptual pipeline

```
Detect → Diagnose → Decide → Policy Gate → Action → Outcome → Evaluation / Metrics
```

---

## 2. High-Level System Architecture

The repository contains **two coexisting subsystems sharing one PostgreSQL database and one config module**:

- **Subsystem A — Live Razorpay path (Phase 0).** A FastAPI service that creates Razorpay orders/payment links, receives signature-verified idempotent webhooks, and maintains an audit trail. (`backend/main.py`)
- **Subsystem B — Offline benchmark & agent pipeline (Phase 1–2).** Batch scripts that generate synthetic events, run the baseline detector, run the AI Recovery Agent through the policy gate, simulate outcomes, and evaluate. (`backend/generate_synthetic_data.py`, `detect_at_risk.py`, `run_agent.py`, `simulate_outcomes.py`, `evaluate.py`)

These two subsystems do **not** call each other. Subsystem A is the production-shaped integration path; Subsystem B is the controlled experiment that decides whether the AI layer earns its place. This is intentional: agent decisions are currently *recorded*, not executed against Razorpay.

```
┌─────────────────────────────────────────────────────────────────────┐
│                       HIGH-LEVEL SYSTEM ARCHITECTURE                │
└─────────────────────────────────────────────────────────────────────┘

   Subsystem A — Live Razorpay path (IMPLEMENTED)
┌───────────────────────────────────────────────────────┐
│  FastAPI (backend/main.py)                            │
│  /health · /transactions/create-test-order            │
│  /transactions/{id}/create-payment-link               │
│  /webhook (HMAC-verified, idempotent)                 │
│  /audit/{transaction_id}                              │
│          │           ▲                                │
│          ▼           │                                │
│  Razorpay SDK    Webhooks                             │
└──────────┼───────────┼────────────────────────────────┘
           ▼           │
   ┌───────────────────────────────┐
   │   PostgreSQL (Neon)           │
   │   transactions · webhook_     │
   │   events · audit_logs ·       │
   │   recovery_attempts (unused)  │
   └───────────────────────────────┘
           ▲
           │  (same DB, separate pipelines — no code coupling)
           │
   Subsystem B — Offline benchmark & agent pipeline (IMPLEMENTED)
┌───────────────────────────────────────────────────────┐
│  generate_synthetic_data.py   ── synthetic_events ──┐ │
│  detect_at_risk.py            ── detection_results  │ │
│  run_agent.py (LLM+policy)    ── agent_decisions    │ │
│  simulate_outcomes.py · evaluate.py ── reports/     │ │
│                                                     │ │
│  GROUND_TRUTH_POLICY.md  ← normative rules for B    │ │
└─────────────────────────────────────────────────────┴─┘
```

---

## 3. End-to-End Transaction / Event Flow (Subsystem B)

Every stage below is verified in code.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    END-TO-END EVENT LIFECYCLE                        │
└──────────────────────────────────────────────────────────────────────┘

 1 ┌────────────────────────────────────────────────┐
   │ Synthetic event generation                     │
   │ generate_synthetic_data.py --seed 42 --count N │
   │ • seeded RNG (reproducible; self-check regener │
   │   ates and compares before writing)            │
   │ • materializes transaction + customer +        │
   │   temporal + recovery-history fields           │
   │ • applies Ground-Truth Policy (§6) AT          │
   │   GENERATION TIME: tier → probability draw →   │
   │   ground_truth_recoverable / outcome / amount  │
   └───────────────────────┬────────────────────────┘
                           ▼
              synthetic_events table (1000 rows, seed 42)
                           │
 2 ┌───────────────────────▼────────────────────────┐
   │ Baseline detector (detect_at_risk.py)          │
   │ • reads ONLY: id, amount_paise, status,        │
   │   failure_reason, previous_recovery_attempts,  │
   │   previous_successful_payments                 │
   │ • 5 deterministic rules → at_risk /            │
   │   recoverability / risk_reason                 │
   └───────────────────────┬────────────────────────┘
                           ▼
              detection_results table (1:1 with events;
              ~662 at_risk=TRUE on the current dataset)
                           │
 3 ┌───────────────────────▼────────────────────────┐
   │ Eligibility gate (run_agent.py SQL)            │
   │ • only events with detection_results.at_risk   │
   │   = TRUE enter the agent                       │
   └───────────────────────┬────────────────────────┘
                           ▼
 4 ┌────────────────────────────────────────────────┐
   │ Recovery Agent (run_agent.py)                  │
   │ • context enrichment = SELECT of enriched      │
   │   columns already materialized in              │
   │   synthetic_events (no separate service)       │
   │ • prompt construction → LLM (llm_provider.py)  │
   │ • JSON schema validation                       │
   └───────────────────────┬────────────────────────┘
                           ▼
 5 ┌────────────────────────────────────────────────┐
   │ Policy Gate (deterministic, in run_agent.py)   │
   │ • pre-filters (before LLM)                     │
   │ • post-filters (after LLM)                     │
   │ • error fallback                               │
   └───────────────────────┬────────────────────────┘
                           ▼
 6 ┌────────────────────────────────────────────────┐
   │ Persistence: agent_decisions table             │
   │ (batched execute_values, 100 rows/commit)      │
   └───────────────────────┬────────────────────────┘
                           ▼
 7 ┌────────────────────────────────────────────────┐
   │ Outcome simulation (simulate_outcomes.py)      │
   │ IMPLEMENTED for baseline; agent wiring PLANNED │
   │ Rules §20.7/§20.8: success := gt_recoverable;  │
   │ ₹200 penalty per bad intervention              │
   └───────────────────────┬────────────────────────┘
                           ▼
 8 ┌────────────────────────────────────────────────┐
   │ Evaluation (evaluate.py + reports/)            │
   │ • classification: TP/FP/TN/FN, P/R/F1          │
   │ • business: candidates, recoveries, ₹ gross,   │
   │   bad interventions, ₹ net                     │
   │ • baseline-vs-AI comparison report: PLANNED    │
   └────────────────────────────────────────────────┘
```

### Stage notes

| Stage | Where | Notes |
|---|---|---|
| Generation | `backend/generate_synthetic_data.py` | `--seed` (default 42), `--count` (default 1000). Deletes and repopulates `synthetic_events` + `detection_results`. Batch inserts via `psycopg2.extras.execute_values`. Contains a built-in reproducibility self-check (generates twice, compares). |
| Detection | `backend/detect_at_risk.py` | Clears and repopulates `detection_results` 1:1 with events. Verifies row-count parity. |
| Eligibility | `backend/run_agent.py` (SQL JOIN) | `agent_decisions` only ever receives `at_risk = TRUE` events. |
| Agent + Policy | `backend/run_agent.py` | See §5. |
| Simulation | `backend/simulate_outcomes.py` | `simulate()` is decision-maker-agnostic (takes `(event, action)` pairs); `main()` currently wires **baseline only** (`at_risk → "recover_now"`, else `"no_action"`). |
| Evaluation | `backend/evaluate.py`, `backend/reports/` | Writes `day2_baseline.txt`, `day3_baseline_simulation.txt`. |

**Current dataset reference numbers** (from `backend/reports/`, seed 42, 1000 events): 662 at-risk, 438 ground-truth recoverable; baseline Precision 0.66 / Recall 1.00 / F1 0.80; baseline simulation net **₹4,244,118** (₹4,288,918 recovered − ₹44,800 penalties for 224 bad interventions). These are benchmark figures for the synthetic development dataset, not real-world Razorpay distribution claims.

---

## 4. Database Architecture

**Technology: PostgreSQL hosted on Neon** (verified: `DATABASE_URL` usage across all scripts; Neon-specific bulk-insert constraint documented in `docs/specifications/CHAT_SUMMARY_3.md` — SQLAlchemy `executemany` times out, so all batch scripts use `psycopg2.execute_values` with 100-row pages).

**Access layers:**

- **SQLAlchemy ORM** (`backend/db.py`, `backend/models.py`) — used by the FastAPI app and migration tooling. `create_engine(DATABASE_URL)`, `sessionmaker`, `DeclarativeBase`.
- **Raw psycopg2** — used by all batch pipeline scripts (`generate_synthetic_data.py`, `detect_at_risk.py`, `evaluate.py`, `simulate_outcomes.py`, `run_agent.py`) for bulk throughput.
- **Alembic migrations** (`backend/alembic/versions/`) — `001_initial_tables`, `002_add_synthetic_and_detection_tables`, `003_add_customer_behavior_columns`, `004_add_agent_decisions_table`.

**Configuration:** `DATABASE_URL` read from environment / `.env` via `backend/config.py` (`load_dotenv()`), never hardcoded. `.env` is gitignored; `.env.example` carries placeholder values.

### Tables (7 — verified in `backend/models.py` and migrations)

| Table | Purpose | Written by |
|---|---|---|
| `transactions` | Live Razorpay orders (order id, payment-link id, amount, status) | FastAPI app |
| `recovery_attempts` | Defined schema for recovery action tracking | **Defined but unused by any current code path** |
| `webhook_events` | Raw webhook payloads keyed by `X-Razorpay-Event-Id` (deduplication primary key) | FastAPI app |
| `audit_logs` | Human-readable audit trail (order_created, payment_link_created, webhook_verified, webhook_signature_rejected, revenue_recovered) | FastAPI app |
| `synthetic_events` | Synthetic benchmark events + **enriched context** + **ground-truth fields (evaluation-only)** | Generator |
| `detection_results` | Baseline detector output per event (1:1 FK) | Detector |
| `agent_decisions` | One decision per evaluated at-risk event (FK) | Agent runner |

### `synthetic_events` — the information-separation table

```
                    ┌────────────────────────────────┐
                    │       synthetic_events         │
                    ├────────────────────────────────┤
  LIMITED SET       │ id, amount_paise, status,      │◄── baseline detector
  (Phase 1)         │ failure_reason, customer_ref,  │    (SELECTs 6 cols)
                    │ previous_successful_payments,  │
                    │ previous_recovery_attempts,    │
                    │ created_at, raw_payload        │
                    ├────────────────────────────────┤
  ENRICHED SET      │ customer_tenure_days,          │◄── Recovery Agent
  (Phase 2,         │ previous_failed_payments,      │    (SELECTs enriched
   permitted)       │ average_order_value,           │     cols; NEVER selects
                    │ time_since_last_successful_    │     ground-truth cols)
                    │ payment_hours,                 │
                    │ time_since_last_recovery_      │
                    │ attempt_hours,                 │
                    │ checkout_duration_seconds,     │
                    │ payment_method                 │
                    ├────────────────────────────────┤
  EVALUATION-ONLY   │ ground_truth_recoverable,      │✖ NEVER shown to agent
  (ground truth)    │ ground_truth_outcome,          │✖ NEVER shown to detector
                    │ ground_truth_recovered_amount  │✓ read only by evaluation/
                    │                                │   simulation after decisions
                    └────────────────────────────────┘
```

### `agent_decisions` (verified, migration 004)

| Column | Type | Meaning |
|---|---|---|
| `id` | UUID PK | Decision id |
| `synthetic_event_id` | UUID FK → `synthetic_events.id` | Evaluated event |
| `diagnosis` | String | Root-cause diagnosis (or pre-filter tag like `pre_filtered_high_value`) |
| `recovery_probability` | Float | Model-estimated recovery probability |
| `recommended_action` | String | One of the 5 permitted actions |
| `reason` | Text | Free-text reasoning |
| `confidence` | Float | Decision-maker confidence 0.0–1.0 |
| `decision_path` | String | `ai_decision` / `pre_filtered` / `gated_override` |
| `override_reason` | String, nullable | e.g. `attempts_exhausted`, `high_value_requires_human_review`, `low_confidence`, `invalid_action_returned`, `llm_call_failed` |
| `created_at` | timestamptz | Decision timestamp |

### ER-style view

```
synthetic_events 1 ──── 1 detection_results
        │
        └──────── 1..N agent_decisions

transactions 1 ──── N recovery_attempts   (FK defined, table unused)
transactions 1 ──── N audit_logs          (transaction_id nullable)
webhook_events (standalone, PK = provider event id)
```

No secondary indexes beyond PKs/FKs are declared; table sizes are small (≤ a few thousand rows) and queries are full scans by design.

**Repeatable experiments:** identical `--seed` ⇒ identical dataset (generator has a built-in double-generation check); ground truth is computed once at generation time and never re-rolled at simulation time (policy §20.7); each pipeline stage clears and rebuilds its own table so any stage can be re-run in isolation.

---

## 5. Recovery Agent — Detailed Pipeline

Implemented in `backend/run_agent.py` (~400 lines) + `backend/llm_provider.py`.

```
┌──────────────────────────────────────────────────────────────────────┐
│                     RECOVERY AGENT PIPELINE                          │
└──────────────────────────────────────────────────────────────────────┘

 (1) Input event
     SQL: synthetic_events JOIN detection_results WHERE at_risk = TRUE
     ORDER BY created_at ASC      [optional --limit N slices this list]
          │
 (2) Context enrichment
     SELECT pulls the enriched column set already materialized in
     synthetic_events (tenure, failed-payment count, AOV, recency
     signals, checkout duration, payment method)
          │
 (3) Policy Gate — PRE-FILTERS (deterministic, before any LLM call)
     ├─ previous_recovery_attempts >= 3 → stop          [attempts_exhausted]
     └─ amount_paise > 1_800_000 (₹18,000) → escalate   [high_value_…]
          │ (else)
 (4) Prompt construction (build_event_prompt)
     • Transaction: amount, status, failure_reason, method, checkout dur
     • Customer: tenure, prev success/failed, AOV, time-since-last-success
     • Recovery history: prior attempts, time-since-last-attempt
     • 5 permitted actions + when to use each
     • NO ground-truth fields anywhere in the prompt
          │
 (5) LLM invocation (llm_provider.get_structured_decision)
     • OpenRouter chat-completions API, temperature 0.1, timeout 30 s
     • response_format json_object; JSON schema embedded in system msg
          │
 (6) Structured response + validation
     • strip markdown fences → json.loads → custom recursive schema
       validator (required keys, types, enum membership)
          │
 (7) Policy Gate — POST-FILTERS (deterministic, after LLM)
     ├─ invalid action value  → escalate_to_merchant [invalid_action_returned]
     └─ confidence < 0.5      → escalate_to_merchant [low_confidence]
          │
 (8) Persistence → agent_decisions (batched, 100 rows/commit,
     row-count verified against evaluated events)
          │
 (9) Run summary printed: decision-path breakdown, override reasons,
     final action distribution
```

### 5.1 What the agent can / cannot see

**Can see (verified — the exact SELECT in `run_agent.py`):** `id`, `amount_paise`, `status`, `failure_reason`, `customer_ref`, `previous_successful_payments`, `previous_recovery_attempts`, `created_at`, `customer_tenure_days`, `previous_failed_payments`, `average_order_value`, `time_since_last_successful_payment_hours`, `time_since_last_recovery_attempt_hours`, `checkout_duration_seconds`, `payment_method`.

**Cannot see (never selected, never prompted):** `ground_truth_recoverable`, `ground_truth_outcome`, `ground_truth_recovered_amount`, detection results beyond the at-risk flag, any evaluation metric.

**Why enriched context matters:** failure_reason alone is a weak prior — a `network_error` on a 13-day-old customer with zero successes is a different business problem than the same failure on a 215-day-old customer with 9 past successes (see §10 evaluation discussion; in the 15-event development sample the agent's reasoning cited checkout duration, AOV deviation, and attempt history in every AI-decision case, not just failure_reason).

**Decision space (verified — `DECISION_SCHEMA` enum and `ALLOWED_ACTIONS`):**

| Action | Meaning | Counts as "attempted recovery" in simulation |
|---|---|---|
| `recover_now` | Urgent recovery payment link | Yes |
| `send_payment_link` | Standard recovery payment link | Yes |
| `wait_and_retry` | Cooldown then re-attempt | Yes (in `RECOVERY_ACTIONS`), but **no cooldown/scheduling logic is implemented** — the action exists only in the decision space and simulation accounting |
| `escalate_to_merchant` | Human review | No |
| `stop` | Cease recovery | No |

### 5.2 Policy Gate — full rule set (verified in code)

**The LLM recommends; the policy layer decides.** All gates are plain deterministic Python — no model output can bypass them.

| # | Gate | Rule | Outcome | `override_reason` |
|---|---|---|---|---|
| 0a | Eligibility | Event must be `at_risk = TRUE` (detector) | Enters pipeline or excluded | — |
| 0b | Pre-filter | `previous_recovery_attempts >= 3` | `stop`, LLM never called | `attempts_exhausted` |
| 0c | Pre-filter | `amount_paise > 1_800_000` (> ₹18,000) | `escalate_to_merchant`, LLM never called | `high_value_requires_human_review` |
| 0d | Post-filter | `recommended_action` not in allowed enum | `escalate_to_merchant` | `invalid_action_returned` |
| 0e | Post-filter | `confidence < 0.5` | `escalate_to_merchant` | `low_confidence` |
| 0f | Error fallback | LLM/API/parse/schema failure | `escalate_to_merchant` | `llm_call_failed` |

Design stance: **AI = reasoning, Policy = authority, Execution = controlled** (currently, "execution" is persistence + offline simulation; live execution through Razorpay is PLANNED, see §12).

### 5.3 LLM provider architecture

**IMPLEMENTED — single provider (OpenRouter), provider-agnostic at the call boundary:**

- `backend/llm_provider.py` exposes one function, `get_structured_decision(prompt, schema)`. The agent knows nothing about HTTP, models, or providers.
- Model is configuration, not code: `OPENROUTER_MODEL` env var (code default `google/gemini-2.0-flash-001`; the recent dry run used `nvidia/nemotron-3-super-120b-a12b:free` **served through OpenRouter** — i.e. a model swap via env var, *not* a second provider integration).
- Request: `POST https://openrouter.ai/api/v1/chat/completions`, `temperature=0.1`, `timeout=30 s`, `response_format={"type":"json_object"}`, JSON schema embedded in the system message with strict "JSON only, no fences" instructions.
- Response handling: markdown-fence stripping (`_clean_json_text`) → `json.loads` → **custom recursive JSON-schema validator** (`required` keys, `string`/`number`/`integer`/`boolean`/`array`/`object` types, `enum` membership; bool-excluded-from-number check). No external validation dependency.
- Error taxonomy (all subclasses of `LLMProviderError`): `LLMAPIError` (missing key, network, timeout, non-200), `LLMJSONDecodeError` (unparseable output), `LLMSchemaValidationError` (schema violation).

**PLANNED — AgentRouter / multi-provider resilience.** A resilient provider layer (PRIMARY: NVIDIA model via AgentRouter → FALLBACK: OpenRouter on provider/model failure) is **design-stage only**. **No AgentRouter code, configuration, or provider-abstraction dispatch exists in the repository** (verified by repo-wide search). The current `llm_provider.py` is OpenRouter-only with **no retry and no cross-provider fallback**. The intended target shape:

```
        PLANNED — NOT YET IMPLEMENTED

   Recovery Agent
        │  (provider-agnostic interface — get_structured_decision)
        ▼
   LLM Provider Interface  ◄── to be extracted from llm_provider.py
        │
        ├────────────────────────────┐
        ▼                            ▼
 ┌──────────────┐  failure   ┌──────────────┐
 │ AgentRouter  │ ─────────► │ OpenRouter   │
 │ PRIMARY      │  fallback  │ FALLBACK     │
 │ NVIDIA model │            │ (IMPLEMENTED │
 └──────────────┘            │  as the only │
                             │  provider)   │
                             └──────────────┘
```

> **Important distinction — two different "fallbacks":**
>
> 1. **Provider fallback** (LLM provider → different LLM provider): **PLANNED, not implemented.**
> 2. **Policy/safety fallback** (LLM failure → deterministic `escalate_to_merchant` decision): **IMPLEMENTED** in `run_agent.py`. The pipeline never crashes on LLM failure; it degrades to the safest action and records why.

---

## 6. Ground Truth vs Baseline vs AI — Information Separation

This is the architectural core of the project. Normative rules: `backend/GROUND_TRUTH_POLICY.md` (§1–§20, incl. numeric appendix).

```
┌───────────────────────────────────────────────────────────────────────┐
│              GROUND TRUTH vs BASELINE vs AI SEPARATION                │
└───────────────────────────────────────────────────────────────────────┘

                 ┌──────────────────────┐
                 │    Ground Truth      │
                 │   richer signals:    │
                 │  txn + customer +    │
                 │  temporal + recovery │
                 │  + outcome model     │
                 │  (HIGH .85 / MED .50 │
                 │   / LOW .15 / NONE 0)│
                 └──────────┬───────────┘
                            ▼
                 hidden synthetic outcome
                 (ground_truth_recoverable,
                  outcome, recovered_amount)
                            │
                            │  evaluation only — never
                            │  visible to either system
                            │
┌──────────────────┐        │        ┌──────────────────┐
│ Baseline         │        │        │ Recovery Agent   │
│ DETECTOR         │        │        │ (LLM)            │
│ limited signals: │        │        │ enriched context:│
│ status, failure_ │        │        │ + tenure, failed │
│ reason, attempts,│        │        │ count, AOV,      │
│ (succ payments)  │        │        │ recency, checkout│
│                  │        │        │ duration, method │
└────────┬─────────┘        │        └────────┬─────────┘
         │                  │                 │
         └──────────────┬───┴─────────────────┘
                        ▼
              same fixed simulation rules (§20.7)
                        ▼
              compare decisions vs outcomes
                        ▼
              ₹ recovered / bad interventions / uplift
```

**How separation is mechanically enforced (verified):**

1. **Generation time:** ground truth is computed inside `generate_synthetic_data.py` from the *full* enriched signal set (baseline tiers per failure reason → engagement-signal scoring → tier adjustment → seeded probability draw per §20.1), *before* any system runs. No re-roll at simulation time.
2. **Detector boundary (§10 of policy):** `detect_at_risk.py` SELECTs only the limited column set; `classify()` uses `status`, `previous_recovery_attempts`, `failure_reason`. It cannot see tenure, AOV, recency, or checkout duration.
3. **Agent boundary (§11 of policy):** `run_agent.py` SELECTs the enriched set but **never selects any `ground_truth_*` column**; `build_event_prompt()` cannot include them by construction.
4. **Evaluation reads ground truth only after decisions are persisted.**

**Why this prevents circular evaluation:** if the ground-truth policy were computed from the detector's output (or the agent could see it), the benchmark would be grading systems against a definition derived from their own behavior — any "improvement" would be tautological. Because ground truth is (a) generated from a strictly wider signal set, (b) fixed before decisions, (c) probability-based rather than hard-cut, and (d) protected by a policy-integrity rule (§19: no post-hoc tuning without versioning and re-running both systems), the comparison between baseline and AI is a genuine experiment: **same events → two information sets → same simulation → same outcome definition → ₹ comparison.**

---

## 7. Failure Handling

Verified behavior in `backend/run_agent.py` + `backend/llm_provider.py`:

| Failure | Detected by | Handling | Recorded as |
|---|---|---|---|
| Missing API key | `llm_provider` pre-flight | `LLMAPIError` → agent catches | `gated_override` / `llm_call_failed` |
| Network error / timeout (30 s) | `requests` exceptions | `LLMAPIError` → agent catches | `gated_override` / `llm_call_failed` |
| HTTP non-200 (incl. provider errors, parsed from body) | status check | `LLMAPIError` → agent catches | `gated_override` / `llm_call_failed` |
| Empty/malformed wrapper JSON | response parse | `LLMAPIError` → agent catches | `gated_override` / `llm_call_failed` |
| **Malformed / truncated LLM JSON** (fences, missing brace) | `json.loads` after fence-stripping | `LLMJSONDecodeError` → agent catches | `gated_override` / `llm_call_failed` |
| Schema violation (missing key, wrong type, bad enum) | custom validator | `LLMSchemaValidationError` → agent catches | `gated_override` / `llm_call_failed` |
| Invalid action value in otherwise-valid JSON | post-filter | override, LLM reason preserved in `reason` | `gated_override` / `invalid_action_returned` |
| Confidence < 0.5 | post-filter | override, original recommendation preserved in `reason` | `gated_override` / `low_confidence` |
| Row-count mismatch after insert | runner verification | `RuntimeError` — run aborts loudly | — |

**Observed real case (development, 15-event run):** the model returned a logically sound recommendation but truncated JSON (missing closing brace). Parsing failed → the event was recorded as `gated_override` / `llm_call_failed` → fell back to `escalate_to_merchant` → a recoverable transaction was missed. This is **by-design current behavior** and is a known cost of the benchmark (see §10: LLM failure rate is a tracked metric). There is **no retry** at either the HTTP or parse level today.

**Failure-handling gaps (current state):** no retry/backoff, no provider-level fallback (§5.3), no partial-run checkpointing (a crash mid-run leaves a partial `agent_decisions` table; the runner clears and rebuilds on next run).

**Subsystem A failure handling (live path):** webhook signature failure → audit entry + HTTP 401; duplicate event id → deduplicated (no-op); DB errors → rollback + 500 / logged; Razorpay SDK errors → 502.

---

## 8. Security & Configuration

**IMPLEMENTED:**

- All secrets are environment variables read in `backend/config.py` / `backend/llm_provider.py` via `python-dotenv` — nothing hardcoded.
- `.env` is gitignored (verified in `.gitignore`); `.env.example` (committed) contains placeholder values only.
- **Environment variables that actually exist:** `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `DATABASE_URL`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
- Webhook authenticity enforced via HMAC signature verification before any processing; event ids from the `X-Razorpay-Event-Id` header are used as primary keys for idempotency.
- Provider credentials are configuration, not application logic — swapping models/providers requires env changes, not code changes (subject to the PLANNED abstraction in §5.3).

No secrets appear in the repository. No real API keys are documented anywhere in this file.

---

## 9. Observability

**IMPLEMENTED (modest, console/file-based):**

- Python `logging` in the agent runner (`logger.warning` per LLM failure, includes event id and error text) and FastAPI (`logger.error` on webhook processing errors).
- Printed run summaries: per-stage progress, decision-path breakdown, override-reason counts, final action distribution.
- **Persisted decision telemetry** in `agent_decisions`: per event — `decision_path`, `override_reason`, `recommended_action`, `recovery_probability`, `confidence`, `reason`, `created_at` (timestamp). Event linkage via `synthetic_event_id`.
- Audit trail on the live path (`audit_logs` table + `/audit/{id}` endpoint with console formatting).
- Text reports under `backend/reports/`.

**Fields currently NOT logged per LLM call:** provider name, model id, latency, token usage, prompt/response snapshots. (Model is only indirectly observable via `OPENROUTER_MODEL` config.)

**PLANNED / not present (verified absent):** Langfuse, Prometheus, Grafana, structured JSON logging, tracing, cost tracking. Nothing beyond stdlib logging exists in the repo.

---

## 10. Evaluation Architecture

### Decision quality vs business recovery value

Classification metrics (Precision/Recall/F1) measure *detection* quality and are computed by `evaluate.py` for the baseline. They are explicitly **not** the success criterion for the AI layer: an agent could post a great F1 while recovering less money or annoying more customers. The north-star metric is **net ₹ recovered**, computed by the fixed simulation rules:

```
simulated_intervention_succeeds := ground_truth_recoverable == True     (§20.7)
recovered_amount                := amount_paise (if success) else 0
bad_intervention                := attempt-recovery action taken on a
                                   ground-truth non-recoverable event
net_₹_recovered = Σ recovered_amount − bad_interventions × ₹200        (§20.8)
```

Attempt-recovery actions = `{recover_now, send_payment_link, wait_and_retry}`; `stop` / `escalate_to_merchant` / no-action are excluded from success/failure accounting entirely (neither a recovery nor a bad intervention).

### Metrics

| Metric | Source | Status |
|---|---|---|
| Recoverable events (ground truth) | `synthetic_events.ground_truth_recoverable` | ✅ IMPLEMENTED |
| Detection TP/FP/TN/FN, Precision, Recall, F1 | `evaluate.py` | ✅ IMPLEMENTED |
| Successful recoveries, candidate decisions | `simulate_outcomes.py` | ✅ IMPLEMENTED (baseline wiring) |
| Gross recovered ₹ / bad interventions / penalties / net ₹ | `simulate_outcomes.py` (§20.7/§20.8) | ✅ IMPLEMENTED (baseline wiring) |
| Recovery uplift vs baseline (Δ net ₹) | comparison report | 🔵 PLANNED (comparison report not yet written; `simulate()` already accepts any decision-maker's action pairs) |
| Missed recoverable events (recoverable but not attempted) | derivable from `agent_decisions` + ground truth | 🟡 derivable; no dedicated report |
| LLM failure rate | `agent_decisions.decision_path='gated_override' AND override_reason='llm_call_failed'` | 🟡 persisted; no aggregate report |
| Provider fallback rate | — | ❌ N/A until provider fallback exists (§5.3) |
| Policy override rate (`pre_filtered`, `gated_override` breakdown) | `agent_decisions.decision_path` / `override_reason` | 🟡 persisted + printed per run; no aggregate report |
| AI decision alignment vs ground truth | offline analysis (as done for dev samples) | 🟡 manual; no automated report |

### Sample-size discipline

The **5-event and 15-event agent runs are development/evaluation samples only** (the latter documented in `tests/gate_b_dry_run_5.md`). The full benchmark contains **~662 at-risk events**; no sample-run result in this document or the repo constitutes project-wide performance. The full run is `python backend/run_agent.py` (no `--limit`), and the baseline-vs-AI verdict report (`backend/reports/day3_experiment_result.md`) is **PLANNED but not yet written**.

---

## 11. Technology Stack

Based **only** on technologies present in the repository.

| Layer | Technology | Purpose | Status |
|---|---|---|---|
| Backend | Python 3 | All pipeline + service code | ✅ IMPLEMENTED |
| API | FastAPI + Pydantic | Live transaction/webhook/audit endpoints | ✅ IMPLEMENTED |
| Server | uvicorn | ASGI server | ✅ IMPLEMENTED |
| Payments | Razorpay Python SDK | Orders, payment links, webhook signature verification | ✅ IMPLEMENTED |
| Database | PostgreSQL (Neon) | All persistent state | ✅ IMPLEMENTED |
| DB access (API) | SQLAlchemy 2 (ORM, `DeclarativeBase`) | Models + session management | ✅ IMPLEMENTED |
| DB access (batch) | psycopg2 + `execute_values` | Bulk inserts (Neon-safe, 100-row pages) | ✅ IMPLEMENTED |
| Migrations | Alembic (4 revisions) | Schema evolution | ✅ IMPLEMENTED |
| LLM | OpenRouter chat-completions API (`requests`) | Structured recovery decisions | ✅ IMPLEMENTED |
| LLM providers | OpenRouter (current); AgentRouter + multi-provider dispatch | Provider resilience | 🔵 PLANNED (no code) |
| Structured output | JSON schema in system prompt + custom recursive validator | Contract enforcement on model output | ✅ IMPLEMENTED |
| Config | python-dotenv + environment variables | Secrets & provider config | ✅ IMPLEMENTED |
| Testing | `tests/test_phase0.py` (requests + DB asserts) | Phase 0 smoke tests | ✅ IMPLEMENTED |
| Agent orchestration | Single-process batch runner (`run_agent.py`) with `--limit` dry-run support | Agent execution | ✅ IMPLEMENTED |
| Frontend | — | Dashboard | ❌ NOT PRESENT (empty `frontend/` dir) |
| Observability platforms | — | Langfuse/Prometheus/Grafana etc. | ❌ NOT PRESENT (PLANNED concept only) |
| Deployment | — | Hosting/packaging | ❌ NOT PRESENT |

---

## 12. Architectural Trade-offs

- **Why AI at all, given a working deterministic baseline?** The baseline's rules are fixed to a handful of observable fields; recoverability actually depends on contextual judgment (AOV deviation, hesitation signals, recency, attempt history) that resists clean rule encoding. The experiment is designed so the AI must *earn* its place in net ₹ — otherwise the deterministic strategy stays.
- **Why keep a deterministic Policy Gate in front of the LLM?** LLMs are probabilistic and can produce invalid actions, unwarranted confidence, or hallucinated reasoning. Hard business constraints (attempt limits, high-value human review, action whitelist, minimum confidence) must be enforced by code that cannot be argued with. The gate also makes failure deterministic: any LLM malfunction degrades to `escalate_to_merchant`, never to an unsafe automated action.
- **Why separate ground truth from both systems?** Circularity (§6): ground truth derived from a system's own inputs would make evaluation tautological. Wider-signal, pre-registered, probability-based ground truth + a written integrity rule (§19) is what makes the ₹ comparison meaningful.
- **Why synthetic data?** Real failed-payment recovery outcomes with known ground truth don't exist at hackathon scale (and privacy rules would forbid it). A seeded generator gives a controlled, reproducible, recovery-heavy benchmark (~45–50% recoverable by design, documented honestly as non-representative).
- **Why provider abstraction?** Free/cheap models change frequently; provider outages are inevitable. Config-driven model selection already exists; the planned AgentRouter/primary-fallback layer keeps vendor lock-in out of the agent's decision logic. Provider failures degrade safely today via the policy fallback.
- **Why ₹ recovered over raw accuracy?** The business question is revenue: recovering ₹X with Y bad interventions beats a high-F1 detector that recovers less net. The ₹200 flat penalty makes "spray links everywhere" strategies unprofitable, forcing selective recovery.
- **Why structured LLM output + validation?** Free-text replies can't be persisted, gated, simulated, or audited reliably. A JSON contract validated against a schema turns model output into data; the custom validator (no extra dependency) catches malformed output deterministically — as demonstrated by the caught truncation failure in the dev run.
- **Why persist `decision_path` and `override_reason`?** They separate *what the AI thought* from *what the system allowed* — the audit story ("why did this customer get no recovery attempt?") is answerable from the database alone, and override rates become measurable rather than anecdotal.

### Design principles — implementation status

| Principle | Status |
|---|---|
| 1. AI reasoning separated from policy enforcement | ✅ IMPLEMENTED (LLM proposes; `check_pre_filter`/`apply_post_filter` dispose) |
| 2. Ground truth isolated from agent inputs | ✅ IMPLEMENTED (never selected/prompted; verified) |
| 3. Baseline and AI use intentionally different information sets | ✅ IMPLEMENTED (different SELECT column sets, same table) |
| 4. Recovery decisions structured and auditable | ✅ IMPLEMENTED (`agent_decisions` schema) |
| 5. Provider abstraction prevents vendor lock-in | 🟡 PARTIAL (single module boundary exists; one provider only; dispatch layer PLANNED) |
| 6. Provider failures must not crash the pipeline | ✅ IMPLEMENTED (per-event catch → safe fallback) |
| 7. Safety rules remain deterministic | ✅ IMPLEMENTED (all gates are pure Python) |
| 8. Evaluation focuses on economic recovery value | ✅ IMPLEMENTED for simulation rules (§20.7/§20.8); AI-side comparison report 🔵 PLANNED |
| 9. Synthetic data enables controlled experimentation | ✅ IMPLEMENTED (seeded generator + policy) |
| 10. Decisions reproducible and inspectable | ✅ IMPLEMENTED (seed, fixed prompt/context, persisted decisions; LLM output itself is non-deterministic at temperature 0.1 — noted honestly) |

---

## 13. Implementation Status

| Component | Status | Evidence / Notes |
|---|---|---|
| Synthetic event generation | ✅ Implemented | `generate_synthetic_data.py`; seeded, self-checked, batched; `--seed/--count` |
| Baseline detector | ✅ Implemented | `detect_at_risk.py`; 5 rules; limited 6-column input |
| Ground truth policy | ✅ Implemented | `GROUND_TRUTH_POLICY.md` §1–20; encoded in generator; probability draw at generation time |
| Context enrichment | 🟡 Partially implemented | Enriched columns materialized in `synthetic_events` at generation time and read by the agent; no separate enrichment stage/service exists |
| Recovery Agent | ✅ Implemented | `run_agent.py`; full loop incl. `--limit` dry runs; decision-making only (no execution) |
| Structured LLM output | ✅ Implemented | `llm_provider.py`; schema-in-prompt + custom validator; error taxonomy |
| Policy Gate | 🟡 Partially implemented | Fully functional pre/post/error gates in `run_agent.py`, but not a standalone reusable module, and not connected to any execution layer |
| Agent decision persistence | ✅ Implemented | `agent_decisions` (migration 004); batched inserts; count verification |
| Evaluation pipeline | 🟡 Partially implemented | `evaluate.py` (classification) + `simulate_outcomes.py` (₹, baseline wiring) done; AI-side simulation run, comparison table, uplift report 🔵 PLANNED |
| OpenRouter integration | ✅ Implemented | `llm_provider.py`; model via `OPENROUTER_MODEL` (recent runs: NVIDIA `nemotron-3-super-120b-a12b:free` served **through** OpenRouter) |
| AgentRouter integration | 🔵 Planned | Zero code/config in repo (verified by search) |
| Provider fallback (AgentRouter→OpenRouter) | 🔵 Planned | Only the per-event *safety* fallback (`llm_call_failed` → escalate) exists — a different mechanism (§5.3) |
| Metrics | 🟡 Partially implemented | Classification + business metrics computed for baseline; decision-path/override/LLM-failure data persisted but not aggregated; uplift/failed-recovery reports PLANNED |
| Recovery execution (Razorpay link sending from decisions) | 🔵 Planned | `execute_recovery.py` implements the policy gates + audit trail and creates real payment links when `LIVE_EXECUTION_ENABLED=true`; execution policy in `EXECUTION_POLICY.md`, config in `execution_config.py` |
| Google OAuth merchant login | ✅ Implemented | `auth.py` + `merchants` table (migration 006): `/auth/google/login`, `/auth/google/callback`, `/auth/me`, `/auth/logout`; HS256 JWT session in httpOnly `recoverai_session` cookie (24h) via `JWT_SECRET`; `get_current_merchant` dependency returns 401 without a valid session |
| Frontend / deployment / tracing | ❌ Not present | Empty dirs; no code |

### Protected-route rule (auth dependency pattern)

Every dashboard and escalation-action route built from here on **must** take the
`get_current_merchant` dependency from `backend/auth.py` so it returns 401
without a valid session:

```python
from auth import get_current_merchant

@router.get("/dashboard/summary")
def dashboard_summary(merchant: Merchant = Depends(get_current_merchant)): ...

@router.post("/dashboard/escalations/{escalation_id}/approve")
def approve_escalation(escalation_id: str,
                       merchant: Merchant = Depends(get_current_merchant)): ...

@router.post("/dashboard/escalations/{escalation_id}/dismiss")
def dismiss_escalation(escalation_id: str,
                       merchant: Merchant = Depends(get_current_merchant)): ...
```

Planned protected routes: `GET /dashboard/summary`,
`POST /dashboard/escalations/{id}/approve`, `POST /dashboard/escalations/{id}/dismiss`.

---

## Appendix A — Agent decision record (example shape)

```json
{
  "id": "3c49a01f-…",
  "synthetic_event_id": "d7d8911c-…",
  "diagnosis": "OTP timeout after 118s; transient, not a decline …",
  "recovery_probability": 0.62,
  "recommended_action": "recover_now",
  "reason": "otp_timeout is transient; short checkout and OTP engagement indicate intent …",
  "confidence": 0.71,
  "decision_path": "ai_decision",
  "override_reason": null,
  "created_at": "2026-08-28T15:27:00+00:00"
}
```

## Appendix B — Repository map

```
razor_recover/
├── backend/
│   ├── main.py                     FastAPI app (live Razorpay path)
│   ├── config.py                   env config + Razorpay client
│   ├── db.py / models.py           SQLAlchemy engine + 7 ORM models
│   ├── alembic/                    migrations 001–004
│   ├── generate_synthetic_data.py  seeded events + ground truth
│   ├── detect_at_risk.py           baseline detector (limited signals)
│   ├── run_agent.py                agent runner + policy gates + --limit
│   ├── llm_provider.py             OpenRouter structured-decision client
│   ├── simulate_outcomes.py        §20.7/§20.8 simulation (baseline wiring)
│   ├── evaluate.py                 classification + revenue report
│   ├── GROUND_TRUTH_POLICY.md      normative benchmark policy
│   └── reports/                    day2_baseline.txt, day3_baseline_simulation.txt
├── docs/                           this file; specs, workflow, decisions
├── tests/                          test_phase0.py, gate_b_dry_run_5.md
├── frontend/ demo/ pitch/          empty (planned)
└── .env.example                    placeholder configuration template
```
