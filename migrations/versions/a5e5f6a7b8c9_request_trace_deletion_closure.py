"""Bind diagnostic request traces to their seat and class lifetimes."""
from alembic import op
import sqlalchemy as sa

revision = "a5e5f6a7b8c9"
down_revision = "f4d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    # Rows whose owner is already gone cannot lawfully survive deletion.
    bind.execute(sa.text("""
        DELETE FROM actor_request_trace
        WHERE class_id IS NULL
           OR NOT EXISTS (SELECT 1 FROM classes WHERE classes.class_id = actor_request_trace.class_id)
           OR NOT EXISTS (SELECT 1 FROM seats WHERE seats.public_id = actor_request_trace.actor_public_id)
    """))
    mismatched = bind.execute(sa.text("""
        SELECT COUNT(*) FROM actor_request_trace t
        JOIN seats s ON s.public_id = t.actor_public_id
        WHERE s.class_id IS NULL OR s.class_id <> t.class_id OR s.role <> t.actor_type
    """)).scalar()
    if mismatched:
        raise RuntimeError("Request traces have mismatched live seat/class references; reconcile before migration")
    foreign_keys = sa.inspect(bind).get_foreign_keys("actor_request_trace")
    with op.batch_alter_table("actor_request_trace") as batch:
        batch.alter_column("class_id", existing_type=sa.String(36), nullable=False)
        for columns, name, target, remote in [
            (["class_id"], "fk_actor_request_trace_class_id_classes", "classes", ["class_id"]),
            (["actor_public_id"], "fk_actor_request_trace_seat", "seats", ["public_id"]),
        ]:
            existing = next((fk for fk in foreign_keys if fk["constrained_columns"] == columns), None)
            if existing and existing.get("options", {}).get("ondelete", "").upper() == "CASCADE":
                continue
            if existing:
                batch.drop_constraint(existing["name"], type_="foreignkey")
            batch.create_foreign_key(name, target, columns, remote, ondelete="CASCADE")


def downgrade():
    with op.batch_alter_table("actor_request_trace") as batch:
        batch.drop_constraint("fk_actor_request_trace_seat", type_="foreignkey")
        batch.drop_constraint("fk_actor_request_trace_class_id_classes", type_="foreignkey")
        batch.alter_column("class_id", existing_type=sa.String(36), nullable=True)
        batch.create_foreign_key("fk_actor_request_trace_class_id_classes", "classes",
                                 ["class_id"], ["class_id"], ondelete="SET NULL")
