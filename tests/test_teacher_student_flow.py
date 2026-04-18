import pytest
from app.models import Student, TeacherBlock, Transaction, StoreItem, StudentItem, Admin
from app.utils.analytics_engine import AnalyticsEngine
from app import db
import time
from datetime import datetime, timezone, timedelta

@pytest.fixture
def teacher(app):
    from app.models import Admin
    from app.utils.encryption import encrypt_totp
    import pyotp
    from app.hash_utils import get_random_salt, hash_hmac

    with app.app_context():
        salt = get_random_salt()
        dob_sum_hash = hash_hmac(str(2003).encode(), salt) # 1+1+2001

        t = Admin(
            username="teacher_test",
            totp_secret=encrypt_totp(pyotp.random_base32()),
            salt=salt,
            dob_sum_hash=dob_sum_hash
        )
        db.session.add(t)
        db.session.commit()
        return t

def test_teacher_student_lifecycle(client, teacher, app):
    """
    Test the full lifecycle of a Teacher Student account:
    1. Automatic creation on class creation/upload.
    2. Claiming process.
    3. Functionality (logging in, viewing dashboard).
    4. Constraints (cannot delete, cannot move).
    5. Exclusion from analytics/goals.
    """
    with app.app_context():
        # Merge teacher into current session
        teacher = db.session.merge(teacher)

        # 1. Verify automatic creation via helper
        from app.routes.admin import _ensure_teacher_student_seat

        # Login as teacher
        client.post('/admin/login', data={'username': teacher.username, 'totp_code': '000000'})

        join_code = "TEACHER_TEST_CODE"
        block = "Z"
        _ensure_teacher_student_seat(teacher.id, join_code, block)

        # Verify TeacherBlock created
        tb = TeacherBlock.query.filter_by(teacher_id=teacher.id, join_code=join_code, is_teacher=True).first()
        assert tb is not None
        assert tb.first_name == "Teacher"
        assert tb.last_initial == "S"
        assert tb.dob_sum == 2003 # 1+1+2001

        # 2. Claim the account (Step 1)
        response = client.post('/student/claim-account', data={
            'join_code': join_code,
            'first_initial': 'T',
            'last_name': 'Student',
            'dob_sum': '2001-01-01'
        }, follow_redirects=True)

        assert response.status_code == 200

        # Verify TeacherBlock is claimed and linked
        db.session.refresh(tb)
        assert tb.is_claimed is True
        assert tb.student_id is not None

        student = db.session.get(Student, tb.student_id)
        assert student is not None
        assert student.is_teacher is True
        assert student.block == block

        # Step 2: Create Username
        # Note: Form expects 'write_in_word'. Logic: adjective + word + dob + initials
        response = client.post('/student/create-username', data={
            'write_in_word': 'hero'
        }, follow_redirects=True)
        assert response.status_code == 200

        # Refresh student to get generated username
        db.session.refresh(student)
        # Note: username is hashed in DB, but plaintext is in session['generated_username']
        # We can't access session easily here without mocking secure cookie?
        # Actually client.session works.
        with client.session_transaction() as sess:
            generated_username = sess.get('generated_username')

        assert generated_username is not None
        assert 'hero' in generated_username

        # Step 3: Setup PIN/Passphrase
        response = client.post('/student/setup-pin-passphrase', data={
            'pin': '1234',
            'passphrase': 'secure logic'
        }, follow_redirects=True)
        assert response.status_code == 200

        db.session.refresh(student)
        assert student.has_completed_setup is True

        # 3. Verify Constraints

        # A. Cannot delete via admin
        with client.session_transaction() as sess:
            sess['admin_id'] = teacher.id
            sess['is_admin'] = True

        response = client.post('/admin/student/delete', data={
            'student_id': student.id,
            'confirmation': 'DELETE'
        }, follow_redirects=True)

        assert "Teacher student accounts cannot be deleted directly" in response.get_data(as_text=True)

        db.session.refresh(student)
        assert student.is_active is True

        # B. Cannot move via edit
        response = client.post('/admin/student/edit', data={
            'student_id': student.id,
            'first_name': 'Teacher',
            'last_name': 'Student',
            'blocks': ['A', 'B']
        }, follow_redirects=True)

        assert "Teacher student accounts cannot be moved" in response.get_data(as_text=True)

        db.session.refresh(student)
        assert student.block == "Z"

        # 4. Analytics Exclusion
        from app.hash_utils import get_random_salt

        regular_student = Student(
            first_name="Regular",
            last_initial="R",
            block="Z",
            is_teacher=False,
            salt=get_random_salt(),
            dob_sum=100,
            first_half_hash=b'fakehash',
            last_name_hash_by_part=["fakehashpart"]
        )
        db.session.add(regular_student)
        db.session.commit()

        regular_tb = TeacherBlock(
            teacher_id=teacher.id,
            block="Z",
            join_code=join_code,
            student_id=regular_student.id,
            is_claimed=True,
            first_name="Regular",
            last_initial="R",
            dob_sum=100,
            salt=regular_student.salt,
            first_half_hash=b'fakehash',
            last_name_hash_by_part=["fakehashpart"]
        )
        db.session.add(regular_tb)

        # Add StudentTeacher link
        from app.models import StudentTeacher
        st1 = StudentTeacher(student_id=regular_student.id, admin_id=teacher.id)
        db.session.add(st1)

        db.session.commit()

        now_ts = datetime.now(timezone.utc)

        # Teacher Student transaction
        t1 = Transaction(
            student_id=student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=100,
            type='deposit',
            timestamp=now_ts
        )
        # Regular Student transaction
        t2 = Transaction(
            student_id=regular_student.id,
            teacher_id=teacher.id,
            join_code=join_code,
            amount=100,
            type='deposit',
            timestamp=now_ts
        )
        db.session.add_all([t1, t2])
        db.session.commit()

        # Lazy student (Inactive)
        lazy_student = Student(
            first_name="Lazy",
            last_initial="L",
            block="Z",
            is_teacher=False,
            salt=get_random_salt(),
            dob_sum=100,
            first_half_hash=b'fakehash2',
            last_name_hash_by_part=["fakehashpart2"]
        )
        db.session.add(lazy_student)
        db.session.commit()

        lazy_tb = TeacherBlock(
            teacher_id=teacher.id,
            block="Z",
            join_code=join_code,
            student_id=lazy_student.id,
            is_claimed=True,
            first_name="Lazy",
            last_initial="L",
            dob_sum=100,
            salt=lazy_student.salt,
            first_half_hash=b'fakehash2',
            last_name_hash_by_part=["fakehashpart2"]
        )
        db.session.add(lazy_tb)

        # Add StudentTeacher link
        st2 = StudentTeacher(student_id=lazy_student.id, admin_id=teacher.id)
        db.session.add(st2)

        db.session.commit()

        # Instantiate AnalyticsEngine
        engine = AnalyticsEngine(teacher.id, join_code)

        start = now_ts - timedelta(days=1)
        end = now_ts + timedelta(days=1)

        rate, active, total = engine.calculate_participation_rate(start, end)

        # Teacher Student is EXCLUDED.
        # Regular Student is INCLUDED.
        # Lazy Student is INCLUDED.
        # Total Enrolled = 2 (Regular + Lazy).
        # Active = 1 (Regular).
        # Rate = 50.0.

        assert total == 2
        assert active == 1
        assert rate == 50.0

        # 5. Collective Goal Exclusion
        goal_item = StoreItem(
            teacher_id=teacher.id,
            name="Pizza Party",
            price=1000,
            item_type='collective',
            is_active=True
        )
        db.session.add(goal_item)
        db.session.commit()

        # Teacher student buys it (should NOT contribute)
        si_teacher = StudentItem(
            student_id=student.id,
            store_item_id=goal_item.id,
            join_code=join_code,
            status='purchased'
        )
        db.session.add(si_teacher)
        db.session.commit()

        count = StudentItem.query.join(Student).filter(
            StudentItem.store_item_id == goal_item.id,
            Student.is_teacher == False
        ).count()
        assert count == 0

        # Regular student buys it (should contribute)
        si_regular = StudentItem(
            student_id=regular_student.id,
            store_item_id=goal_item.id,
            join_code=join_code,
            status='purchased'
        )
        db.session.add(si_regular)
        db.session.commit()

        count = StudentItem.query.join(Student).filter(
            StudentItem.store_item_id == goal_item.id,
            Student.is_teacher == False
        ).count()
        assert count == 1


