"""
Invariant: Money Supply Integrity

Three checks against economic drift and exploitation. All assume:
  - credits are positive amount_cents, debits are negative (sign convention)
  - only status='posted' AND NOT is_void rows contribute to balances

─────────────────────────────────────────────────────────────────────────────
Check 1 — Aggregate balance consistency
    SUM(all balance_cache rows) == SUM(all posted transaction amount_cents)

    Cheaper scalar check that runs before the per-pair checks. Also catches
    orphan cache rows (students with a non-zero balance_cache entry but no
    posted transactions) that the per-student join-based check would miss
    because those students fall out of the join.

─────────────────────────────────────────────────────────────────────────────
Check 2 — Transfer pair integrity (for rows with transfer_correlation_id)
    For every transfer pair:
        COUNT(*) == 2              (exactly two legs)
        SUM(amount_cents) == 0     (zero-sum)
        MIN(amount_cents) < 0      (one leg is a debit)
        MAX(amount_cents) > 0      (one leg is a credit)

    transfer_correlation_id is set on all new transfer rows (from this
    migration onward). Legacy rows (NULL) are covered by Check 3.

─────────────────────────────────────────────────────────────────────────────
Check 3 — Legacy transfer zero-sum (NULL correlation_id rows)
    For every (student_id, join_code):
        SUM(amount_cents WHERE description ILIKE 'Transfer%' AND correlation_id IS NULL) == 0

    Covers pre-migration rows. This check can be retired once all historical
    transfer rows have been backfilled with a correlation_id (or confirmed
    clean via audit).

─────────────────────────────────────────────────────────────────────────────
Metrics emitted on every run (PASS or FAIL):
    total_supply_cents          — sum of all balance_cache rows
    total_posted_ledger_cents   — sum of all posted transaction amount_cents
    delta_cents                 — cache − ledger (should always be 0)
    per_class_supply            — per-join_code breakdown (top 20)
"""

from sqlalchemy import text
from app.extensions import db


def run():
    violations = []
    total_cache_cents = 0
    total_ledger_cents = 0
    per_class = []

    try:
        # ── Check 1: Aggregate cache == aggregate posted ledger ──────────────

        total_cache_cents = db.session.execute(text("""
            SELECT
                COALESCE(SUM(posted_checking_balance_cents), 0)
                + COALESCE(SUM(posted_savings_balance_cents), 0)
            FROM balance_cache
        """)).scalar() or 0

        total_ledger_cents = db.session.execute(text("""
            SELECT COALESCE(SUM(amount_cents), 0)
            FROM transactions
            WHERE status = 'posted'
              AND NOT is_void
        """)).scalar() or 0

        delta_cents = total_cache_cents - total_ledger_cents

        if delta_cents != 0:
            violations.append(
                f"Money supply drift: cached balances total {total_cache_cents}¢, "
                f"ledger totals {total_ledger_cents}¢ (delta: {delta_cents:+d}¢)"
            )

        # ── Check 2: Pair integrity for rows with transfer_correlation_id ────

        broken_pairs = db.session.execute(text("""
            SELECT
                transfer_correlation_id,
                COUNT(*)            AS leg_count,
                SUM(amount_cents)   AS net_cents,
                MIN(amount_cents)   AS min_cents,
                MAX(amount_cents)   AS max_cents
            FROM transactions
            WHERE status = 'posted'
              AND NOT is_void
              AND transfer_correlation_id IS NOT NULL
            GROUP BY transfer_correlation_id
            HAVING
                COUNT(*) != 2
                OR SUM(amount_cents) != 0
                OR MIN(amount_cents) >= 0
                OR MAX(amount_cents) <= 0
        """)).fetchall()

        if broken_pairs:
            violations.append(
                f"{len(broken_pairs)} transfer pair(s) failed integrity check "
                f"(wrong leg count, non-zero sum, or missing debit/credit)"
            )

        # ── Check 3: Legacy zero-sum for pre-migration rows (NULL corr. id) ──

        legacy_imbalanced = db.session.execute(text("""
            SELECT student_id, join_code, SUM(amount_cents) AS net_cents
            FROM transactions
            WHERE status = 'posted'
              AND NOT is_void
              AND transfer_correlation_id IS NULL
              AND description ILIKE 'Transfer%'
            GROUP BY student_id, join_code
            HAVING SUM(amount_cents) != 0
        """)).fetchall()

        if legacy_imbalanced:
            violations.append(
                f"{len(legacy_imbalanced)} (student, class) pair(s) have imbalanced "
                f"legacy transfer rows (pre-migration, NULL correlation_id)"
            )

        # ── Per-class supply breakdown (logged only, not a FAIL condition) ───

        per_class = [
            {"join_code": row[0], "supply_cents": row[1]}
            for row in db.session.execute(text("""
                SELECT
                    join_code,
                    SUM(posted_checking_balance_cents)
                    + SUM(posted_savings_balance_cents) AS supply_cents
                FROM balance_cache
                GROUP BY join_code
                ORDER BY supply_cents DESC
                LIMIT 20
            """)).fetchall()
        ]

        # ── Build result ─────────────────────────────────────────────────────

        base = {
            "total_supply_cents": total_cache_cents,
            "total_posted_ledger_cents": total_ledger_cents,
            "delta_cents": delta_cents,
            "per_class_supply": per_class,
        }

        if violations:
            return {
                "name": "money_supply_integrity",
                "status": "FAIL",
                "details": "; ".join(violations),
                **base,
            }

        return {
            "name": "money_supply_integrity",
            "status": "PASS",
            **base,
        }

    except Exception as e:
        return {
            "name": "money_supply_integrity",
            "status": "FAIL",
            "details": str(e),
            "total_supply_cents": total_cache_cents,
            "total_posted_ledger_cents": total_ledger_cents,
            "delta_cents": total_cache_cents - total_ledger_cents,
            "per_class_supply": per_class,
        }
