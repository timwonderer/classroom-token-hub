import pytest
from app.extensions import db
from app.models import Student
from app.feats.base import FEATContextError, requires_feat_context, is_feat_active

def test_commit_fails_outside_feat_context(app):
    """
    CONFIRM: No mutation until a FEAT context is established.
    This is the core architectural safeguard.
    """
    from app.hash_utils import hash_username, get_random_salt
    salt = get_random_salt()
    stu = Student(
        first_name="Illegal",
        last_initial="M",
        block="A",
        salt=salt,
        username_hash=hash_username("illegal", salt),
        pin_hash="fake-hash",
    )
    db.session.add(stu)
    
    with pytest.raises(FEATContextError) as excinfo:
        db.session.commit()
    
    assert "MANDATORY FEAT CONSTITUTIONAL VIOLATION (COMMIT)" in str(excinfo.value)
    db.session.rollback()

def test_flush_fails_outside_feat_context(app):
    """
    CONFIRM: No SQL emission (flush) until a FEAT context is established.
    """
    from app.hash_utils import hash_username, get_random_salt
    salt = get_random_salt()
    stu = Student(
        first_name="IllegalFlush",
        last_initial="M",
        block="A",
        salt=salt,
        username_hash=hash_username("illegalflush", salt),
        pin_hash="fake-hash",
    )
    db.session.add(stu)
    
    with pytest.raises(FEATContextError) as excinfo:
        db.session.flush()
    
    assert "MANDATORY FEAT CONSTITUTIONAL VIOLATION (FLUSH)" in str(excinfo.value)
    db.session.rollback()

def test_commit_succeeds_inside_feat_context(app):
    """
    CONFIRM: Mutations are permitted when wrapped in @requires_feat_context.
    """
    @requires_feat_context("FEAT-TEST-001")
    def legal_mutation():
        from app.hash_utils import hash_username, get_random_salt
        salt = get_random_salt()
        stu = Student(
            first_name="Legal",
            last_initial="M",
            block="A",
            salt=salt,
            username_hash=hash_username("legal", salt),
            pin_hash="fake-hash",
        )
        db.session.add(stu)
        db.session.commit()
        return stu

    stu = legal_mutation()
    assert stu.id is not None
    assert is_feat_active() is False # Should be cleared after exit

def test_nested_feat_context(app):
    """
    CONFIRM: Nested FEATs are tracked correctly.
    """
    @requires_feat_context("OUTER")
    def outer():
        assert is_feat_active()
        
        @requires_feat_context("INNER")
        def inner():
            assert is_feat_active()
            db.session.commit() # Should be allowed
        
        inner()
        assert is_feat_active()
        db.session.commit() # Should still be allowed
    
    outer()
    assert is_feat_active() is False

def test_feat_bypass_fails_in_production(app, monkeypatch):
    """
    CONFIRM: FEATBypass is strictly prohibited in production.
    """
    from app.feats.base import FEATBypass
    monkeypatch.setenv("FLASK_ENV", "production")
    
    with pytest.raises(FEATContextError) as excinfo:
        with FEATBypass():
            pass
    
    assert "strictly prohibited in PRODUCTION" in str(excinfo.value)

def test_feat_bypass_logs_warning(app, caplog):
    """
    CONFIRM: FEATBypass emits a warning log.
    """
    from app.feats.base import FEATBypass
    import logging
    
    with caplog.at_level(logging.WARNING):
        with FEATBypass():
            pass
    
    assert "FEAT-INTEGRITY-WARNING" in caplog.text
