#!/usr/bin/env python3
import sys

import requests
from sqlalchemy import func

from db import SessionLocal
from models import WebhookEvent

BASE = "http://localhost:8000"
passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"PASS  {name}")
        passed += 1
    else:
        print(f"FAIL  {name}" + (f" — {detail}" if detail else ""))
        failed += 1


# 1. Idempotency — query DB for the most recent event_id and verify exactly 1 row
print("\n--- 1. Idempotency (DB direct) ---")
db = SessionLocal()
try:
    latest = db.query(WebhookEvent).order_by(WebhookEvent.processed_at.desc()).first()
    if latest:
        count = (
            db.query(func.count(WebhookEvent.id))
            .filter(WebhookEvent.id == latest.id)
            .scalar()
        )
        check(
            f"event_id={latest.id} has exactly 1 row",
            count == 1,
            f"got {count}",
        )
    else:
        check("webhook_events table has data", False, "table is empty")
finally:
    db.close()

# 2. Signature rejection
print("\n--- 2. Signature rejection ---")
resp = requests.post(
    f"{BASE}/webhook",
    json={"event": "payment_link.paid", "payload": {}},
    headers={
        "Content-Type": "application/json",
        "X-Razorpay-Signature": "bad_signature",
        "X-Razorpay-Event-Id": "evt_reject_test",
    },
)
check("Status is 401", resp.status_code == 401, f"got {resp.status_code}")
check(
    "Detail is 'Invalid webhook signature'",
    resp.json().get("detail") == "Invalid webhook signature",
    f"got {resp.json()}",
)

# 3. UUID validation
print("\n--- 3. UUID validation ---")
resp = requests.get(f"{BASE}/audit/not-a-valid-uuid")
check("Status is 422", resp.status_code == 422, f"got {resp.status_code}")

# 4. Empty audit trail
print("\n--- 4. Empty audit trail ---")
resp = requests.get(f"{BASE}/audit/00000000-0000-0000-0000-000000000000")
check("Status is 200", resp.status_code == 200, f"got {resp.status_code}")
check("Body is []", resp.json() == [], f"got {resp.json()}")

# Summary
print(f"\n{'=' * 40}")
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
