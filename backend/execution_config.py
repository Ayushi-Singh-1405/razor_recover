#!/usr/bin/env python3
"""Execution policy configuration for RecoverAI.

Values governing real (live) recovery actions, per backend/EXECUTION_POLICY.md.
Every value is overridable via environment variables; defaults encode the
conservative posture - live execution is OFF unless a human explicitly
turns it on, and the volume/amount/attempt caps are tight.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _int_from_env(name: str, default: int) -> int:
    """Read an integer env var, falling back to the default when unset.

    Raises ValueError on a non-integer value rather than silently using
    the default - a misconfigured safety cap must be loud, not quiet.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer, got {raw!r}"
        ) from exc
    if value < 0:
        raise ValueError(f"Environment variable {name} must be >= 0, got {value}")
    return value


# Maximum number of real payment-link sends the execution layer may
# perform per execution run (volume safety cap against bugs/bad deploys).
MAX_REAL_RECOVERY_ACTIONS = _int_from_env("MAX_REAL_RECOVERY_ACTIONS", 10)

# Transactions above this amount (paise) are never auto-actioned;
# they escalate to human review. Default: 500000 paise = ₹5,000.
MAX_AUTOMATED_AMOUNT_PAISE = _int_from_env("MAX_AUTOMATED_AMOUNT_PAISE", 500_000)

# Recovery-attempt hard cap; transactions at/above this are hard-stopped.
# Matches the detector's EXHAUSTED_ATTEMPTS rule (previous_recovery_attempts >= 3).
MAX_ATTEMPTS = _int_from_env("MAX_ATTEMPTS", 3)

# Master switch for live execution. Becomes True ONLY when the env var
# is explicitly the string "true" (case-insensitive). Any other value -
# "1", "yes", "", unset - keeps it False. Never default-on.
LIVE_EXECUTION_ENABLED = os.getenv("LIVE_EXECUTION_ENABLED", "").strip().lower() == "true"
