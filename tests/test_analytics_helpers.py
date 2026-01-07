"""
Tests for analytics helper functions.

Tests the resolve_current_join_code and get_teacher_class_options helper
functions to ensure:
- Correct behavior with multiple classes
- Correct behavior with single class
- Correct behavior with no classes
- Proper handling of request args
- Correct session state management
- Multi-tenancy scoping is enforced
"""
import pytest
from flask import session
from app import db
from app.models import Admin, TeacherBlock
from app.routes.analytics import resolve_current_join_code, get_teacher_class_options


@pytest.fixture
def setup_teacher_no_classes(client):
    """Create a teacher with no class periods."""
    teacher = Admin(
        username="teacher_noclass",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(teacher)
    db.session.commit()
    return teacher


@pytest.fixture
def setup_teacher_one_class(client):
    """Create a teacher with one class period."""
    teacher = Admin(
        username="teacher_oneclass",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(teacher)
    db.session.flush()
    
    # Create one TeacherBlock
    tb1 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period A",
        join_code="ONECLASS",
        first_name=b"Test",
        last_initial="S",
        last_name_hash_by_part=['hash1'],
        dob_sum=2025,
        salt=b"salt1234",
        first_half_hash="hash1"
    )
    db.session.add(tb1)
    db.session.commit()
    
    return teacher, tb1


@pytest.fixture
def setup_teacher_multiple_classes(client):
    """Create a teacher with multiple class periods."""
    teacher = Admin(
        username="teacher_multiclass",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(teacher)
    db.session.flush()
    
    # Create multiple TeacherBlocks
    tb1 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period A",
        join_code="CLASSA",
        first_name=b"Test",
        last_initial="S",
        last_name_hash_by_part=['hash1'],
        dob_sum=2025,
        salt=b"salt1234",
        first_half_hash="hash1"
    )
    tb2 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period B",
        join_code="CLASSB",
        first_name=b"Test",
        last_initial="T",
        last_name_hash_by_part=['hash2'],
        dob_sum=2026,
        salt=b"salt5678",
        first_half_hash="hash2"
    )
    tb3 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period C",
        join_code="CLASSC",
        first_name=b"Test",
        last_initial="U",
        last_name_hash_by_part=['hash3'],
        dob_sum=2027,
        salt=b"salt9012",
        first_half_hash="hash3"
    )
    db.session.add_all([tb1, tb2, tb3])
    db.session.commit()
    
    return teacher, [tb1, tb2, tb3]


@pytest.fixture
def setup_teacher_duplicate_join_codes(client):
    """Create a teacher with duplicate join codes (edge case)."""
    teacher = Admin(
        username="teacher_dupes",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(teacher)
    db.session.flush()
    
    # Create multiple TeacherBlocks with the same join_code
    # This can happen if there are multiple students in the same period
    tb1 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period A",
        join_code="DUPE",
        first_name=b"Student1",
        last_initial="A",
        last_name_hash_by_part=['hash1'],
        dob_sum=2025,
        salt=b"salt1234",
        first_half_hash="hash1"
    )
    tb2 = TeacherBlock(
        teacher_id=teacher.id,
        block="Period A",
        join_code="DUPE",
        first_name=b"Student2",
        last_initial="B",
        last_name_hash_by_part=['hash2'],
        dob_sum=2026,
        salt=b"salt5678",
        first_half_hash="hash2"
    )
    db.session.add_all([tb1, tb2])
    db.session.commit()
    
    return teacher, [tb1, tb2]


# ==================== get_teacher_class_options Tests ====================

def test_get_teacher_class_options_no_teacher(client):
    """Test get_teacher_class_options with no teacher_id."""
    options = get_teacher_class_options(None)
    assert options == []


def test_get_teacher_class_options_no_classes(client, setup_teacher_no_classes):
    """Test get_teacher_class_options for teacher with no classes."""
    teacher = setup_teacher_no_classes
    options = get_teacher_class_options(teacher.id)
    assert options == []


def test_get_teacher_class_options_one_class(client, setup_teacher_one_class):
    """Test get_teacher_class_options for teacher with one class."""
    teacher, tb1 = setup_teacher_one_class
    options = get_teacher_class_options(teacher.id)
    
    assert len(options) == 1
    assert options[0]['join_code'] == 'ONECLASS'
    assert options[0]['block'] == 'PERIOD A'
    assert 'label' in options[0]


def test_get_teacher_class_options_multiple_classes(client, setup_teacher_multiple_classes):
    """Test get_teacher_class_options for teacher with multiple classes."""
    teacher, blocks = setup_teacher_multiple_classes
    options = get_teacher_class_options(teacher.id)
    
    assert len(options) == 3
    join_codes = [opt['join_code'] for opt in options]
    assert 'CLASSA' in join_codes
    assert 'CLASSB' in join_codes
    assert 'CLASSC' in join_codes
    
    # Verify each option has required fields
    for opt in options:
        assert 'join_code' in opt
        assert 'block' in opt
        assert 'label' in opt


def test_get_teacher_class_options_deduplicates_join_codes(client, setup_teacher_duplicate_join_codes):
    """Test that get_teacher_class_options deduplicates join codes."""
    teacher, blocks = setup_teacher_duplicate_join_codes
    options = get_teacher_class_options(teacher.id)
    
    # Should only return one option even though there are two TeacherBlocks with same join_code
    assert len(options) == 1
    assert options[0]['join_code'] == 'DUPE'


