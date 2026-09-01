$ ./venv/bin/python - <<'EOF'
import os
from dotenv import load_dotenv
load_dotenv(".env")
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("SELECT count(*) AS n FROM agent_decisions")
print(f"agent_decisions row count: {cur.fetchone()['n']}\n")

query = """
    SELECT
        ad.id AS decision_id,
        ad.synthetic_event_id,
        ad.diagnosis,
        ad.recovery_probability,
        ad.recommended_action,
        ad.reason,
        ad.confidence,
        ad.decision_path,
        ad.override_reason,
        ad.created_at AS decided_at,
        se.amount_paise, se.status, se.failure_reason, se.customer_ref,
        se.previous_recovery_attempts,
        se.customer_tenure_days, se.previous_successful_payments,
        se.previous_failed_payments, se.average_order_value,
        se.time_since_last_successful_payment_hours,
        se.time_since_last_recovery_attempt_hours,
        se.checkout_duration_seconds, se.payment_method,
        dr.at_risk, dr.risk_reason, dr.recoverability AS detector_recoverability,
        se.ground_truth_recoverable, se.ground_truth_outcome
    FROM agent_decisions ad
    JOIN synthetic_events se ON se.id = ad.synthetic_event_id
    JOIN detection_results dr ON dr.synthetic_event_id = se.id
    ORDER BY se.created_at ASC
"""

cur.execute(query)
rows = cur.fetchall()
cur.close(); conn.close()

for i, r in enumerate(rows, 1):
    rupees = r["amount_paise"] / 100.0
    aov = r["average_order_value"]
    aov_str = f"₹{aov/100:,.2f}" if aov else "N/A"
    tls = r["time_since_last_successful_payment_hours"]
    tlr = r["time_since_last_recovery_attempt_hours"]
    print("=" * 70)
    print(f"EVENT {i} of {len(rows)}")
    print("=" * 70)
    print(f"decision_id              : {r['decision_id']}")
    print(f"synthetic_event_id       : {r['synthetic_event_id']}")
    print(f"customer_ref             : {r['customer_ref']}")
    print()
    print("--- Context used by the agent ---")
    print(f"amount                   : ₹{rupees:,.2f} ({r['amount_paise']} paise)")
    print(f"status                   : {r['status']}")
    print(f"failure_reason           : {r['failure_reason']}")
    print(f"payment_method           : {r['payment_method']}")
    print(f"checkout_duration        : {r['checkout_duration_seconds']}s")
    print(f"customer_tenure          : {r['customer_tenure_days']} days")
    print(f"prev successful payments : {r['previous_successful_payments']}")
    print(f"prev failed payments     : {r['previous_failed_payments']}")
    print(f"avg order value          : {aov_str}")
    print(f"time since last success  : {tls if tls is not None else 'No prior success recorded'}")
    print(f"prev recovery attempts   : {r['previous_recovery_attempts']}")
    print(f"time since last attempt  : {tlr if tlr is not None else 'No prior recovery attempt'}")
    print()
    print("--- Detector (Phase 1, eligibility gate) ---")
    print(f"at_risk                  : {r['at_risk']}")
    print(f"risk_reason              : {r['risk_reason']}")
    print(f"detector recoverability  : {r['detector_recoverability']}")
    print()
    print("--- Decision ---")
    print(f"decision_path            : {r['decision_path']}")
    print(f"override_reason          : {r['override_reason']}")
    print(f"diagnosis                : {r['diagnosis']}")
    print(f"recommended_action       : {r['recommended_action']}")
    print(f"recovery_probability     : {r['recovery_probability']}")
    print(f"confidence               : {r['confidence']}")
    print(f"reason                   : {r['reason']}")
    print()
    print("--- Ground truth (NOT shown to the agent; reference only) ---")
    print(f"gt_recoverable           : {r['ground_truth_recoverable']}")
    print(f"gt_outcome               : {r['ground_truth_outcome']}")
    print()
EOF

agent_decisions row count: 5