def test_teacher_student_unique_identity_per_join_code(client, teacher, app):
    """
    Verify that a teacher claiming seats in two different classes
    gets two separate Student records with independent balances.

    This prevents the multi-tenancy leak where global dedup would
    link teacher seats across classes to the same Student record.
    """
    with app.app_context():
        teacher = db.session.merge(teacher)
        from app.routes.admin import _ensure_teacher_student_seat

        join_code_a = "TEACHER_CLASS_A"
        join_code_b = "TEACHER_CLASS_B"

        _ensure_teacher_student_seat(teacher.id, join_code_a, "A")
        _ensure_teacher_student_seat(teacher.id, join_code_b, "B")
        db.session.commit()

        # Claim seat in class A
        response = client.post('/student/claim-account', data={
            'join_code': join_code_a,
            'first_initial': 'T',
            'last_name': 'Student',
            'dob_sum': '2001-01-01'
        }, follow_redirects=True)
        assert response.status_code == 200

        tb_a = TeacherBlock.query.filter_by(
            teacher_id=teacher.id, join_code=join_code_a, is_teacher=True
        ).first()
        assert tb_a.is_claimed is True
        student_a = db.session.get(Student, tb_a.student_id)
        assert student_a is not None
        assert student_a.is_teacher is True

        # Complete setup for student A so it has completed_setup
        client.post('/student/create-username', data={'write_in_word': 'alpha'})
        client.post('/student/setup-pin-passphrase', data={
            'pin': '1234', 'passphrase': 'secure alpha'
        })

        # Claim seat in class B (should create a NEW Student record)
        response = client.post('/student/claim-account', data={
            'join_code': join_code_b,
            'first_initial': 'T',
            'last_name': 'Student',
            'dob_sum': '2001-01-01'
        }, follow_redirects=True)
        assert response.status_code == 200

        tb_b = TeacherBlock.query.filter_by(
            teacher_id=teacher.id, join_code=join_code_b, is_teacher=True
        ).first()
        assert tb_b.is_claimed is True
        student_b = db.session.get(Student, tb_b.student_id)
        assert student_b is not None
        assert student_b.is_teacher is True

        # CRITICAL: Two separate Student records
        assert student_a.id != student_b.id, (
            "Teacher seats in different classes must create separate Student records"
        )


