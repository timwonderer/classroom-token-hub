"""
Tests for feature settings and teacher onboarding functionality.
"""
from tests.helpers.v2_fixtures import make_admin, make_sysadmin
import os
import pytest
import pyotp
from app import app, db
from app.models import Admin, ClassEconomy, ClassFeature, FeatureSettings, TeacherOnboarding, TeacherBlock


def _create_class_scope(admin, block='A', join_code='JOIN_A'):
    economy = ClassEconomy(
        join_code=join_code,
        teacher_id=admin.id,
        created_by_admin_id=admin.id,
        display_name=f'Period {block}',
    )
    db.session.add(economy)
    db.session.flush()
    db.session.add(TeacherBlock(
        teacher_id=admin.id,
        block=block,
        join_code=join_code,
        first_name='Test',
        last_initial='T',
        last_name_hash_by_part=[],
        dob_sum_hash=None,
        salt=b'salt',
        first_half_hash='hash',
    ))
    db.session.flush()
    return economy


@pytest.fixture
def test_admin():
    """Create a test admin for feature settings tests."""
    import pyotp
    admin = make_admin('test_teacher', pyotp.random_base32(),
    )
    db.session.add(admin)
    db.session.commit()
    return admin


class TestClassFeatures:
    """Tests for class feature row-existence semantics."""

    def test_class_feature_defaults(self, client, test_admin):
        """New classes start with payroll enabled and other features disabled."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        db.session.commit()

        enabled_names = ClassFeature.enabled_names_for_class(economy.class_id)
        assert enabled_names == {'payroll'}

    def test_feature_settings_to_dict_reads_class_features(self, client, test_admin):
        """Policy rows expose feature state from class_features."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        settings = FeatureSettings(
            teacher_id=test_admin.id,
            join_code='JOIN_A',
            class_id=economy.class_id,
            block='A',
        )
        db.session.add(settings)
        for row in ClassFeature.query.filter_by(class_id=economy.class_id).all():
            if row.feature_name in {"insurance", "rent"}:
                db.session.delete(row)
        db.session.commit()

        settings_dict = settings.to_dict()
        assert settings_dict['payroll_enabled'] is True
        assert settings_dict['insurance_enabled'] is False
        assert settings_dict['rent_enabled'] is False

    def test_class_features_per_period(self, client, test_admin):
        """Test that different periods can have different settings."""
        economy_a = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        economy_b = _create_class_scope(test_admin, block='B', join_code='JOIN_B')
        # Enable rent for class A only.
        db.session.add(ClassFeature(class_id=economy_a.class_id, feature_name='rent'))
        db.session.commit()

        settings_a = ClassFeature.feature_map_for_class(economy_a.class_id)
        settings_b = ClassFeature.feature_map_for_class(economy_b.class_id)
        assert settings_a['rent_enabled'] is True
        assert settings_b['rent_enabled'] is False
        assert settings_a['payroll_enabled'] is True
        assert settings_b['payroll_enabled'] is True

    def test_unique_constraint_class_feature(self, client, test_admin):
        """Duplicate feature rows for the same class are prevented."""
        economy = _create_class_scope(test_admin, block='A', join_code='JOIN_A')
        db.session.add(ClassFeature(class_id=economy.class_id, feature_name='payroll'))

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.session.commit()

        db.session.rollback()


class TestTeacherOnboarding:
    """Tests for the TeacherOnboarding model."""

    def test_onboarding_model_defaults(self, client, test_admin):
        """Test that TeacherOnboarding has correct defaults."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        assert onboarding.is_completed is False
        assert onboarding.is_skipped is False
        assert onboarding.current_step == 1
        assert onboarding.total_steps == 5
        assert onboarding.steps_completed == {}

    def test_mark_step_completed(self, client, test_admin):
        """Test marking steps as completed."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.mark_step_completed('welcome')
        onboarding.mark_step_completed('features')
        db.session.commit()

        assert onboarding.is_step_completed('welcome') is True
        assert onboarding.is_step_completed('features') is True
        assert onboarding.is_step_completed('periods') is False

    def test_complete_onboarding(self, client, test_admin):
        """Test completing onboarding."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.complete_onboarding()
        db.session.commit()

        assert onboarding.is_completed is True
        assert onboarding.completed_at is not None

    def test_skip_onboarding(self, client, test_admin):
        """Test skipping onboarding."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        onboarding.skip_onboarding()
        db.session.commit()

        assert onboarding.is_skipped is True
        assert onboarding.skipped_at is not None

    def test_needs_onboarding_property(self, client, test_admin):
        """Test the needs_onboarding property."""
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        # Initially needs onboarding
        assert onboarding.needs_onboarding is True

        # After completion, no longer needs it
        onboarding.complete_onboarding()
        db.session.commit()
        assert onboarding.needs_onboarding is False

    def test_unique_teacher_onboarding(self, client, test_admin):
        """Test that each teacher can only have one onboarding record."""
        onboarding1 = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding1)
        db.session.commit()

        # Try to add another onboarding for the same teacher
        onboarding2 = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            db.session.commit()

        db.session.rollback()