======================================================================
EVENT 1 of 5
======================================================================
decision_id              : c16260ca-1478-47db-a62a-216f12af3c24
synthetic_event_id       : 55f5b0d7-f040-4elf-b647-9cd13839f3f2
customer_ref             : cust_b7e681634ff5511b

--- Context used by the agent ---
amount                   : ₹2,564.31 (256431 paise)
status                   : failed
failure_reason           : network_error
payment_method           : upi
checkout_duration        : 148s
customer_tenure          : 13 days
prev successful payments : 0
prev failed payments     : 1
avg order value          : ₹2,378.93
time since last success  : No prior success recorded
prev recovery attempts   : 0
time since last attempt  : No prior recovery attempt

--- Detector (Phase 1, eligibility gate) ---
at_risk                  : True
risk_reason              : TRANSIENT_FAILURE
detector recoverability  : high

--- Decision ---
decision_path            : ai_decision
override_reason          : None
diagnosis                : Transaction failed due to a transient network_error during UPI payment attempt; customer spent 148 seconds in checkout indicating purchase intent, but lacks prior successful payment history.
recommended_action       : recover_now
recovery_probability     : 0.72
confidence               : 0.81
reason                   : Network errors are typically temporary and resolvable by retrying the payment. The relatively long checkout duration suggests the customer was engaged and likely to complete the purchase if given a fresh payment link. With no prior successful payments but only one prior failure, the risk of chronic inability to pay is low, making an immediate recovery link the optimal action.

--- Ground truth (NOT shown to the agent; reference only) ---
gt_recoverable           : True
gt_outcome               : recovered

======================================================================
EVENT 2 of 5
======================================================================
decision_id              : 383d5a0a-e072-4b3c-b192-eb72158184cd
synthetic_event_id       : d3c2d507-1009-46f7-9d40-0f24f3e8e213
customer_ref             : cust_6485e142b1368771

--- Context used by the agent ---
amount                   : ₹7,221.62 (722162 paise)
status                   : failed
failure_reason           : network_error
payment_method           : netbanking
checkout_duration        : 399s
customer_tenure          : 10 days
prev successful payments : 0
prev failed payments     : 1
avg order value          : ₹2,577.52
time since last success  : No prior success recorded
prev recovery attempts   : 1
time since last attempt  : 159

--- Detector (Phase 1, eligibility gate) ---
at_risk                  : True
risk_reason              : TRANSIENT_FAILURE
detector recoverability  : high

--- Decision ---
decision_path            : ai_decision
override_reason          : None
diagnosis                : Transient network error during netbanking payment caused the failure despite the customer completing checkout steps.
recommended_action       : recover_now
recovery_probability     : 0.62
confidence               : 0.71
reason                   : Customer spent 399 seconds in checkout indicating high intent, has no successful payments but only one prior failure, and the failure reason is network_error which is typically transient. The last recovery attempt was 159 hours ago, so a new urgent recovery link is appropriate.

--- Ground truth (NOT shown to the agent; reference only) ---
gt_recoverable           : True
gt_outcome               : recovered

======================================================================
EVENT 3 of 5
======================================================================
decision_id              : 7f1b726a-9f70-4e8d-b5a8-330f482ef4d4
synthetic_event_id       : 28bd61e5-6af4-4db9-910b-bf1fa6fcf148
customer_ref             : cust_4a615a2384d5b5e7

--- Context used by the agent ---
amount                   : ₹15,575.48 (1557548 paise)
status                   : abandoned_checkout
failure_reason           : customer_abandoned
payment_method           : netbanking
checkout_duration        : 162s
customer_tenure          : 2 days
prev successful payments : 0
prev failed payments     : 2
avg order value          : ₹799.24
time since last success  : No prior success recorded
prev recovery attempts   : 0
time since last attempt  : No prior recovery attempt

--- Detector (Phase 1, eligibility gate) ---
at_risk                  : True
risk_reason              : CHECKOUT_ABANDONMENT
detector recoverability  : high

