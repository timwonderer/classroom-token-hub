"""
Tests for Economy API endpoints.

Tests the /api/economy/* endpoints to ensure they correctly use
expected_weekly_hours from payroll_settings rather than hardcoded values.
"""
import pytest
from datetime import datetime, timezone
from app import db
from app.models import Admin, PayrollSettings
from app.utils.economy_balance import EconomyBalanceChecker, WarningLevel


@pytest.fixture
def admin_with_payroll(client):
    """Create an admin with payroll settings for testing."""
    # Create admin
    admin = Admin(
        username="testeconomyadmin",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(admin)
    db.session.flush()

    # Create payroll settings with specific expected_weekly_hours
    payroll_settings = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=0.25,  # $0.25/min = $15/hour
        expected_weekly_hours=8.0,  # Custom value, not 5.0
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True
    )
    db.session.add(payroll_settings)
    db.session.commit()

    return admin, payroll_settings


@pytest.fixture
def logged_in_admin_client(client, admin_with_payroll):
    """A client with a logged-in admin."""
    admin, _ = admin_with_payroll
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()
    return client


def test_validate_endpoint_uses_payroll_settings_hours(logged_in_admin_client, admin_with_payroll):
    """Test that /api/economy/validate reads expected_weekly_hours from payroll_settings."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test validation endpoint - should use expected_weekly_hours from payroll_settings (8.0)
    response = client.post(
        '/admin/api/economy/validate/rent',
        json={
            'value': 100.0,
            'frequency_type': 'weekly'
            # Note: NOT sending expected_weekly_hours
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.get_json()
    assert data['status'] in ['success', 'warning']
    assert 'cwi' in data
    assert 'cwi_breakdown' in data

    # Verify the expected_weekly_hours in breakdown matches payroll_settings
    breakdown = data['cwi_breakdown']
    assert 'expected_weekly_hours' in breakdown
    assert breakdown['expected_weekly_hours'] == 8.0, \
        f"Expected 8.0 hours from payroll_settings, got {breakdown['expected_weekly_hours']}"

    # Verify CWI is calculated correctly with 8 hours
    # CWI = pay_rate_per_minute * expected_weekly_minutes
    # CWI = 0.25 * (8.0 * 60) = 0.25 * 480 = 120.0
    expected_cwi = 0.25 * 8.0 * 60
    assert abs(data['cwi'] - expected_cwi) < 0.01, \
        f"Expected CWI {expected_cwi}, got {data['cwi']}"


def test_validate_endpoint_not_hardcoded_5_hours(logged_in_admin_client, admin_with_payroll):
    """Test that validation doesn't use hardcoded 5.0 hours."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    response = client.post(
        '/admin/api/economy/validate/store_item',
        json={'value': 10.0}
    )

    assert response.status_code == 200
    data = response.get_json()

    # CWI with 8 hours should be 120.0, not 75.0 (which would be 5 hours)
    assert abs(data['cwi'] - 120.0) < 0.01, \
        f"CWI should be 120.0 (8 hours), not {data['cwi']} (suggests hardcoded 5 hours)"


