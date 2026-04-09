"""
Invariant runner — executes all registered invariant checks and returns
a structured result suitable for the /health/invariants endpoint.

Design constraints:
  - Read-only: no writes or side effects
  - Deterministic: same DB state → same result
  - Fail-loud: any FAIL check produces an overall FAIL
  - Each check is independently try/caught; one check cannot crash another
"""

import logging
import time

from app.invariants import (
    balance_rules,
    idempotency,
    ledger_consistency,
    money_supply,
    temporal_integrity,
    transaction_state,
)
from app.utils.time import utc_now

logger = logging.getLogger(__name__)

_CHECKS = [
    ledger_consistency.run,
    idempotency.run,
    balance_rules.run,
    transaction_state.run,
    temporal_integrity.run,
    money_supply.run,
]


def _extract_supply_metrics(checks):
    """Pull money supply scalars out of the money_supply check result for top-level logging."""
    for check in checks:
        if check.get("name") == "money_supply_integrity":
            return {
                "total_supply_cents": check.get("total_supply_cents"),
                "total_posted_ledger_cents": check.get("total_posted_ledger_cents"),
                "delta_cents": check.get("delta_cents"),
            }
    return {}


def _safe_check(check):
    """
    Run a single check and return a result dict safe for HTTP serialization.

    Exception details (str(exc)) are logged here and never included in the
    returned dict, so tainted data cannot flow into the HTTP response.
    """
    try:
        raw = check()
    except Exception as exc:  # noqa: BLE001
        name = getattr(check, "__module__", "unknown").split(".")[-1]
        logger.error(
            "invariant_check_unhandled_exception",
            extra={"check": name, "error": str(exc)},
            exc_info=True,
        )
        return {"name": name, "status": "FAIL"}

    # Log internal details (which may contain db error strings) then drop them
    # from the dict so they are never serialised into the HTTP response.
    details = raw.pop("details", None)
    if details:
        logger.warning(
            "invariant_check_details",
            extra={"check": raw.get("name"), "details": details},
        )
    return raw


def run_invariants():
    started_at = time.monotonic()
    checks = [_safe_check(check) for check in _CHECKS]
    duration_ms = round((time.monotonic() - started_at) * 1000)

    failed = [c for c in checks if c.get("status") == "FAIL"]
    supply_metrics = _extract_supply_metrics(checks)

    result = {
        "status": "FAIL" if failed else "PASS",
        "failed_count": len(failed),
        "checks": checks,
        "duration_ms": duration_ms,
        "timestamp": utc_now().isoformat().replace("+00:00", "Z"),
    }

    log_extra = {
        "status": result["status"],
        "failed_count": len(failed),
        "duration_ms": duration_ms,
        "timestamp": result["timestamp"],
        **supply_metrics,
    }

    if failed:
        log_extra["failed_checks"] = [c["name"] for c in failed]
        logger.error("invariant_check_failed", extra=log_extra)
    else:
        logger.info("invariant_check", extra=log_extra)

    return result