--- Decision ---
decision_path            : ai_decision
override_reason          : None
diagnosis                : Customer abandoned checkout likely due to high order value (₹15,575) far exceeding their historical average (₹799) and limited experience (2-day tenure, zero successful payments), causing hesitation or trust concerns during netbanking payment.
recommended_action       : send_payment_link
recovery_probability     : 0.38
confidence               : 0.71
reason                   : The customer showed intent by initiating checkout but abandoned due to amount mismatch and lack of prior success; a standard recovery payment link allows them to complete purchase at their convenience without pressure, fitting abandoned checkout behavior with low recovery history.

--- Ground truth (NOT shown to the agent; reference only) ---
gt_recoverable           : True
gt_outcome               : recovered

======================================================================
EVENT 4 of 5
======================================================================
decision_id              : 7565fcdb-92a8-407b-8acf-094a60d7f310
synthetic_event_id       : 4f00fa6b-25b1-407a-b8cf-7f0a2b8b4686
customer_ref             : cust_d13ee4f01df5543c

--- Context used by the agent ---
amount                   : ₹4,096.72 (409672 paise)
status                   : abandoned_checkout
failure_reason           : customer_abandoned
payment_method           : upi
checkout_duration        : 453s
customer_tenure          : 38 days
prev successful payments : 0
prev failed payments     : 2
avg order value          : ₹1,787.38
time since last success  : No prior success recorded
prev recovery attempts   : 2
time since last attempt  : 130

--- Detector (Phase 1, eligibility gate) ---
at_risk                  : True
risk_reason              : CHECKOUT_ABANDONMENT
detector recoverability  : high

--- Decision ---
decision_path            : ai_decision
override_reason          : None
diagnosis                : Customer abandoned checkout after ~7.5 minutes, likely due to price sensitivity or lack of trust in UPI, with no prior successful payments and two prior failed attempts.
recommended_action       : stop
recovery_probability     : 0.12
confidence               : 0.78
reason                   : Customer tenure 38 days with zero successful payments, two prior failed payments, historical AOV lower than current amount, and two prior recovery attempts already made without success; indicates low intent and unrecoverable failure.

--- Ground truth (NOT shown to the agent; reference only) ---
gt_recoverable           : False
gt_outcome               : not_recovered

======================================================================
EVENT 5 of 5
======================================================================
decision_id              : 3c49a01f-8fd3-4739-8ff2-bc535e5135ce
synthetic_event_id       : d7d8911c-d92b-4713-ae3c-a33ffcb602d8
customer_ref             : cust_6bd2692f82b7095d

--- Context used by the agent ---
amount                   : ₹10,998.20 (1099820 paise)
status                   : failed
failure_reason           : otp_timeout
payment_method           : card
checkout_duration        : 118s
customer_tenure          : 54 days
prev successful payments : 0
prev failed payments     : 1
avg order value          : ₹783.02
time since last success  : No prior success recorded
prev recovery attempts   : 0
time since last attempt  : No prior recovery attempt

--- Detector (Phase 1, eligibility gate) ---
at_risk                  : True
risk_reason              : TRANSIENT_FAILURE
detector recoverability  : high

--- Decision ---
decision_path            : ai_decision
override_reason          : None
diagnosis                : Customer attempted OTP but timed out after 118 seconds of checkout, indicating a transient failure likely due to distraction or network delay rather than card decline; no prior successful payments and low historical AOV suggest limited purchase intent, but the OTP attempt shows some commitment.
recommended_action       : recover_now
recovery_probability     : 0.62
confidence               : 0.71
reason                   : The failure reason 'otp_timeout' is a transient issue recoverable by sending a fresh payment link; the customer spent considerable time in checkout and engaged with OTP, indicating moderate intent despite lack of prior success; sending an urgent recovery link now capitalizes on the recent attempt.

--- Ground truth (NOT shown to the agent; reference only) ---
gt_recoverable           : True
gt_outcome               : recovered

+ Thought: 3.0s

