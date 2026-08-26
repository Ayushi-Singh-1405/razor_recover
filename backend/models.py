import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razorpay_order_id = Column(String, nullable=False)
    razorpay_payment_link_id = Column(String, nullable=True)
    amount_paise = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="created")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class RecoveryAttempt(Base):
    __tablename__ = "recovery_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)
    action = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSONB, nullable=False)
    processed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), nullable=True)
    event = Column(String, nullable=False)
    details = Column(JSONB, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SyntheticEvent(Base):
    __tablename__ = "synthetic_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    amount_paise = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    failure_reason = Column(String, nullable=True)
    customer_ref = Column(String, nullable=False)
    previous_successful_payments = Column(Integer, nullable=False, default=0)
    previous_recovery_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    raw_payload = Column(JSONB, nullable=True)
    ground_truth_recoverable = Column(Boolean, nullable=False, default=False)
    ground_truth_outcome = Column(String, nullable=False, default="not_applicable")
    ground_truth_recovered_amount = Column(Integer, nullable=False, default=0)
    customer_tenure_days = Column(Integer, nullable=True)
    previous_failed_payments = Column(Integer, nullable=False, default=0)
    average_order_value = Column(Integer, nullable=True)
    time_since_last_successful_payment_hours = Column(Integer, nullable=True)
    time_since_last_recovery_attempt_hours = Column(Integer, nullable=True)
    checkout_duration_seconds = Column(Integer, nullable=True)
    payment_method = Column(String, nullable=True)


class DetectionResult(Base):
    __tablename__ = "detection_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    synthetic_event_id = Column(UUID(as_uuid=True), ForeignKey("synthetic_events.id"), nullable=False)
    at_risk = Column(Boolean, nullable=False, default=False)
    recoverability = Column(String, nullable=False, default="none")
    risk_reason = Column(String, nullable=False, default="NOT_AT_RISK")
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
