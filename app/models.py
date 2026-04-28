from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB, UUID
from datetime import datetime
import uuid
# DOM-IDEN-001: Identity & Class Binding

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    username_lookup_hash = db.Column(db.String(64), unique=True, nullable=False)
    passphrase_hash = db.Column(db.Text, nullable=False)
    totp_secret_encrypted = db.Column(db.Text, nullable=True)
    user_role = db.Column(db.String(20), nullable=False) # STUDENT, TEACHER, SYSADMIN
    current_session_nonce = db.Column(db.String(64), nullable=True)
    last_active_seat_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Class(db.Model):
    __tablename__ = 'classes'
    class_id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    join_code = db.Column(db.String(20), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=True)
    class_timezone = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class Seat(db.Model):
    __tablename__ = 'seats'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()), nullable=False, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    role = db.Column(db.String(20), nullable=False) # STUDENT, TEACHER
    roster_fingerprint = db.Column(db.String(128), nullable=True)
    dedupe_code = db.Column(db.String(8), nullable=True)
    claimed_at = db.Column(db.DateTime(timezone=True), nullable=True)

class IdentityProfile(db.Model):
    __tablename__ = 'identity_profiles'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), unique=True, nullable=False)
    profile_type = db.Column(db.String(32), nullable=False)
    first_name_encrypted = db.Column(db.Text, nullable=False)
    last_initial = db.Column(db.String(1), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class UserInviteToken(db.Model):
    __tablename__ = 'user_invite_tokens'
    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class UserRecoveryToken(db.Model):
    __tablename__ = 'user_recovery_tokens'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

# DOM-CLASS-001: Class Configuration

class ClassFeature(db.Model):
    __tablename__ = 'class_features'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    feature_name = db.Column(db.String(50), nullable=False)
    __table_args__ = (db.UniqueConstraint('class_id', 'feature_name'),)

class FeatureSettings(db.Model):
    __tablename__ = 'feature_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), unique=True, nullable=False)
    settings_payload = db.Column(JSONB, nullable=False)

class HallPassSettings(db.Model):
    __tablename__ = 'hall_pass_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), unique=True, nullable=False)
    default_daily_limit = db.Column(db.Integer, nullable=False)
    cost_per_pass_cents = db.Column(db.Integer, nullable=False)

class RentSettings(db.Model):
    __tablename__ = 'rent_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), unique=True, nullable=False)
    base_rent_cents = db.Column(db.Integer, nullable=False)
    late_fee_cents = db.Column(db.Integer, nullable=False)
    due_day_of_month = db.Column(db.Integer, nullable=False)

class PayrollSettings(db.Model):
    __tablename__ = 'payroll_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), unique=True, nullable=False)
    base_salary_cents = db.Column(db.Integer, nullable=False)
    payment_schedule = db.Column(db.String(20), nullable=False)

class PayrollReward(db.Model):
    __tablename__ = 'payroll_rewards'
    id = db.Column(db.Integer, primary_key=True)
    payroll_settings_id = db.Column(db.Integer, db.ForeignKey('payroll_settings.id'), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)

class PayrollFine(db.Model):
    __tablename__ = 'payroll_fines'
    id = db.Column(db.Integer, primary_key=True)
    payroll_settings_id = db.Column(db.Integer, db.ForeignKey('payroll_settings.id'), nullable=False)
    description = db.Column(db.String(100), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)

class BankingSettings(db.Model):
    __tablename__ = 'banking_settings'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), unique=True, nullable=False)
    interest_rate_percent = db.Column(db.Numeric(5, 2), nullable=False)

# DOM-ATT-001: Attendance & Mobility

class AttendanceSession(db.Model):
    __tablename__ = 'attendance_sessions'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    status = db.Column(db.String(10), nullable=False) # ACTIVE, INACTIVE
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False)
    reason_code = db.Column(db.String(50), nullable=True)

class HallPassLog(db.Model):
    __tablename__ = 'hall_pass_logs'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    status = db.Column(db.String(20), nullable=False) # PENDING, APPROVED, REJECTED, LEFT, RETURNED
    request_time = db.Column(db.DateTime(timezone=True), nullable=False)
    decision_time = db.Column(db.DateTime(timezone=True), nullable=True)
    left_time = db.Column(db.DateTime(timezone=True), nullable=True)
    return_time = db.Column(db.DateTime(timezone=True), nullable=True)

class SeatAttendanceState(db.Model):
    __tablename__ = 'seat_attendance_state'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), unique=True, nullable=False)
    tap_enabled = db.Column(db.Boolean, default=True, nullable=False)
    done_for_day_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

# DOM-OBL-001: Obligations & Entitlements

class AssessmentEvent(db.Model):
    __tablename__ = 'assessment_events'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class ObligationLifecycle(db.Model):
    __tablename__ = 'obligation_lifecycle'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    status = db.Column(db.String(20), nullable=False) # PAID, OVERDUE, REVERSED
    idempotency_key = db.Column(db.String(100), unique=True, nullable=False)

class ObligationSatisfaction(db.Model):
    __tablename__ = 'obligation_satisfaction'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    method = db.Column(db.String(20), nullable=False) # PAYMENT, WAIVER
    idempotency_key = db.Column(db.String(100), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class ObligationReversal(db.Model):
    __tablename__ = 'obligation_reversal'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)

class EntitlementEvent(db.Model):
    __tablename__ = 'entitlement_events'
    id = db.Column(db.Integer, primary_key=True)
    seat_id = db.Column(db.Integer, db.ForeignKey('seats.id'), nullable=False)
    class_id = db.Column(db.String(36), db.ForeignKey('classes.class_id'), nullable=False)
    entitlement_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, nullable=False)