Read-only inspection complete (no files or DB records modified) - agent_decisions contains exactly 5 rows. Key takeaways:

Decision paths: All 5 were pure ai_decision - no pre-filters triggered (none had ≥3 attempts or amount > ₹18,000) and no gated overrides (all confidences ≥ 0.5, all actions valid).

Action breakdown: recover_now ×3, send_payment_link ×1, stop ×1. Confidences 0.71-0.81.

vs. Ground truth (not shown to the agent, listed for your reference only): 4 events were gt_recoverable=True and the agent attempted recovery on all 4; event 4 (gt_recoverable=False) was correctly stop-ped with low recovery_probability (0.12). So the dry run is 5/5 aligned with ground truth - all 4 recoveries would earn ₹(2,564+7,222+15,575+10,998) ≈ ₹36,360 with zero bad interventions on this tiny sample.

Full per-event details (context, detector gate, decision, reasoning, ground truth) are in the output above.

#,Failure reason,Amount,Key enriched context,Action,Prob.,Conf.,Path,Override,GT (eval-only),Aligned (eval-only)
1,network_error,"₹2,564","13d · 0✓/1× · AOV ₹2,379 · 148s · 0 att",recover_now,0.72,0.81,ai_decision,—,recovered / recoverable,Yes
2,network_error,"₹7,222","10d · 0✓/1× · AOV ₹2,578 · 399s · 1 att, 159h",recover_now,0.72,0.81,ai_decision,—,recovered / recoverable,Yes
3,customer_abandoned,"₹15,575",2d · 0✓/2× · AOV ₹799 · 162s · 0 att,escalate_to_merchant,0.25,0.78,ai_decision,—,recovered / recoverable,No
4,customer_abandoned,"₹4,097","38d · 0✓/2× · AOV ₹1,787 · 453s · 2 att, 130h",stop,0.12,0.88,ai_decision,—,not_recovered / non-recoverable,Yes
5,otp_timeout,"₹10,998",54d · 0✓/1× · AOV ₹783 · 118s · 0 att,recover_now,0.35,0.60,ai_decision,—,recovered / recoverable,Yes
6,otp_timeout,"₹19,075",18d · 0✓/2× · AOV ₹939 · 312s · 0 att,escalate_to_merchant,0.0,1.0,pre_filtered,high_value_requires_human_review,recovered / recoverable,No
7,network_error,"₹18,595","49d · 0✓/2× · AOV ₹2,372 · 346s · 0 att",escalate_to_merchant,0.0,1.0,pre_filtered,high_value_requires_human_review,not_recovered / non-recoverable,Yes
8,card_declined,"₹9,799","63d · 3✓/1× · AOV ₹3,166 · 312s · 0 att · last-succ 326h",escalate_to_merchant,0.0,0.0,gated_override,llm_call_failed,recovered / recoverable,No
9,network_error,"₹2,229","13d · 0✓/0× · AOV ₹2,176 · 89s · 0 att",recover_now,0.78,0.86,ai_decision,—,recovered / recoverable,Yes
10,network_error,"₹5,226","215d · 9✓/2× · AOV ₹1,379 · 338s · 0 att · last-succ 47h",recover_now,0.86,0.91,ai_decision,—,recovered / recoverable,Yes
11,customer_abandoned,"₹17,853","163d · 2✓/2× · AOV ₹2,200 · 521s · 0 att · last-succ 443h",send_payment_link,0.48,0.72,ai_decision,—,recovered / recoverable,Yes
12,otp_timeout,"₹12,836",48d · 0✓/2× · AOV ₹982 · 269s · 0 att,send_payment_link,0.45,0.68,ai_decision,—,recovered / recoverable,Yes
13,otp_timeout,"₹10,827","22d · 0✓/2× · AOV ₹1,268 · 198s · 0 att",recover_now,0.55,0.78,ai_decision,—,recovered / recoverable,Yes
14,otp_timeout,₹689,"889d · 9✓/10× · AOV ₹7,057 · 347s · 4 att, 86h",stop,0.0,1.0,pre_filtered,attempts_exhausted,not_recovered / non-recoverable,Yes
15,customer_abandoned,"₹2,044",26d · 0✓/2× · AOV ₹789 · 199s · 0 att,stop,0.12,0.78,ai_decision,—,recovered / recoverable,No

