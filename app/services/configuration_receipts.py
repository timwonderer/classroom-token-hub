"""Class-owned temporary deduplication. Authority is checked by the FEAT first."""
from sqlalchemy.dialects.postgresql import insert
from app.extensions import db
from app.models import ConfigurationImportReceipt, ClassEconomy
from app.services.configuration_artifact import ConfigurationError


def reserve(context, operation_id, fingerprint, expires_at, accepted_at):
    table = ConfigurationImportReceipt.__table__
    inserted = db.session.execute(insert(table).values(
        class_id=context.class_id, operation_id=operation_id, actor_seat_id=context.seat_id,
        fingerprint=fingerprint, expires_at=expires_at, accepted_at=accepted_at, result={}
    ).on_conflict_do_nothing(index_elements=["class_id", "operation_id"]).returning(table.c.operation_id)).scalar_one_or_none()
    receipt = ConfigurationImportReceipt.query.filter_by(class_id=context.class_id,
        operation_id=operation_id).populate_existing().with_for_update().one()
    if receipt.fingerprint != fingerprint or receipt.actor_seat_id != context.seat_id:
        raise ConfigurationError("This operation was already submitted with different inputs")
    return receipt, inserted is not None


def find(context, operation_id):
    return ConfigurationImportReceipt.query.filter_by(class_id=context.class_id, operation_id=operation_id).populate_existing().first()


def cleanup(class_id, cutoff):
    return ConfigurationImportReceipt.query.filter(ConfigurationImportReceipt.class_id == class_id,
        ConfigurationImportReceipt.expires_at <= cutoff).delete(synchronize_session=False)


def class_scope(class_id, *, lock):
    query = ClassEconomy.query.filter_by(class_id=class_id).populate_existing()
    return (query.with_for_update() if lock else query).first()