def test_edit_student_ignores_dob_sum_field(client, teacher, app):
    """POST /admin/student/edit must not modify Student.dob_sum even when dob_sum is sent."""
    from app.models import TeacherBlock, StudentTeacher
    from app.hash_utils import get_random_salt
    from app.utils.claim_credentials import compute_primary_claim_hash

    with app.app_context():
        teacher = db.session.merge(teacher)
        teacher_id = teacher.id

        salt = get_random_salt()
        dob_sum = 2025
        first_half_hash = compute_primary_claim_hash('T', dob_sum, salt)

        student = Student(
            first_name='Testname',
            last_initial='S',
            block='A',
            salt=salt,
            dob_sum=dob_sum,
            first_half_hash=first_half_hash,
        )
        db.session.add(student)
        db.session.flush()

        join_code = 'DOBEDIT1'
        tb = TeacherBlock(
            teacher_id=teacher_id,
            block='A',
            first_name='Testname',
            last_initial='S',
            last_name_hash_by_part=[],
            dob_sum=dob_sum,
            salt=salt,
            first_half_hash=first_half_hash,
            join_code=join_code,
            is_claimed=False,
            student_id=student.id,
        )
        db.session.add(tb)
        db.session.add(StudentTeacher(student_id=student.id, admin_id=teacher_id))
        db.session.commit()

        student_id = student.id
        original_dob_sum = student.dob_sum
        original_first_half_hash = student.first_half_hash

    with client.session_transaction() as sess:
        sess['admin_id'] = teacher_id
        sess['current_join_code'] = join_code

    client.post('/admin/student/edit', data={
        'student_id': student_id,
        'first_name': 'Testname',
        'last_name': 'Student',
        'blocks': ['A'],
        'dob_sum': '2000-01-01',  # Attempt to mutate DOB — must be ignored
    }, follow_redirects=False)

    with app.app_context():
        updated = db.session.get(Student, student_id)
        assert updated.dob_sum == original_dob_sum, (
            "edit_student must not mutate Student.dob_sum"
        )
        assert updated.first_half_hash == original_first_half_hash, (
            "edit_student must not change first_half_hash when dob_sum was not modified"
        )