--------------------------------------------------------------------------------
EVENT 1
--------------------------------------------------------------------------------
failure_reason         : network_error | status: failed | method: upi
amount                 : ₹2,564.31 (256431 paise)
enriched context       : tenure 13d · succ 0 / failed 1 · AOV ₹2,378.93 · checkout 148s · attempts 0 · last-attempt none · last-success none
recommended_action     : recover_now
recovery_probability   : 0.72
confidence             : 0.81
decision_path          : ai_decision
override_reason        : None
diagnosis              : Transient network error during UPI payment attempt, likely a temporary connectivity issue causing failure despite customer engagement.
reason                 : Customer spent 148 seconds in checkout indicating intent, has no successful payments yet but only one prior failure; network_error is a transient fault suitable for immediate recovery link.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 2
--------------------------------------------------------------------------------
failure_reason         : network_error | status: failed | method: netbanking
amount                 : ₹7,221.62 (722162 paise)
enriched context       : tenure 10d · succ 0 / failed 1 · AOV ₹2,577.52 · checkout 399s · attempts 1 · last-attempt 159h · last-success none
recommended_action     : recover_now
recovery_probability   : 0.72
confidence             : 0.81
decision_path          : ai_decision
override_reason        : None
diagnosis              : Network error interrupted the netbanking payment flow despite customer spending ~6.5 minutes in checkout, indicating a transient failure rather than intent loss.
reason                 : Customer tenure is short with no successful payments, but the lengthy checkout duration and network_error failure suggest a recoverable transient issue. The prior recovery attempt was over 6 days ago, so a fresh urgent payment link is appropriate.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 3
--------------------------------------------------------------------------------
failure_reason         : customer_abandoned | status: abandoned_checkout | method: netbanking
amount                 : ₹15,575.48 (1557548 paise)
enriched context       : tenure 2d · succ 0 / failed 2 · AOV ₹799.24 · checkout 162s · attempts 0 · last-attempt none · last-success none
recommended_action     : escalate_to_merchant
recovery_probability   : 0.25
confidence             : 0.78
decision_path          : ai_decision
override_reason        : None
diagnosis              : Customer abandoned checkout likely due to high order value (₹15,575.48) far exceeding their historical average (₹799.24) and lack of prior successful payments, indicating trust or affordability concerns during netbanking payment.
reason                 : The customer has only 2 days tenure, zero successful payments, two prior failures, and abandoned a high-value checkout after 162 seconds. This combination of low intent signals and high uncertainty suggests merchant review is warranted before automated recovery.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: False