class TestFeatureSettingsRoutes:
    """Tests for feature settings routes."""

    def test_feature_settings_page_requires_login(self, client):
        """Test that feature settings page requires admin login."""
        response = client.get('/admin/feature-settings')
        assert response.status_code == 302  # Redirect to login

    def test_feature_settings_page_accessible_when_logged_in(self, client, test_admin):
        """Test that feature settings page is accessible when logged in."""
        with client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_id'] = test_admin.id

        response = client.get('/admin/feature-settings')
        assert response.status_code == 200


class TestOnboardingRoutes:
    """Tests for onboarding routes."""

    def test_onboarding_page_requires_login(self, client):
        """Test that onboarding page requires admin login."""
        response = client.get('/admin/onboarding')
        assert response.status_code == 302  # Redirect to login

    def test_onboarding_skip(self, client, test_admin):
        """Test skipping onboarding via API."""
        # Create onboarding record
        onboarding = TeacherOnboarding(teacher_id=test_admin.id)
        db.session.add(onboarding)
        db.session.commit()

        with client.session_transaction() as sess:
            sess['is_admin'] = True
            sess['admin_id'] = test_admin.id

        response = client.post('/admin/onboarding/skip',
                               content_type='application/json')
        assert response.status_code == 200

        data = response.get_json()
        assert data['status'] == 'success'

        # Verify onboarding was skipped
        onboarding = TeacherOnboarding.query.filter_by(
            teacher_id=test_admin.id
        ).first()
        assert onboarding.is_skipped is True


class TestTeacherDeletionCascade:
    """Tests for CASCADE deletion when a teacher is deleted."""

    def test_class_features_cascade_on_teacher_delete(self, client_with_fk):
        """Class features are removed when their teacher-owned class is deleted."""
        # Create a teacher
        admin = make_admin('cascade_test_teacher', pyotp.random_base32(),
        )
        db.session.add(admin)
        db.session.commit()
        teacher_id = admin.id

        economy_a = _create_class_scope(admin, block='A', join_code='TESTA1')
        economy_b = _create_class_scope(admin, block='B', join_code='TESTB1')
        db.session.commit()

        assert ClassFeature.query.join(ClassEconomy, ClassFeature.class_id == ClassEconomy.class_id).filter(
            ClassEconomy.teacher_id == teacher_id
        ).count() == 2

        # Delete the teacher
        db.session.delete(admin)
        db.session.commit()

        assert ClassFeature.query.join(ClassEconomy, ClassFeature.class_id == ClassEconomy.class_id).filter(
            ClassEconomy.teacher_id == teacher_id
        ).count() == 0

    def test_teacher_onboarding_cascade_on_teacher_delete(self, client_with_fk):
        """Test that TeacherOnboarding is CASCADE deleted when teacher is deleted."""
        # Create a teacher
        admin = make_admin('onboarding_cascade_test', pyotp.random_base32(),
        )
        db.session.add(admin)
        db.session.commit()
        teacher_id = admin.id

        # Create onboarding record for the teacher
        onboarding = TeacherOnboarding(teacher_id=teacher_id)
        db.session.add(onboarding)
        db.session.commit()

        # Verify onboarding exists
        assert TeacherOnboarding.query.filter_by(teacher_id=teacher_id).first() is not None

        # Delete the teacher
        db.session.delete(admin)
        db.session.commit()

        # Verify onboarding was CASCADE deleted
        assert TeacherOnboarding.query.filter_by(teacher_id=teacher_id).first() is None

    def test_teacher_blocks_cascade_on_teacher_delete(self, client_with_fk):
        """Test that TeacherBlocks are CASCADE deleted when teacher is deleted."""
        from app.models import ClassEconomy

        # Create a teacher
        admin = make_admin('blocks_cascade_test', pyotp.random_base32(),
        )
        db.session.add(admin)
        db.session.commit()
        teacher_id = admin.id

        # Ensure ClassEconomy exists for FK constraints
        if not db.session.get(ClassEconomy, 'TEST123'):
            db.session.add(ClassEconomy(join_code='TEST123', teacher_id=teacher_id, created_by_admin_id=teacher_id, display_name='Class TEST123'))
        if not db.session.get(ClassEconomy, 'TEST456'):
            db.session.add(ClassEconomy(join_code='TEST456', teacher_id=teacher_id, created_by_admin_id=teacher_id, display_name='Class TEST456'))
        db.session.commit()

        # Create teacher blocks
        # PIIEncryptedType will handle encryption automatically
        block1 = TeacherBlock(
            teacher_id=teacher_id,
            block='A',
            first_name='John',
            last_initial='D',
            last_name_hash_by_part=['hash1'],
            dob_sum_hash=None,
            salt=os.urandom(16),
            first_half_hash='test_hash_1',
            join_code='TEST123',
            is_claimed=False
        )
        block2 = TeacherBlock(
            teacher_id=teacher_id,
            block='B',
            first_name='Jane',
            last_initial='S',
            last_name_hash_by_part=['hash2'],
            dob_sum_hash=None,
            salt=os.urandom(16),
            first_half_hash='test_hash_2',
            join_code='TEST456',
            is_claimed=False
        )
        db.session.add(block1)
        db.session.add(block2)
        db.session.commit()

        # Verify blocks exist
        assert TeacherBlock.query.filter_by(teacher_id=teacher_id).count() == 2

        # Delete the teacher
        db.session.delete(admin)
        db.session.commit()

        # Verify teacher blocks were CASCADE deleted
        assert TeacherBlock.query.filter_by(teacher_id=teacher_id).count() == 0
