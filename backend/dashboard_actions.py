#!/usr/bin/env python3
"""Merchant escalation actions for the dashboard.

POST /dashboard/escalations/{transaction_id}/approve  — human override:
    creates a real payment link via the existing create_payment_link logic
    (no duplicated Razorpay code) and audits execution_action_taken with
    triggered_by=merchant_manual_approval.
POST /dashboard/escalations/{transaction_id}/dismiss — record the
    merchant's decision to drop the escalation; no Razorpay call.

Both routes are protected by auth.get_current_merchant and both require
the transaction's LATEST execution_* audit event to be execution_escalated
— actions can only be taken on transactions that are actually awaiting
human judgment. Stopped transactions (attempts exhausted, already
recovered) can never be actioned: hard stops have no override.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_merchant
from db import get_db
from execution_config import LIVE_EXECUTION_ENABLED
from models import AuditLog, Merchant, Transaction

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

EXECUTION_EVENT_NAMES = {
    "execution_action_taken",
    "execution_stopped",
    "execution_escalated",
    "execution_capped",
    "execution_action_failed",
}


def _latest_execution_event(db: Session, transaction_id) -> AuditLog | None:
    """Most recent execution_* audit entry for the transaction (or None)."""
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.transaction_id == transaction_id,
            AuditLog.event.in_(EXECUTION_EVENT_NAMES),
        )
        .order_by(AuditLog.timestamp.desc())
        .first()
    )


def _load_escalated_transaction(transaction_id: str, db: Session) -> Transaction:
    """Shared precondition for approve/dismiss: transaction must exist and
    its latest execution_* audit event must be execution_escalated."""
    try:
        tid = uuid.UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Transaction not found")

    txn = db.get(Transaction, tid)
    if txn is None:
        raise HTTPException(status_code=404, detail="Transaction not found")

    latest = _latest_execution_event(db, tid)
    if latest is None or latest.event != "execution_escalated":
        current = latest.event if latest else "none"
        raise HTTPException(
            status_code=409,
            detail=f"Transaction is not currently escalated "
                   f"(latest execution event: {current})",
        )
    if txn.status == "recovered":
        raise HTTPException(
            status_code=409,
            detail="Transaction was already recovered via webhook; "
                   "no action possible",
        )
    return txn


@router.post("/escalations/{transaction_id}/approve")
def approve_escalation(
    transaction_id: str,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Merchant approves an escalated transaction: create the real
    recovery payment link (human judgment overrides the escalation)."""
    if not LIVE_EXECUTION_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Live execution is disabled (LIVE_EXECUTION_ENABLED is not 'true'). "
                   "Cannot create a real payment link.",
        )

    txn = _load_escalated_transaction(transaction_id, db)

    if txn.razorpay_payment_link_id:
        raise HTTPException(
            status_code=409,
            detail=f"Transaction already has a payment link ({txn.razorpay_payment_link_id})",
        )

    # Reuse the existing endpoint logic — no duplicated Razorpay call.
    # Imported lazily: main.py includes this router, so a module-level
    # import would be circular.
    from main import create_payment_link

    try:
        response = create_payment_link(transaction_id=str(txn.id))
    except Exception as exc:
        db.add(AuditLog(
            transaction_id=txn.id,
            event="execution_action_failed",
            details={
                "phase": "execution_policy",
                "triggered_by": "merchant_manual_approval",
                "approved_by": merchant.email,
                "error": str(exc),
            },
        ))
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=f"Payment link creation failed: {exc}",
        )

    db.add(AuditLog(
        transaction_id=txn.id,
        event="execution_action_taken",
        details={
            "phase": "execution_policy",
            "triggered_by": "merchant_manual_approval",
            "payment_link_id": response.payment_link_id,
            "approved_by": merchant.email,
        },
    ))
    db.commit()

    return {
        "transaction_id": str(txn.id),
        "payment_link_id": response.payment_link_id,
        "short_url": response.short_url,
        "amount_paise": txn.amount_paise,
        "approved_by": merchant.email,
        "status": "approved",
    }


@router.post("/escalations/{transaction_id}/dismiss")
def dismiss_escalation(
    transaction_id: str,
    merchant: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """Merchant dismisses an escalated transaction: audit the decision,
    take no automated action, make no Razorpay call."""
    txn = _load_escalated_transaction(transaction_id, db)

    db.add(AuditLog(
        transaction_id=txn.id,
        event="merchant_dismissed",
        details={
            "phase": "execution_policy",
            "dismissed_by": merchant.email,
        },
    ))
    db.commit()

    return {
        "transaction_id": str(txn.id),
        "status": "dismissed",
        "dismissed_by": merchant.email,
    }
