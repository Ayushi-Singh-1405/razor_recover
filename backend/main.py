import json
import logging
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone, timedelta

import psycopg2
from fastapi import FastAPI, HTTPException, Path, Request, Depends
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db import SessionLocal, get_db
from models import Transaction, AuditLog, WebhookEvent, SyntheticEvent, DetectionResult, Merchant
from config import DATABASE_URL, razorpay_client, RAZORPAY_WEBHOOK_SECRET
from auth import router as auth_router, get_current_merchant
from dashboard_actions import router as dashboard_actions_router

_summary_cache = {"payload": None, "ts": 0.0}
import time as _time
from simulate_outcomes import RECOVERY_ACTIONS
from sqlalchemy import text

logger = logging.getLogger(__name__)

app = FastAPI(title="RecoverAI", version="0.1.0")
app.include_router(auth_router)
app.include_router(dashboard_actions_router)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/analytics", include_in_schema=False)
def analytics_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "analytics.html"))


@app.get("/audit", include_in_schema=False)
def audit_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "audit.html"))


@app.get("/developers", include_in_schema=False)
def developers_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "developers.html"))


@app.get("/resources", include_in_schema=False)
def resources_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "resources.html"))


@app.get("/security", include_in_schema=False)
def security_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "security.html"))


@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "dashboard.html"))


