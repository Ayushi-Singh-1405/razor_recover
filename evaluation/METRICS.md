# Metrics

All numbers from the implemented system — benchmark reports in
`backend/reports/`, live Test Mode execution from the audit trail. No
projections, no invented figures. Provenance is labeled per block.

## 1. Detection benchmark — 1,000 synthetic events [SIMULATED]

Detector: `detect_at_risk.py`, observed signals only. Full report:
[baseline.md](baseline.md).

| Metric | Value |
|---|---:|
| Total events | 1,000 |
| At-risk events | 662 |
| Confusion matrix | TP 438 · FP 224 · TN 338 · FN 0 |
| Precision | 0.6616 |
| Recall | 1.0000 |
| F1 Score | 0.7964 |
| Total revenue analyzed | ₹9,824,112 |
| Revenue at risk | ₹6,538,889 (66.6%) |
| Ground-truth recoverable | 438 |

Sanity check: zero succeeded transactions flagged at-risk (PASS).

## 2. Agent vs deterministic benchmark — 662 decisions [SIMULATED]

Identical §20.7/§20.8 economics applied to both systems. Full report:
[agent_performance_result.md](agent_performance_result.md).

| System | Candidates | Recoveries | ₹ Recovered | Bad interventions | Net ₹ |
|---|---:|---:|---:|---:|---:|
| Deterministic benchmark | 662 | 438 | ₹42,88,918 | 224 | **₹42,44,118** |
| AI recovery agent | 408 | 298 | ₹25,76,773 | 110 | **₹25,54,773** |

Net ₹ uplift (agent - baseline): **-₹16,89,345** — reported as-is.

### Why the agent trails

- More precise per attempt: 73% targeting precision vs 66% (110 vs 224 bad
  interventions)
- But far more conservative: attempted recovery on only 408 of 662 events,
  leaving recoverable revenue untouched
- Verdict: the deterministic benchmark is retained for real execution; the
  agent's reasoning is evaluated, not yet execution-authorized

### Agent decision paths

| Path | Count | Share |
|---|---:|---:|
| ai_decision | 553 | 83.5% |
| pre_filtered | 94 | 14.2% |
| gated_override | 15 | 2.3% |

### Gated override reasons (infrastructure vs model quality)

| Reason | Count | Class |
|---|---:|---|
| llm_call_failed | 11 | Infrastructure/provider |
| low_confidence | 4 | Model quality |

### Targeting quality by action (agent)

| Action | On recoverable | On non-recoverable |
|---|---:|---:|
| recover_now | 126 | 15 |
| send_payment_link | 161 | 91 |
| wait_and_retry | 11 | 4 |

## 3. Live execution — Razorpay Test Mode [REAL]

Policy-gated run over 9 demo transactions (`execute_recovery.py` +
`agent_recommendations.py`), audited end to end.

| Measure | Value |
|---|---:|
| Scenarios executed | 9 |
| Payment links created | 6 |
| Actions stopped (hard stops) | 2 |
| Escalated to human review | 1+ |
| Webhook-confirmed recovered | ₹13,497 (3 transactions paid) |
| Merchant approvals | Audited with `triggered_by: merchant_manual_approval` |

## 4. LLM reliability — full run

| Measure | Value |
|---|---:|
| LLM calls | 662 |
| 429 rate-limit retries | handled with 2s/4s/8s backoff |
| Hard failures (gated to safe escalation) | 11 (1.7%) |
| Low-confidence overrides | 4 |
| Format robustness | free-router models vary; reasoning-fallback in provider |

## Sources

| Report | Path |
|---|---|
| Detection evaluation | [backend/reports/baseline.md](../backend/reports/baseline.md) |
| Benchmark simulation | [backend/reports/baseline_simulation.md](../backend/reports/baseline_simulation.md) |
| Agent performance | [backend/reports/agent_performance_result.md](../backend/reports/agent_performance_result.md) |
| Nemotron sample | [backend/reports/nemotron_15_event_sample.md](../backend/reports/nemotron_15_event_sample.md) |
| Dataset snapshots | [data/](data/) |
