from app import create_app
from app.extensions import db
from app.models import BalanceCache, Transaction
from app.utils.banking import settle_balances


def main() -> int:
    app = create_app()
    with app.app_context():
        contexts = set(
            db.session.query(BalanceCache.student_id, BalanceCache.join_code).all()
        )
        contexts.update(
            db.session.query(Transaction.student_id, Transaction.join_code)
            .filter(Transaction.join_code.isnot(None))
            .distinct()
            .all()
        )

        reconciled = 0
        failed = 0

        for student_id, join_code in sorted(contexts):
            try:
                settle_balances(student_id, join_code)
                db.session.commit()
                reconciled += 1
            except Exception:
                db.session.rollback()
                failed += 1
                app.logger.exception(
                    "Balance cache reconciliation failed for student=%s join_code=%s",
                    student_id,
                    join_code,
                )

        print(f"reconciled={reconciled} failed={failed}")
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
