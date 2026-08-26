# Changelog

All notable changes to RecoverAI will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- Project directory scaffolding (backend/, frontend/, docs/, tests/, evaluation/, pitch/, demo/)
- FastAPI backend with /health, /transactions/*, /webhook, /audit/* endpoints
- SQLAlchemy models: Transaction, RecoveryAttempt, WebhookEvent, AuditLog
- Razorpay integration: order creation, payment link creation, webhook signature verification
- Idempotent webhook handler with event deduplication via X-Razorpay-Event-Id header
- Audit trail endpoint with human-readable console output
- Alembic migration for all 4 tables (PostgreSQL)
- Phase 0 smoke test script (test_phase0.py)
- Razorpay buildathon plan and engineering decision log
- Sprint planning docs (Day 1, Day 2)