def test_get_teacher_class_options_handles_empty_block(client):
    """Test get_teacher_class_options handles empty block string gracefully."""
    teacher = Admin(
        username="teacher_emptyblock",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(teacher)
    db.session.flush()
    
    # Create TeacherBlock with empty string block
    tb = TeacherBlock(
        teacher_id=teacher.id,
        block="",
        join_code="EMPTYBLOCK",
        first_name=b"Test",
        last_initial="N",
        last_name_hash_by_part=['hash1'],
        dob_sum=2025,
        salt=b"salt1234",
        first_half_hash="hash1"
    )
    db.session.add(tb)
    db.session.commit()
    
    options = get_teacher_class_options(teacher.id)
    
    assert len(options) == 1
    assert options[0]['join_code'] == 'EMPTYBLOCK'
    assert options[0]['block'] == ''  # Should handle empty string


# ==================== resolve_current_join_code Tests ====================

def test_resolve_current_join_code_no_classes(client, setup_teacher_no_classes):
    """Test resolve_current_join_code for teacher with no classes."""
    teacher = setup_teacher_no_classes
    
    with client.application.test_request_context('/'):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        assert join_code is None
        assert available_classes == []


def test_resolve_current_join_code_one_class_defaults_to_it(client, setup_teacher_one_class):
    """Test resolve_current_join_code defaults to the only class when teacher has one class."""
    teacher, tb1 = setup_teacher_one_class
    
    with client.application.test_request_context('/'):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        assert join_code == 'ONECLASS'
        assert len(available_classes) == 1
        assert session.get('current_join_code') == 'ONECLASS'


def test_resolve_current_join_code_multiple_classes_defaults_to_first(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code defaults to first class when teacher has multiple classes."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/'):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        assert join_code == 'CLASSA'  # First in the list
        assert len(available_classes) == 3
        assert session.get('current_join_code') == 'CLASSA'


def test_resolve_current_join_code_uses_valid_request_arg(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code uses valid join_code from request args."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/?join_code=CLASSB'):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        assert join_code == 'CLASSB'
        assert session.get('current_join_code') == 'CLASSB'


def test_resolve_current_join_code_ignores_invalid_request_arg(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code ignores invalid join_code in request args."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/?join_code=INVALID'):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        # Should fall back to first class since the request arg is invalid
        assert join_code == 'CLASSA'
        assert session.get('current_join_code') == 'CLASSA'


def test_resolve_current_join_code_uses_session_join_code(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code uses join_code from session when no request arg."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/'):
        session['current_join_code'] = 'CLASSC'
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        assert join_code == 'CLASSC'
        assert session.get('current_join_code') == 'CLASSC'


def test_resolve_current_join_code_request_arg_overrides_session(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code prefers request arg over session."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/?join_code=CLASSB'):
        session['current_join_code'] = 'CLASSC'
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        # Request arg should override session
        assert join_code == 'CLASSB'
        assert session.get('current_join_code') == 'CLASSB'


def test_resolve_current_join_code_ignores_invalid_session_join_code(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code ignores invalid join_code in session."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/'):
        session['current_join_code'] = 'INVALID'
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        # Should fall back to first class
        assert join_code == 'CLASSA'
        # Session should be updated to the valid join_code
        assert session.get('current_join_code') == 'CLASSA'


def test_resolve_current_join_code_handles_whitespace_in_request_arg(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code handles whitespace in request arg."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/?join_code= CLASSB '):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        # Should strip whitespace and use the valid join_code
        assert join_code == 'CLASSB'
        assert session.get('current_join_code') == 'CLASSB'


def test_resolve_current_join_code_updates_session(client, setup_teacher_multiple_classes):
    """Test resolve_current_join_code properly updates session state."""
    teacher, blocks = setup_teacher_multiple_classes
    
    with client.application.test_request_context('/'):
        # Initially no session join_code
        assert 'current_join_code' not in session
        
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        # Session should be set
        assert session.get('current_join_code') == join_code
        assert join_code is not None


def test_resolve_current_join_code_no_teacher(client):
    """Test resolve_current_join_code with no teacher_id."""
    with client.application.test_request_context('/'):
        join_code, available_classes = resolve_current_join_code(None)
        
        assert join_code is None
        assert available_classes == []


def test_resolve_current_join_code_multi_tenancy(client, setup_teacher_multiple_classes):
    """Test that resolve_current_join_code properly isolates classes."""
    teacher, blocks = setup_teacher_multiple_classes
    
    # Create another teacher with their own classes
    teacher2 = Admin(
        username="teacher2",
        totp_secret="TESTSECRET654321"
    )
    db.session.add(teacher2)
    db.session.flush()
    
    tb = TeacherBlock(
        teacher_id=teacher2.id,
        block="Period X",
        join_code="TEACHER2X",
        first_name=b"Test",
        last_initial="X",
        last_name_hash_by_part=['hash_t2'],
        dob_sum=2028,
        salt=b"saltt2",
        first_half_hash="hasht2"
    )
    db.session.add(tb)
    db.session.commit()
    
    # Test that teacher1 cannot see teacher2's classes
    with client.application.test_request_context('/?join_code=TEACHER2X'):
        join_code, available_classes = resolve_current_join_code(teacher.id)
        
        # Should ignore TEACHER2X and fall back to teacher1's first class
        assert join_code == 'CLASSA'
        join_codes = [c['join_code'] for c in available_classes]
        assert 'TEACHER2X' not in join_codes