@app.get("/dashboard/summary")
def dashboard_summary(
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Aggregated dashboard data for the logged-in merchant.

    Detection and agent-evaluation numbers are aggregated from the same
    tables/reports verified on Day 2-4 — nothing is recomputed beyond
    counting and summing. Real-execution numbers come from the audit trail.
    """
    # Cache HIT: repeat loads within the TTL window return the cached
    # payload instantly (auth is still enforced by the dependency above).
    global _summary_cache
    if (_summary_cache["payload"] is not None
            and _time.time() - _summary_cache["ts"] <= 30):
        return _summary_cache["payload"]

    # ---- Detection (simulated benchmark, Day 2) --------------------------
    # One round trip for every scalar aggregate (detection + baseline +
    # agent) — each query is a cross-region round trip to Neon.
    AGG_SQL = """
        SELECT
          (SELECT count(*) FROM synthetic_events) AS total_events,
          (SELECT count(*) FROM detection_results WHERE at_risk) AS at_risk,
          (SELECT coalesce(sum(se.amount_paise), 0)
             FROM detection_results dr
             JOIN synthetic_events se ON se.id = dr.synthetic_event_id
            WHERE dr.at_risk) AS revenue_at_risk_paise,
          (SELECT count(*) FROM detection_results WHERE at_risk) AS bench_candidates,
          (SELECT count(*) FROM detection_results dr
             JOIN synthetic_events se ON se.id = dr.synthetic_event_id
            WHERE dr.at_risk AND se.ground_truth_recoverable) AS bench_recoveries,
          (SELECT coalesce(sum(se.ground_truth_recovered_amount), 0)
             FROM detection_results dr
             JOIN synthetic_events se ON se.id = dr.synthetic_event_id
            WHERE dr.at_risk AND se.ground_truth_recoverable) AS bench_recovered_paise,
          (SELECT count(*) FROM detection_results dr
             JOIN synthetic_events se ON se.id = dr.synthetic_event_id
            WHERE dr.at_risk AND NOT se.ground_truth_recoverable) AS bench_bad,
          (SELECT count(*) FROM agent_decisions ad
             JOIN synthetic_events se ON se.id = ad.synthetic_event_id
            WHERE ad.recommended_action IN ('recover_now','send_payment_link','wait_and_retry')) AS agent_candidates,
          (SELECT count(*) FROM agent_decisions ad
             JOIN synthetic_events se ON se.id = ad.synthetic_event_id
            WHERE ad.recommended_action IN ('recover_now','send_payment_link','wait_and_retry')
              AND se.ground_truth_recoverable) AS agent_recoveries,
          (SELECT coalesce(sum(se.ground_truth_recovered_amount), 0)
             FROM agent_decisions ad
             JOIN synthetic_events se ON se.id = ad.synthetic_event_id
            WHERE ad.recommended_action IN ('recover_now','send_payment_link','wait_and_retry')
              AND se.ground_truth_recoverable) AS agent_recovered_paise,
          (SELECT count(*) FROM agent_decisions ad
             JOIN synthetic_events se ON se.id = ad.synthetic_event_id
            WHERE ad.recommended_action IN ('recover_now','send_payment_link','wait_and_retry')
              AND NOT se.ground_truth_recoverable) AS agent_bad
    """
    agg = db.execute(text(AGG_SQL)).mappings().one()

    detection = {
        "total_events": int(agg["total_events"] or 0),
        "at_risk": int(agg["at_risk"] or 0),
        "revenue_at_risk_paise": int(agg["revenue_at_risk_paise"] or 0),
        "provenance": "simulated",
    }

    # ---- Real execution (Day 4, from the audit trail) --------------------
    tagged = (
        db.query(AuditLog)
        .filter(AuditLog.event == "demo_scenario_state_applied")
        .all()
    )
    scenario_by_txn = {a.transaction_id: (a.details or {}).get("scenario") for a in tagged}
    demo_ids = list(scenario_by_txn.keys())

    exec_event_names = {
        "execution_action_taken", "execution_stopped", "execution_escalated",
        "execution_capped", "execution_action_failed",
    }
    all_logs = (
        db.query(AuditLog)
        .filter(AuditLog.transaction_id.in_(demo_ids))
        .order_by(AuditLog.timestamp.asc())
        .all()
        if demo_ids
        else []
    )
    logs_by_txn = defaultdict(list)
    for log in all_logs:
        logs_by_txn[log.transaction_id].append(log)

    real_paise_recovered = sum(
        (log.details or {}).get("amount_paise", 0)
        for log in all_logs
        if log.event == "revenue_recovered"
    )

    txns = (
        db.query(Transaction)
        .filter(Transaction.id.in_(demo_ids))
        .order_by(Transaction.created_at.asc())
        .all()
    )

    # One decision per scenario: the LATEST execution_* event wins (the
    # audit trail may contain superseded entries from earlier runs).
    DECISION_BY_EVENT = {
        "execution_action_taken": "action",
        "execution_escalated": "escalate",
        "execution_stopped": "stop",
        "execution_capped": "stop",
        "execution_action_failed": "action",
    }
    transactions_out = []
    decision_counts = {"action": 0, "stop": 0, "escalate": 0}
    for txn in txns:
        exec_events = [l for l in logs_by_txn.get(txn.id, []) if l.event in exec_event_names]
        latest = exec_events[-1] if exec_events else None
        details = (latest.details or {}) if latest else {}
        decision = DECISION_BY_EVENT.get(latest.event) if latest else None
        if decision is None:
            reason = "no_execution_event"
            decision = "none"
        elif latest.event == "execution_action_taken":
            reason = "tier_high_within_limits"
        elif latest.event == "execution_action_failed":
            reason = details.get("reason", "action_failed")
        else:
            reason = details.get("reason", "policy_gate")
        if decision in decision_counts:
            decision_counts[decision] += 1

        transactions_out.append({
            "transaction_id": str(txn.id),
            "scenario": scenario_by_txn.get(txn.id),
            "amount_paise": txn.amount_paise,
            "failure_reason": txn.failure_reason,
            "decision": decision,
            "reason": reason,
            "payment_link_id": txn.razorpay_payment_link_id,
            "recovered": any(l.event == "revenue_recovered" for l in logs_by_txn.get(txn.id, [])),
            "audit_chain": [
                {
                    "timestamp": l.timestamp.isoformat(),
                    "event": l.event,
                    "details": l.details,
                }
                for l in logs_by_txn.get(txn.id, [])
            ],
        })

    real_execution = {
        "decision_engine": "deterministic_policy_gate",
        "llm_execution_authority": False,
        "scenarios_run": len(txns),
        "actions_taken": decision_counts["action"],
        "stopped": decision_counts["stop"],
        "escalated": decision_counts["escalate"],
        "real_paise_recovered": real_paise_recovered,
        "transactions": transactions_out,
    }

    # ---- Agent evaluation (Day 3 experiment) -----------------------------
    # Same accounting as simulate() (SS20.7/SS20.8), computed with aggregate
    # queries over the same tables so the request avoids pulling ~1,700 rows
    # and a fresh cross-region connection. dashboard_summary_check.py
    # cross-verifies these numbers against the written Day 3 reports.
    def stats_from_row(row):
        recovered_paise = int(row["recovered_paise"] or 0)
        bad = int(row["bad"] or 0)
        return {
            "candidate_decisions": int(row["candidates"] or 0),
            "successful_recoveries": int(row["recoveries"] or 0),
            "total_recovered_paise": recovered_paise,
            "bad_interventions": bad,
            "total_penalty_paise": bad * 20000,  # SS20.8: Rs 200 flat
            "net_recovered_paise": recovered_paise - bad * 20000,
        }

    def targeting_precision(stats) -> float:
        attempted = stats["candidate_decisions"]
        correct = stats["successful_recoveries"]
        return round(correct / attempted, 4) if attempted else 0.0

    baseline_stats = stats_from_row({
        "candidates": agg["bench_candidates"],
        "recoveries": agg["bench_recoveries"],
        "recovered_paise": agg["bench_recovered_paise"],
        "bad": agg["bench_bad"],
    })
    agent_stats = stats_from_row({
        "candidates": agg["agent_candidates"],
        "recoveries": agg["agent_recoveries"],
        "recovered_paise": agg["agent_recovered_paise"],
        "bad": agg["agent_bad"],
    })

    def block(stats, precision):
        return {
            "candidate_decisions": stats["candidate_decisions"],
            "successful_recoveries": stats["successful_recoveries"],
            "recovered_paise": stats["total_recovered_paise"],
            "bad_interventions": stats["bad_interventions"],
            "net_recovered_paise": stats["net_recovered_paise"],
            "targeting_precision": precision,
        }

    agent_evaluation = {
        "label": "Agent vs Deterministic Benchmark",
        "agent": block(agent_stats, targeting_precision(agent_stats)),
        "benchmark": block(baseline_stats, targeting_precision(baseline_stats)),
        "verdict": "benchmark_retained_for_execution",
        "verdict_text": (
            "The recovery agent showed higher per-attempt targeting precision "
            "(73% vs 66%) but was more conservative economically. Under current "
            "evaluation economics, the deterministic benchmark is retained for "
            "real execution; the agent's reasoning is evaluated, not yet "
            "execution-authorized."
        ),
        "provenance": "simulated",
    }

    payload = {
        "detection": detection,
        "real_execution": real_execution,
        "agent_evaluation": agent_evaluation,
    }

    # Short TTL cache: repeated dashboard/analytics loads re-use the payload
    # for 30s instead of re-paying cross-region query round trips. Execution
    # runs and merchant actions take effect within one TTL window.
    if _summary_cache["payload"] is None or _time.time() - _summary_cache["ts"] > 30:
        _summary_cache["payload"] = payload
        _summary_cache["ts"] = _time.time()
    return _summary_cache["payload"]


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


class CreateTestOrderRequest(BaseModel):
    amount_paise: int = 499900


class CreateTestOrderResponse(BaseModel):
    transaction_id: str
    razorpay_order_id: str


@app.post("/transactions/create-test-order", response_model=CreateTestOrderResponse)
def create_test_order(request: CreateTestOrderRequest | None = None):
    amount_paise = request.amount_paise if request is not None else 499900

    try:
        order = razorpay_client.order.create({
            "amount": amount_paise,
            "currency": "INR",
        })
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Razorpay order creation failed: {e}")

    order_id = order["id"]
    db: Session = SessionLocal()
    try:
        txn = Transaction(
            razorpay_order_id=order_id,
            amount_paise=amount_paise,
            status="created",
        )
        db.add(txn)
        db.flush()

        audit = AuditLog(
            transaction_id=txn.id,
            event="order_created",
            details={"order_id": order_id, "amount": amount_paise},
        )
        db.add(audit)
        db.commit()
        db.refresh(txn)

        return CreateTestOrderResponse(
            transaction_id=str(txn.id),
            razorpay_order_id=order_id,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        db.close()


class CreatePaymentLinkResponse(BaseModel):
    transaction_id: str
    payment_link_id: str
    short_url: str


@app.post(
    "/transactions/{transaction_id}/create-payment-link",
    response_model=CreatePaymentLinkResponse,
)
def create_payment_link(
    transaction_id: str = Path(description="UUID of the transaction"),
):
    db: Session = SessionLocal()
    try:
        txn = db.get(Transaction, uuid.UUID(transaction_id))
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        expire_by = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())

        try:
            link = razorpay_client.payment_link.create({
                "amount": txn.amount_paise,
                "currency": "INR",
                "reference_id": str(txn.id),
                "expire_by": expire_by,
                "description": f"Payment for order {txn.razorpay_order_id}",
            })
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Razorpay payment link creation failed: {e}")

        payment_link_id = link["id"]
        short_url = link["short_url"]

        txn.razorpay_payment_link_id = payment_link_id

        audit = AuditLog(
            transaction_id=txn.id,
            event="payment_link_created",
            details={"payment_link_id": payment_link_id, "short_url": short_url},
        )
        db.add(audit)
        db.commit()
        db.refresh(txn)

        return CreatePaymentLinkResponse(
            transaction_id=str(txn.id),
            payment_link_id=payment_link_id,
            short_url=short_url,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        db.close()


def _find_transaction_for_payload(db: Session, payload: dict):
    event_data = payload.get("payload", {})

    payment_link_entity = (
        event_data.get("payment_link", {}).get("entity", {})
    )
    payment_link_id = payment_link_entity.get("id")
    if payment_link_id:
        txn = (
            db.query(Transaction)
            .filter(Transaction.razorpay_payment_link_id == payment_link_id)
            .first()
        )
        if txn:
            return txn

    order_id = payment_link_entity.get("order_id")
    if not order_id:
        payment_entity = event_data.get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
    if order_id:
        txn = (
            db.query(Transaction)
            .filter(Transaction.razorpay_order_id == order_id)
            .first()
        )
        if txn:
            return txn

    return None


@app.post("/webhook")
async def webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    try:
        razorpay_client.utility.verify_webhook_signature(
            body.decode("utf-8"), signature, RAZORPAY_WEBHOOK_SECRET
        )
    except Exception:
        truncated_sig = signature[:8] + "..." if len(signature) > 8 else signature
        try:
            db: Session = SessionLocal()
            db.add(AuditLog(
                event="webhook_signature_rejected",
                details={"signature_prefix": truncated_sig},
            ))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return {"status": "ignored"}

    event_id = request.headers.get("X-Razorpay-Event-Id", "")
    event_type = payload.get("event", "")

    if not event_id:
        return {"status": "ignored"}

    db: Session = SessionLocal()
    try:
        existing = db.get(WebhookEvent, event_id)
        if existing:
            return {"status": "ok"}

        webhook_event = WebhookEvent(
            id=event_id,
            event_type=event_type,
            payload=payload,
        )
        db.add(webhook_event)

        recovered_txn = None
        if event_type in ("payment_link.paid", "payment.captured"):
            recovered_txn = _find_transaction_for_payload(db, payload)
            if recovered_txn:
                recovered_txn.status = "recovered"

        db.add(AuditLog(
            event="webhook_verified",
            details={"event_id": event_id, "event_type": event_type},
        ))

        if recovered_txn:
            db.add(AuditLog(
                transaction_id=recovered_txn.id,
                event="revenue_recovered",
                details={
                    "event_id": event_id,
                    "amount_paise": recovered_txn.amount_paise,
                },
            ))

        db.commit()
    except IntegrityError:
        db.rollback()
    except Exception as e:
        db.rollback()
        logger.error("Webhook processing error: %s", e)
    finally:
        db.close()

    return {"status": "ok"}


def _format_audit_label(log: AuditLog) -> str:
    event = log.event
    if event == "order_created":
        return "Order created"
    if event == "payment_link_created":
        return "Payment Link created"
    if event == "webhook_verified":
        return "Webhook verified"
    if event == "webhook_signature_rejected":
        return "Webhook signature rejected"
    if event == "revenue_recovered":
        amount = (log.details or {}).get("amount_paise", 0)
        return f"Revenue recovered: ₹{amount // 100:,}"
    return event


@app.get("/audit/{transaction_id}")
def get_audit_log(transaction_id: uuid.UUID):
    db: Session = SessionLocal()
    try:
        logs = (
            db.query(AuditLog)
            .filter(AuditLog.transaction_id == transaction_id)
            .order_by(AuditLog.timestamp.asc())
            .all()
        )

        for log in logs:
            print(f"{log.timestamp.strftime('%H:%M:%S')} {_format_audit_label(log)}")

        return [
            {
                "timestamp": log.timestamp.isoformat(),
                "event": log.event,
                "details": log.details,
            }
            for log in logs
        ]
    finally:
        db.close()