def test_analyze_endpoint_uses_payroll_settings_hours(logged_in_admin_client, admin_with_payroll):
    """Test that /api/economy/analyze reads expected_weekly_hours from payroll_settings."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test analyze endpoint - should use expected_weekly_hours from payroll_settings (8.0)
    response = client.post(
        '/admin/api/economy/analyze',
        json={
            'block': 'A'
            # Note: NOT sending expected_weekly_hours
        }
    )

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = response.get_json()
    assert data['status'] == 'success'
    assert 'cwi' in data
    assert 'cwi_breakdown' in data

    # Verify the expected_weekly_hours in breakdown matches payroll_settings
    breakdown = data['cwi_breakdown']
    assert 'expected_weekly_hours' in breakdown
    assert breakdown['expected_weekly_hours'] == 8.0, \
        f"Expected 8.0 hours from payroll_settings, got {breakdown['expected_weekly_hours']}"

    # Verify CWI calculation
    expected_cwi = 0.25 * 8.0 * 60  # 120.0
    assert abs(data['cwi'] - expected_cwi) < 0.01


def test_analyze_endpoint_override_hours(logged_in_admin_client, admin_with_payroll):
    """Test that /api/economy/analyze accepts override when explicitly provided."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test with explicit override to 10 hours
    response = client.post(
        '/admin/api/economy/analyze',
        json={
            'block': 'A',
            'expected_weekly_hours': 10.0  # Override value
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should use the override value (10.0), not payroll_settings (8.0)
    breakdown = data['cwi_breakdown']
    assert breakdown['expected_weekly_hours'] == 10.0, \
        f"Expected override value 10.0, got {breakdown['expected_weekly_hours']}"

    # Verify CWI with override
    expected_cwi = 0.25 * 10.0 * 60  # 150.0
    assert abs(data['cwi'] - expected_cwi) < 0.01


def test_analyze_endpoint_null_override_uses_payroll(logged_in_admin_client, admin_with_payroll):
    """Test that null expected_weekly_hours falls back to payroll_settings."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test with explicit null - should fall back to payroll_settings
    response = client.post(
        '/admin/api/economy/analyze',
        json={
            'block': 'A',
            'expected_weekly_hours': None
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should use payroll_settings value (8.0), not null
    breakdown = data['cwi_breakdown']
    assert breakdown['expected_weekly_hours'] == 8.0, \
        f"Expected payroll_settings value 8.0 when override is null, got {breakdown['expected_weekly_hours']}"


def test_different_expected_hours_per_block(client):
    """Test that different blocks can have different expected_weekly_hours."""
    # Create admin
    admin = Admin(
        username="testmultiblock",
        totp_secret="TESTSECRET123456"
    )
    db.session.add(admin)
    db.session.flush()

    # Create payroll settings for different blocks with different hours
    payroll_a = PayrollSettings(
        teacher_id=admin.id,
        block="A",
        pay_rate=0.25,
        expected_weekly_hours=5.0,  # Block A: 5 hours
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True
    )

    payroll_b = PayrollSettings(
        teacher_id=admin.id,
        block="B",
        pay_rate=0.25,
        expected_weekly_hours=10.0,  # Block B: 10 hours
        payroll_frequency_days=14,
        settings_mode='simple',
        is_active=True
    )

    db.session.add(payroll_a)
    db.session.add(payroll_b)
    db.session.commit()

    # Login as admin
    with client.session_transaction() as sess:
        sess['is_admin'] = True
        sess['admin_id'] = admin.id
        sess['is_system_admin'] = False
        sess['last_activity'] = datetime.now(timezone.utc).isoformat()

    # Test Block A
    response_a = client.post(
        '/admin/api/economy/analyze',
        json={'block': 'A'}
    )
    assert response_a.status_code == 200
    data_a = response_a.get_json()
    assert data_a['cwi_breakdown']['expected_weekly_hours'] == 5.0
    assert abs(data_a['cwi'] - (0.25 * 5.0 * 60)) < 0.01  # 75.0

    # Test Block B
    response_b = client.post(
        '/admin/api/economy/analyze',
        json={'block': 'B'}
    )
    assert response_b.status_code == 200
    data_b = response_b.get_json()
    assert data_b['cwi_breakdown']['expected_weekly_hours'] == 10.0
    assert abs(data_b['cwi'] - (0.25 * 10.0 * 60)) < 0.01  # 150.0


def test_validate_rent_with_monthly_frequency(logged_in_admin_client, admin_with_payroll):
    """Test that monthly rent recommendations are correctly calculated per AGENTS spec."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Test with monthly rent of $440
    # CWI = 0.25 * 8 * 60 = 120.0 per week
    # Per AGENTS spec: monthly rent ratios are 2.0-2.5x CWI (weekly)
    # Recommended MONTHLY rent range: $240 - $300 (2.0-2.5 × $120 weekly CWI)
    # Weekly equivalent: $240/4.348 = ~$55.20/week to $300/4.348 = ~$69.00/week
    response = client.post(
        '/admin/api/economy/validate/rent',
        json={
            'value': 440.0,
            'frequency_type': 'monthly'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Verify CWI is calculated correctly
    expected_cwi = 0.25 * 8.0 * 60  # 120.0 per week
    assert abs(data['cwi'] - expected_cwi) < 0.01

    # Verify recommendations are MONTHLY values per AGENTS spec
    # Monthly rent_min = 2.0 * CWI (weekly) = 2.0 * 120 = 240
    recommendations = data['recommendations']
    assert abs(recommendations['min'] - (expected_cwi * 2.0)) < 0.01  # 240.0 per month
    assert abs(recommendations['max'] - (expected_cwi * 2.5)) < 0.01  # 300.0 per month
    assert abs(recommendations['recommended'] - (expected_cwi * 2.25)) < 0.01  # 270.0 per month

    # Monthly rent of $440 is ABOVE the recommended maximum of $300/month
    assert data['status'] == 'warning'
    assert len(data['warnings']) > 0
    warning_msg = data['warnings'][0]['message'].lower()
    # Warning should mention "per month" since that's the input frequency
    assert 'per month' in warning_msg or 'month' in warning_msg


def test_validate_insurance_premium_only(logged_in_admin_client, admin_with_payroll):
    """Test insurance premium validation without coverage parameters."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # CWI = 0.25 * 8 * 60 = 120.0 per week
    # Per AGENTS spec: insurance premium should be 5-12% of CWI
    # Recommended range: $6.00 - $14.40 per week
    
    # Test with balanced premium ($10/week is ~8.3% of CWI)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Verify CWI calculation
    expected_cwi = 0.25 * 8.0 * 60  # 120.0 per week
    assert abs(data['cwi'] - expected_cwi) < 0.01

    # Verify recommendations are provided
    recommendations = data['recommendations']
    assert abs(recommendations['min'] - (expected_cwi * 0.05)) < 0.01  # $6.00
    assert abs(recommendations['max'] - (expected_cwi * 0.12)) < 0.01  # $14.40
    assert abs(recommendations['recommended'] - (expected_cwi * 0.08)) < 0.01  # $9.60

    # Premium of $10/week should be within acceptable range
    assert data['status'] in ['success', 'warning']
    assert any('balanced' in w['message'].lower() for w in data['warnings'])


def test_validate_insurance_premium_too_high(logged_in_admin_client, admin_with_payroll):
    """Test insurance premium that exceeds maximum ratio."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # CWI = 120.0, max premium should be 12% = $14.40
    # Test with $20/week (16.7% of CWI - too high)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 20.0,
            'frequency': 'weekly'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should get a critical warning
    assert data['status'] in ['error', 'warning']
    critical_warnings = [w for w in data['warnings'] if w.get('level') == 'critical']
    assert len(critical_warnings) > 0
    assert any('too expensive' in w['message'].lower() for w in critical_warnings)


def test_validate_insurance_premium_too_low(logged_in_admin_client, admin_with_payroll):
    """Test insurance premium that is below minimum ratio."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # CWI = 120.0, min premium should be 5% = $6.00
    # Test with $3/week (2.5% of CWI - too low)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 3.0,
            'frequency': 'weekly'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should get a warning
    assert data['status'] == 'warning'
    assert any('too low' in w['message'].lower() for w in data['warnings'])


def test_validate_insurance_with_coverage_balanced(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with balanced coverage (3-5x premium)."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week
    # Coverage should be 3-5x = $30-$50
    # Test with $40 (4x premium - balanced)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_claim_amount': 40.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have success message for coverage
    coverage_warnings = [w for w in data['warnings'] if 'claim' in w['message'].lower()]
    assert len(coverage_warnings) > 0
    assert any('balanced' in w['message'].lower() and 'claim' in w['message'].lower() 
               for w in coverage_warnings)


def test_validate_insurance_with_coverage_too_low(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with coverage below 3x premium."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week
    # Coverage should be at least 3x = $30
    # Test with $20 (2x premium - too low)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_claim_amount': 20.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have warning for low coverage
    coverage_warnings = [w for w in data['warnings'] if 'claim' in w['message'].lower() and 'low' in w['message'].lower()]
    assert len(coverage_warnings) > 0


def test_validate_insurance_with_coverage_too_high(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with coverage exceeding 5x premium."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week
    # Coverage should be at most 5x = $50
    # Test with $70 (7x premium - too high)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_claim_amount': 70.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have warning for high coverage
    coverage_warnings = [w for w in data['warnings'] if 'claim' in w['message'].lower() and 'exceed' in w['message'].lower()]
    assert len(coverage_warnings) > 0


def test_validate_insurance_with_period_cap_balanced(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with balanced period cap (6-10x premium)."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week
    # Period cap should be 6-10x = $60-$100
    # Test with $80 (8x premium - balanced)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_payout_per_period': 80.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have success message for period cap
    period_warnings = [w for w in data['warnings'] if 'period' in w['message'].lower()]
    assert len(period_warnings) > 0
    assert any('balanced' in w['message'].lower() and 'period' in w['message'].lower() 
               for w in period_warnings)


def test_validate_insurance_with_period_cap_too_low(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with period cap below 6x premium."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week
    # Period cap should be at least 6x = $60
    # Test with $40 (4x premium - too low)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_payout_per_period': 40.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have warning for low period cap
    period_warnings = [w for w in data['warnings'] if 'period' in w['message'].lower() and 'too low' in w['message'].lower()]
    assert len(period_warnings) > 0


def test_validate_insurance_with_period_cap_too_high(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with period cap exceeding 10x premium."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week
    # Period cap should be at most 10x = $100
    # Test with $120 (12x premium - too high)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_payout_per_period': 120.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have warning for high period cap
    period_warnings = [w for w in data['warnings'] if 'period' in w['message'].lower() and 'exceed' in w['message'].lower()]
    assert len(period_warnings) > 0


def test_validate_insurance_with_all_parameters(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with premium, coverage, and period cap all specified."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Premium: $10/week (balanced)
    # Coverage: $40 (4x premium - balanced)
    # Period cap: $80 (8x premium - balanced)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_claim_amount': 40.0,
            'max_payout_per_period': 80.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should have success/info messages for all three validations
    assert data['status'] in ['success', 'warning']
    
    # Check for premium validation message
    premium_warnings = [w for w in data['warnings'] if 'premium' in w['message'].lower() and 'balanced' in w['message'].lower()]
    assert len(premium_warnings) > 0
    
    # Check for coverage validation message
    coverage_warnings = [w for w in data['warnings'] if 'claim' in w['message'].lower() and 'balanced' in w['message'].lower()]
    assert len(coverage_warnings) > 0
    
    # Check for period cap validation message
    period_warnings = [w for w in data['warnings'] if 'period' in w['message'].lower() and 'balanced' in w['message'].lower()]
    assert len(period_warnings) > 0


def test_validate_insurance_non_monetary_skips_coverage(logged_in_admin_client, admin_with_payroll):
    """Test that non-monetary insurance policies don't validate coverage parameters."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # For non-monetary policies, coverage parameters should be ignored
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 10.0,
            'frequency': 'weekly',
            'max_claim_amount': 1000.0,  # Unrealistic value
            'max_payout_per_period': 5000.0,  # Unrealistic value
            'claim_type': 'non_monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should only validate premium, not coverage or period cap
    warnings = data['warnings']
    coverage_warnings = [w for w in warnings if 'claim' in w['message'].lower() or 'period' in w['message'].lower()]
    # Non-monetary policies should not generate coverage/period warnings
    assert len(coverage_warnings) == 0


def test_validate_insurance_monthly_frequency(logged_in_admin_client, admin_with_payroll):
    """Test insurance validation with monthly frequency."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # CWI = 120.0/week
    # Monthly premium should be ~5-12% of weekly CWI * 4.348 weeks/month
    # Range: ~$26.09 - $62.62 per month
    # Test with $40/month (reasonable)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 40.0,
            'frequency': 'monthly'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Should accept this as reasonable
    assert data['status'] in ['success', 'warning']
    
    # Recommendations should be in monthly terms
    recommendations = data['recommendations']
    assert recommendations['frequency'] == 'monthly'
    assert recommendations['min'] > 20  # Should be around $26
    assert recommendations['max'] < 70  # Should be around $62


def test_validate_insurance_with_coverage_monthly_frequency(logged_in_admin_client, admin_with_payroll):
    """Test insurance coverage validation scales correctly with monthly frequency."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    # Monthly premium: $40
    # Coverage should be 3-5x monthly premium = $120-$200
    # Test with $150 (3.75x premium - balanced)
    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 40.0,
            'frequency': 'monthly',
            'max_claim_amount': 150.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    # Coverage should be validated against monthly premium (not weekly)
    coverage_warnings = [w for w in data['warnings'] if 'claim' in w['message'].lower() and 'balanced' in w['message'].lower()]
    assert len(coverage_warnings) > 0


def test_validate_insurance_with_period_cap_monthly_frequency(logged_in_admin_client, admin_with_payroll):
    """Test insurance period cap validation scales correctly with monthly frequency."""
    admin, payroll_settings = admin_with_payroll
    client = logged_in_admin_client

    response = client.post(
        '/admin/api/economy/validate/insurance',
        json={
            'value': 40.0,
            'frequency': 'monthly',
            'max_payout_per_period': 300.0,
            'claim_type': 'monetary'
        }
    )

    assert response.status_code == 200
    data = response.get_json()

    period_warnings = [w for w in data['warnings'] if 'period cap is balanced' in w['message'].lower()]
    assert len(period_warnings) > 0


def test_check_insurance_balance_uses_frequency_premium_for_limits():
    """Ensure coverage and period caps are evaluated against stored premium frequency."""
    checker = EconomyBalanceChecker(teacher_id=1)

    class FakePolicy:
        def __init__(self):
            self.title = "Monthly Health"
            self.premium = 40.0  # monthly premium
            self.charge_frequency = 'monthly'
            self.claim_type = 'monetary'
            self.max_claim_amount = 150.0  # 3.75x monthly premium
            self.max_payout_per_period = 300.0  # 7.5x monthly premium
            self.is_active = True

    policy = FakePolicy()
    warnings = checker.check_insurance_balance([policy], cwi=120.0)

    coverage_warning = next((w for w in warnings if w.feature.startswith("Coverage")), None)
    period_warning = next((w for w in warnings if w.feature.startswith("Period Cap")), None)

    assert coverage_warning is not None
    assert period_warning is not None

    # Recommendations should be based on the monthly premium (not normalized weekly value)
    assert coverage_warning.recommended_min == policy.premium * checker.COVERAGE_MIN_MULTIPLIER
    assert coverage_warning.recommended_max == policy.premium * checker.COVERAGE_MAX_MULTIPLIER
    assert coverage_warning.level == WarningLevel.INFO

    assert period_warning.recommended_min == policy.premium * checker.PERIOD_MIN_MULTIPLIER
    assert period_warning.recommended_max == policy.premium * checker.PERIOD_MAX_MULTIPLIER
    assert period_warning.level == WarningLevel.INFO