--------------------------------------------------------------------------------
EVENT 4
--------------------------------------------------------------------------------
failure_reason         : customer_abandoned | status: abandoned_checkout | method: upi
amount                 : ₹4,096.72 (409672 paise)
enriched context       : tenure 38d · succ 0 / failed 2 · AOV ₹1,787.38 · checkout 453s · attempts 2 · last-attempt 130h · last-success none
recommended_action     : stop
recovery_probability   : 0.12
confidence             : 0.88
decision_path          : ai_decision
override_reason        : None
diagnosis              : Customer abandoned checkout after ~7.5 minutes, likely due to payment reluctance or inability to complete a high-value UPI transaction given no prior successful payments and order value exceeding historical average.
reason                 : Customer tenure 38 days with zero successful payments, two prior failed payments, abandoned after lengthy checkout, amount ₹4,096.72 > historical AOV ₹1,787.38, and two recovery attempts already made with no success; low intent to pay.
[EVAL-ONLY] gt_recoverable: False | gt_outcome: not_recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 5
--------------------------------------------------------------------------------
failure_reason         : otp_timeout | status: failed | method: card
amount                 : ₹10,998.20 (1099820 paise)
enriched context       : tenure 54d · succ 0 / failed 1 · AOV ₹783.02 · checkout 118s · attempts 0 · last-attempt none · last-success none
recommended_action     : recover_now
recovery_probability   : 0.35
confidence             : 0.60
decision_path          : ai_decision
override_reason        : None
diagnosis              : Customer failed to enter OTP within the allotted time, likely due to distraction or hesitation given the high transaction amount and lack of prior successful payment history.
reason                 : The failure reason 'otp_timeout' is a transient issue that can be resolved by re-sending a payment link. Despite the customer's zero successful payments, the relatively short checkout duration (118 s) and the high order value suggest purchase intent. An urgent recovery link offers the best chance to capture the transaction before the customer abandons completely.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 6
--------------------------------------------------------------------------------
failure_reason         : otp_timeout | status: failed | method: netbanking
amount                 : ₹19,074.83 (1907483 paise)
enriched context       : tenure 18d · succ 0 / failed 2 · AOV ₹939.03 · checkout 312s · attempts 0 · last-attempt none · last-success none
recommended_action     : escalate_to_merchant
recovery_probability   : 0.0
confidence             : 1.0
decision_path          : pre_filtered
override_reason        : high_value_requires_human_review
diagnosis              : pre_filtered_high_value
reason                 : Amount exceeds automated recovery threshold (amount > ₹18,000)
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: False

--------------------------------------------------------------------------------
EVENT 7
--------------------------------------------------------------------------------
failure_reason         : network_error | status: failed | method: card
amount                 : ₹18,594.71 (1859471 paise)
enriched context       : tenure 49d · succ 0 / failed 2 · AOV ₹2,371.52 · checkout 346s · attempts 0 · last-attempt none · last-success none
recommended_action     : escalate_to_merchant
recovery_probability   : 0.0
confidence             : 1.0
decision_path          : pre_filtered
override_reason        : high_value_requires_human_review
diagnosis              : pre_filtered_high_value
reason                 : Amount exceeds automated recovery threshold (amount > ₹18,000)
[EVAL-ONLY] gt_recoverable: False | gt_outcome: not_recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 8
--------------------------------------------------------------------------------
failure_reason         : card_declined | status: failed | method: card
amount                 : ₹9,799.11 (979911 paise)
enriched context       : tenure 63d · succ 3 / failed 1 · AOV ₹3,165.82 · checkout 312s · attempts 0 · last-attempt none · last-success 326h
recommended_action     : escalate_to_merchant
recovery_probability   : 0.0
confidence             : 0.0
decision_path          : gated_override
override_reason        : llm_call_failed
diagnosis              : llm_call_failed
reason                 : LLM error: Failed to parse LLM output as JSON: Expecting ',' delimiter: line 6 column 21 (char 793)
Raw content:
{
  "diagnosis": "Card declined likely due to insufficient funds or card limit exceeded, as the transaction amount (~₹9,799) is roughly three times the customer's historical average order value (₹3,166) and there is no recent successful payment in the last 13.6 days.",
  "recovery_probability": 0.52,
  "recommended_action": "send_payment_link",
  "reason": "Customer has solid tenure (63 days) with 3 prior successful payments and only one prior failure, indicating generally good payment behavior. The checkout duration of 312 seconds suggests genuine purchase intent rather than abandonment. A standard recovery payment link allows the customer to retry with the same or alternative card and address potential fund or limit issues without appearing overly urgent.",
  "confidence": 0.71
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: False

--------------------------------------------------------------------------------
EVENT 9
--------------------------------------------------------------------------------
failure_reason         : network_error | status: failed | method: netbanking
amount                 : ₹2,229.17 (222917 paise)
enriched context       : tenure 13d · succ 0 / failed 0 · AOV ₹2,176.46 · checkout 89s · attempts 0 · last-attempt none · last-success none
recommended_action     : recover_now
recovery_probability   : 0.78
confidence             : 0.80
decision_path          : ai_decision
override_reason        : None
diagnosis              : Network error during netbanking payment caused a transient failure; customer showed purchase intent with checkout duration of 89 seconds and order value matching historical average.
reason                 : The failure reason 'network_error' indicates a temporary connectivity issue, not a decline or fraud. Customer tenure of 13 days and average order value close to transaction amount suggest genuine intent. No prior recovery attempts, so an immediate Razorpay recovery link is appropriate to capture the sale before the customer abandons.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 10
--------------------------------------------------------------------------------
failure_reason         : network_error | status: failed | method: upi
amount                 : ₹5,225.57 (522557 paise)
enriched context       : tenure 215d · succ 9 / failed 2 · AOV ₹1,378.56 · checkout 338s · attempts 0 · last-attempt none · last-success 47h
recommended_action     : recover_now
recovery_probability   : 0.86
confidence             : 0.91
decision_path          : ai_decision
override_reason        : None
diagnosis              : Transient network error during UPI payment; customer exhibited moderate checkout duration and strong historical success rate, indicating high intent but a temporary connectivity issue caused failure.
reason                 : Customer tenure of 215 days with 9 successful payments and only 2 prior failures shows reliable behavior. The current order value is above historical average suggests deliberate purchase intent. Checkout duration of 338 seconds (~5.6 minutes) indicates active engagement. Failure reason 'network_error' is typically transient and resolvable by retrying the payment. No prior recovery attempts have been made, so an immediate recovery link is appropriate.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 11
--------------------------------------------------------------------------------
failure_reason         : customer_abandoned | status: abandoned_checkout | method: card
amount                 : ₹17,852.67 (1785267 paise)
enriched context       : tenure 163d · succ 2 / failed 2 · AOV ₹2,200.45 · checkout 521s · attempts 0 · last-attempt none · last-success 443h
recommended_action     : send_payment_link
recovery_probability   : 0.48
confidence             : 0.72
decision_path          : ai_decision
override_reason        : None
diagnosis              : Customer abandoned checkout likely due to price shock or hesitation, as the order value is significantly higher than their historical average despite adequate checkout time and prior successful payment history.
reason                 : The customer has a mixed but existent success history (2 successful payments) and moderate tenure, indicating potential to recover with a standard payment link; no prior recovery attempts and abandonment reason points to customer decision rather than technical failure.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 12
--------------------------------------------------------------------------------
failure_reason         : otp_timeout | status: failed | method: upi
amount                 : ₹12,835.52 (1283552 paise)
enriched context       : tenure 48d · succ 0 / failed 2 · AOV ₹982.83 · checkout 269s · attempts 0 · last-attempt none · last-success none
recommended_action     : send_payment_link
recovery_probability   : 0.45
confidence             : 0.68
decision_path          : ai_decision
override_reason        : None
diagnosis              : OTP timeout failure indicating the customer did not complete the UPI authentication within the allowed time, likely due to distraction or hesitation on a high-value transaction relative to their typical spend.
reason                 : Customer spent 269 seconds at checkout showing some intent, but has zero successful payments and two prior failures, with historical average order value far below current amount, suggesting low confidence in completing high-value UPI payments; OTP timeout is a transient issue, but without established success history a standard recovery link with reasonable expiry balances urgency and customer convenience.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 13
--------------------------------------------------------------------------------
failure_reason         : otp_timeout | status: failed | method: netbanking
amount                 : ₹10,826.82 (1082682 paise)
enriched context       : tenure 22d · succ 0 / failed 2 · AOV ₹1,268.32 · checkout 198s · attempts 0 · last-attempt none · last-success none
recommended_action     : recover_now
recovery_probability   : 0.55
confidence             : 0.78
decision_path          : ai_decision
override_reason        : None
diagnosis              : Customer failed to complete OTP verification within the allotted time, likely due to distraction or unfamiliarity with netbanking OTP flow, given no prior successful payments and a transaction amount significantly higher than historical average.
reason                 : The failure reason 'otp_timeout' is a transient issue amenable to recovery via a payment link. Despite the lack of successful payment history, the customer attempted a high-value checkout (198 seconds duration) indicating intent. No prior recovery attempts have been made, so an urgent Razorpay recovery link is appropriate.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 14
--------------------------------------------------------------------------------
failure_reason         : otp_timeout | status: failed | method: card
amount                 : ₹688.81 (68881 paise)
enriched context       : tenure 889d · succ 9 / failed 10 · AOV ₹7,057.19 · checkout 347s · attempts 4 · last-attempt 86h · last-success 170h
recommended_action     : stop
recovery_probability   : 0.0
confidence             : 1.0
decision_path          : pre_filtered
override_reason        : attempts_exhausted
diagnosis              : pre_filtered_exhausted
reason                 : Recovery attempt limit reached (attempts >= 3)
[EVAL-ONLY] gt_recoverable: False | gt_outcome: not_recovered | aligned: True

--------------------------------------------------------------------------------
EVENT 15
--------------------------------------------------------------------------------
failure_reason         : customer_abandoned | status: abandoned_checkout | method: upi
amount                 : ₹2,043.55 (204355 paise)
enriched context       : tenure 26d · succ 0 / failed 2 · AOV ₹788.91 · checkout 199s · attempts 0 · last-attempt none · last-success none
recommended_action     : stop
recovery_probability   : 0.12
confidence             : 0.78
decision_path          : ai_decision
override_reason        : None
diagnosis              : Customer abandoned checkout after ~3.3 minutes, likely due to hesitation about a higher-than-usual amount and lack of trust from prior failed payments, with no successful transaction history.
reason                 : The customer has zero successful payments, two prior failures, and abandoned a checkout for an amount significantly above their historical average, indicating low intent and trust; recovery attempts are unlikely to succeed.
[EVAL-ONLY] gt_recoverable: True | gt_outcome: recovered | aligned: False

Decision paths: 11 ai_decision, 3 pre_filtered (events 6, 7, 14), 1 gated_override (event 8). So of 12 events that reached the LLM, 11 produced pure AI decisions.

Requested Analysis

Evaluation-only notice: ground-truth columns above and the alignment counts below use the benchmark's pre-generated ground-truth fields, which were NOT shown to the agent. Alignment convention: attempting recovery (recover_now / send_payment_link / wait_and_retry) on a recoverable event, or withholding it (stop / escalation) on a non-recoverable event, counts as aligned.

1. Aligned with ground truth: 11/15. The 4 misses (events 3, 6, 8, 15) are all missed recoverable revenue – false negatives. There are zero false positives.
2. Recovery attempts on recoverable events: 8 (events 1, 2, 5, 9, 10, 11, 12, 13). Per the fixed simulation rule, all 8 recover -> ₹69,753.88 gross, net ₹69,753.88 (no penalties).
3. Bad interventions on non-recoverable events: 0. All 3 non-recoverable events (4, 7, 14) were correctly withheld – no ₹200 penalties.
4. Reasoning relying only on failure_reason: None. Every pure-AI decision cites concrete enriched signals – checkout duration in all 11, AOV/amount deviation in most (events 3, 4, 9, 10, 12, 13, 15), prior attempt recency in events 2 and 4, and success history in events 8-11. The closest to failure-reason-led are events 5 and 13, where "otp_timeout is transient" is the primary justification – but both still anchor on checkout engagement signals. Events 6, 7, 14 have canned deterministic pre-filter reasons (by design, not LLM reasoning).

One flag worth noting for Gate B: event 8 was a LLM output-format failure – the model's reasoning was actually good (cited 3x history, 3x AOV deviation, 312s intent) but the JSON was truncated (missing closing brace), so it fell back to escalate_to_merchant and lost a recoverable ₹9,799. At 1 failure in 12 LLM calls (~8%), format robustness is a real cost in the full run.
