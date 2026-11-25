CREATE TYPE public.ledger_mechanism_enum AS ENUM (
    'self',
    'teacher',
    'system'
);

CREATE TYPE public.recovery_request_status_enum AS ENUM (
    'pending',
    'verified',
    'expired',
    'cancelled'
);

CREATE TYPE public.transactionstatus AS ENUM (
    'PENDING',
    'POSTED',
    'VOID'
);

CREATE TYPE public.user_role_enum AS ENUM (
    'student',
    'teacher',
    'sysadmin'
);

CREATE TABLE public.actor_request_trace (
    id integer NOT NULL,
    actor_type character varying(20) NOT NULL,
    actor_public_id character varying(64) NOT NULL,
    class_id character varying(36) NOT NULL,
    request_id character varying(128) NOT NULL,
    method character varying(10) NOT NULL,
    endpoint character varying(500) NOT NULL,
    status_code integer,
    created_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.actor_request_trace_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.actor_request_trace_id_seq OWNED BY public.actor_request_trace.id;

CREATE TABLE public.announcements (
    id integer NOT NULL,
    created_by_seat_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    title character varying(200) NOT NULL,
    message text NOT NULL,
    is_active boolean NOT NULL,
    priority character varying(20) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone
);

CREATE SEQUENCE public.announcements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.announcements_id_seq OWNED BY public.announcements.id;

CREATE TABLE public.assessment_events (
    id integer NOT NULL,
    seat_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    internal_ref character varying(200) NOT NULL,
    correlation_id character varying(200) NOT NULL,
    source_correlation_id character varying(200),
    event_type character varying(20) NOT NULL,
    obligation_type character varying(30) NOT NULL,
    policy_uuid character varying(36),
    policy_version_id integer,
    "timestamp" timestamp with time zone NOT NULL,
    bill_cycle_id integer,
    ledger_transaction_id integer,
    notes text
);

CREATE SEQUENCE public.assessment_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.assessment_events_id_seq OWNED BY public.assessment_events.id;

CREATE TABLE public.attendance_sessions (
    id integer NOT NULL,
    target_seat_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    actor_seat_id integer NOT NULL,
    mechanism character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    reason_code character varying(32) NOT NULL,
    hall_pass_id character varying(100),
    "timestamp" timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.attendance_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.attendance_sessions_id_seq OWNED BY public.attendance_sessions.id;

CREATE TABLE public.audit_events (
    id integer NOT NULL,
    chain_scope character varying(64) NOT NULL,
    sequence_number integer NOT NULL,
    previous_hash character varying(64) NOT NULL,
    event_hash character varying(64) NOT NULL,
    table_name character varying(64) NOT NULL,
    row_pk character varying(64) NOT NULL,
    operation character varying(16) NOT NULL,
    actor_type character varying(32),
    actor_id_hash character varying(64),
    class_id character varying(36),
    seat_id integer,
    feat_id character varying(32),
    idempotency_key character varying(128),
    correlation_id character varying(64),
    request_id character varying(64),
    payload_digest character varying(64) NOT NULL,
    context_digest character varying(64) NOT NULL,
    created_at_utc timestamp with time zone NOT NULL,
    signer_key_id character varying(16) NOT NULL,
    signature_version integer NOT NULL,
    hmac_signature character varying(64) NOT NULL
);

CREATE SEQUENCE public.audit_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.audit_events_id_seq OWNED BY public.audit_events.id;

CREATE TABLE public.bill_cycles (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    internal_ref character varying(200) NOT NULL,
    cycle_number integer NOT NULL,
    policy_uuid character varying(36),
    source_version_id character varying(200),
    cycle_boundary_at timestamp with time zone NOT NULL,
    next_assessment_at timestamp with time zone,
    grace_boundary_at timestamp with time zone
);

CREATE SEQUENCE public.bill_cycles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.bill_cycles_id_seq OWNED BY public.bill_cycles.id;

CREATE TABLE public.chain_heads (
    chain_scope character varying(64) NOT NULL,
    latest_hash character varying(64) NOT NULL,
    latest_sequence integer NOT NULL,
    event_count integer NOT NULL,
    last_updated_utc timestamp with time zone NOT NULL
);

CREATE TABLE public.class_features (
    class_id character varying(36) NOT NULL,
    feature character varying(32) NOT NULL,
    economic_version_id character varying(36),
    effective_at timestamp with time zone NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_class_features_feature CHECK ((feature IN ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')))
);

CREATE TABLE public.classes (
    class_id character varying(36) NOT NULL,
    class_public_id character varying(36) NOT NULL,
    join_code character varying(20) NOT NULL,
    section character varying(50),
    teacher_user_id integer,
    display_name character varying(100),
    class_timezone character varying(64) NOT NULL,
    created_at timestamp with time zone NOT NULL
);

CREATE TABLE public.economic_engine (
    economic_version_id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    previous_version_id character varying(36),
    expected_weekly_hours double precision,
    interest_rate numeric(8,6),
    interest_calculation_type character varying(20),
    compound_frequency character varying(20),
    interest_accrual_frequency character varying(20),
    interest_payout_frequency character varying(20),
    flat_overdraft_fee numeric(12,2),
    progressive_overdraft_fee json,
    overdraft_protection_enabled boolean,
    economy_policy_mode character varying(20) DEFAULT 'default'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_economic_engine_accrual_freq CHECK (((interest_accrual_frequency IS NULL) OR (interest_accrual_frequency IN ('daily', 'weekly', 'monthly')))),
    CONSTRAINT ck_economic_engine_calc_type CHECK (((interest_calculation_type IS NULL) OR (interest_calculation_type IN ('simple', 'compound')))),
    CONSTRAINT ck_economic_engine_compound_freq CHECK (((compound_frequency IS NULL) OR (compound_frequency IN ('never', 'daily', 'weekly', 'monthly')))),
    CONSTRAINT ck_economic_engine_flat_overdraft_fee CHECK (((flat_overdraft_fee IS NULL) OR (flat_overdraft_fee >= (0)::numeric))),
    CONSTRAINT ck_economic_engine_hours CHECK (((expected_weekly_hours IS NULL) OR (expected_weekly_hours > (0)::double precision))),
    CONSTRAINT ck_economic_engine_mode CHECK ((economy_policy_mode IN ('tight', 'default', 'comfortable'))),
    CONSTRAINT ck_economic_engine_overdraft_fee_exclusive CHECK ((NOT ((flat_overdraft_fee IS NOT NULL) AND (progressive_overdraft_fee IS NOT NULL)))),
    CONSTRAINT ck_economic_engine_payout_freq CHECK (((interest_payout_frequency IS NULL) OR (interest_payout_frequency IN ('weekly', 'monthly')))),
    CONSTRAINT ck_economic_engine_rate CHECK (((interest_rate IS NULL) OR ((interest_rate >= (0)::numeric) AND (interest_rate <= 1.0))))
);

CREATE TABLE public.entitlement_events (
    event_id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    entitlement_id character varying(36) NOT NULL,
    target_seat_id integer NOT NULL,
    actor_seat_id integer NOT NULL,
    product_id character varying(36),
    entitlement_type character varying(50) NOT NULL,
    acquisition_type character varying(20) NOT NULL,
    event_type character varying(20) NOT NULL,
    correlation_id character varying(200),
    payload json,
    "timestamp" timestamp with time zone NOT NULL
);

CREATE TABLE public.feature_settings (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    economy_policy_mode character varying(20) NOT NULL,
    economy_policy_updated_at timestamp with time zone NOT NULL,
    economy_policy_alignment_status character varying(32),
    economy_last_rebalanced_at timestamp with time zone,
    economy_last_rebalanced_by integer,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);

CREATE SEQUENCE public.feature_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.feature_settings_id_seq OWNED BY public.feature_settings.id;

CREATE TABLE public.hall_pass_logs (
    id integer NOT NULL,
    requested_by_seat_id integer NOT NULL,
    approved_by_seat_id integer NOT NULL,
    correlation_id character varying(100) NOT NULL,
    policy_uuid character varying(36) NOT NULL,
    hall_pass_id character varying(100),
    destination character varying(255),
    class_id character varying(36) NOT NULL,
    "timestamp" timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.hall_pass_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.hall_pass_logs_id_seq OWNED BY public.hall_pass_logs.id;

CREATE TABLE public.hall_pass_settings (
    id integer NOT NULL,
    policy_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    availability_state character varying(16) DEFAULT 'IN_USE'::character varying NOT NULL,
    max_queue_limit integer NOT NULL,
    pass_type_payload json NOT NULL,
    effective_date timestamp with time zone NOT NULL,
    CONSTRAINT ck_hall_pass_settings_availability CHECK ((availability_state IN ('IN_USE', 'HIDDEN', 'RETIRED')))
);

CREATE SEQUENCE public.hall_pass_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.hall_pass_settings_id_seq OWNED BY public.hall_pass_settings.id;

CREATE TABLE public.identity_profiles (
    id integer NOT NULL,
    seat_id integer,
    class_id character varying(36),
    profile_type character varying(32) NOT NULL,
    first_name bytea NOT NULL,
    last_name bytea NOT NULL,
    notes bytea,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.identity_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.identity_profiles_id_seq OWNED BY public.identity_profiles.id;

CREATE TABLE public.insurance_claim_productivity_dates (
    id integer NOT NULL,
    claim_id character varying(36) NOT NULL,
    entitlement_id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    claim_date date NOT NULL,
    student_claimed_hours numeric(6,2) NOT NULL,
    student_explanation text NOT NULL,
    teacher_approved_hours numeric(6,2),
    adjustment_note text,
    recognized_payout numeric(12,2)
);

CREATE SEQUENCE public.insurance_claim_productivity_dates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.insurance_claim_productivity_dates_id_seq OWNED BY public.insurance_claim_productivity_dates.id;

CREATE TABLE public.insurance_claims (
    claim_id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    entitlement_id character varying(36) NOT NULL,
    target_seat_id integer NOT NULL,
    actor_seat_id integer NOT NULL,
    status character varying(20) NOT NULL,
    correlation_id character varying(200) NOT NULL,
    claim_basis json NOT NULL,
    submitted_at timestamp with time zone NOT NULL,
    decided_by_seat_id integer,
    decided_at timestamp with time zone,
    decision_note text,
    filing_window_override_reason text,
    result_amount numeric(12,2),
    payroll_event_id integer,
    ledger_transaction_id integer
);

CREATE TABLE public.insurance_policies (
    policy_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    insurance_type character varying(20) NOT NULL,
    tier_level integer,
    premium numeric(12,2) NOT NULL,
    charge_frequency character varying(20) NOT NULL,
    reimbursement_percentage numeric(5,2),
    payout_multiple numeric(6,2),
    claims_per_week_equivalent numeric(6,3),
    claim_window_days integer,
    claimable_dates_per_week_equivalent numeric(6,3),
    waiting_period_days integer,
    bill_preview_days integer,
    nonpayment_mode character varying(24),
    cancel_after_days integer,
    title character varying(120),
    description text,
    tier_name character varying(60),
    tier_group character varying(60),
    availability_state character varying(16) DEFAULT 'IN_USE'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    created_by_seat_id integer,
    retired_at timestamp with time zone,
    CONSTRAINT ck_insurance_policies_availability CHECK ((availability_state IN ('IN_USE', 'HIDDEN', 'RETIRED'))),
    CONSTRAINT ck_insurance_policies_claim_window_nonneg CHECK (((claim_window_days IS NULL) OR (claim_window_days >= 0))),
    CONSTRAINT ck_insurance_policies_claimable_dates_nonneg CHECK (((claimable_dates_per_week_equivalent IS NULL) OR (claimable_dates_per_week_equivalent >= (0)::numeric))),
    CONSTRAINT ck_insurance_policies_claims_per_week_nonneg CHECK (((claims_per_week_equivalent IS NULL) OR (claims_per_week_equivalent >= (0)::numeric))),
    CONSTRAINT ck_insurance_policies_frequency CHECK ((charge_frequency IN ('WEEKLY', 'MONTHLY'))),
    CONSTRAINT ck_insurance_policies_payout_multiple_nonneg CHECK (((payout_multiple IS NULL) OR (payout_multiple >= (0)::numeric))),
    CONSTRAINT ck_insurance_policies_premium_nonneg CHECK ((premium >= (0)::numeric)),
    CONSTRAINT ck_insurance_policies_reimbursement_range CHECK (((reimbursement_percentage IS NULL) OR ((reimbursement_percentage >= (0)::numeric) AND (reimbursement_percentage <= (100)::numeric)))),
    CONSTRAINT ck_insurance_policies_tier_level_nonneg CHECK (((tier_level IS NULL) OR (tier_level >= 0))),
    CONSTRAINT ck_insurance_policies_type CHECK ((insurance_type IN ('TRANSACTION', 'PRODUCTIVITY', 'NON_MONETARY'))),
    CONSTRAINT ck_insurance_policies_type_subset CHECK (((((insurance_type)::text = 'TRANSACTION'::text) AND (reimbursement_percentage IS NOT NULL) AND (payout_multiple IS NOT NULL) AND (claims_per_week_equivalent IS NOT NULL) AND (claim_window_days IS NOT NULL) AND (claimable_dates_per_week_equivalent IS NULL)) OR (((insurance_type)::text = 'PRODUCTIVITY'::text) AND (reimbursement_percentage IS NOT NULL) AND (payout_multiple IS NOT NULL) AND (claimable_dates_per_week_equivalent IS NOT NULL) AND (claims_per_week_equivalent IS NULL) AND (claim_window_days IS NULL)) OR (((insurance_type)::text = 'NON_MONETARY'::text) AND (claims_per_week_equivalent IS NOT NULL) AND (waiting_period_days IS NOT NULL) AND (reimbursement_percentage IS NULL) AND (payout_multiple IS NULL) AND (claim_window_days IS NULL) AND (claimable_dates_per_week_equivalent IS NULL)))),
    CONSTRAINT ck_insurance_policies_waiting_period_nonneg CHECK (((waiting_period_days IS NULL) OR (waiting_period_days >= 0)))
);

CREATE TABLE public.interpretation_cycle_record (
    id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    payroll_cycle_id character varying(36) NOT NULL,
    cycle_started_at timestamp with time zone NOT NULL,
    cycle_completed_at timestamp with time zone NOT NULL,
    computed_at timestamp with time zone NOT NULL,
    reference_configuration jsonb NOT NULL,
    observations_json jsonb NOT NULL
);

CREATE TABLE public.issue_categories (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    category_type character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    display_order integer,
    created_at timestamp with time zone
);

CREATE SEQUENCE public.issue_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.issue_categories_id_seq OWNED BY public.issue_categories.id;

CREATE TABLE public.issue_resolution_actions (
    id integer NOT NULL,
    issue_id integer NOT NULL,
    class_public_id character varying(36),
    action_type character varying(100) NOT NULL,
    action_description text,
    performed_by_type character varying(20) NOT NULL,
    performed_by_public_id character varying(64),
    related_transaction_id integer,
    amount_changed double precision,
    before_value text,
    after_value text,
    created_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.issue_resolution_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.issue_resolution_actions_id_seq OWNED BY public.issue_resolution_actions.id;

CREATE TABLE public.issue_status_history (
    id integer NOT NULL,
    issue_id integer NOT NULL,
    class_public_id character varying(36),
    previous_status character varying(50),
    new_status character varying(50) NOT NULL,
    changed_at timestamp with time zone NOT NULL,
    changed_by_type character varying(20) NOT NULL,
    changed_by_public_id character varying(64),
    notes text
);

CREATE SEQUENCE public.issue_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.issue_status_history_id_seq OWNED BY public.issue_status_history.id;

CREATE TABLE public.issues (
    id integer NOT NULL,
    actor_public_id character varying(64) NOT NULL,
    reviewer_public_id character varying(64),
    class_public_id character varying(36) NOT NULL,
    class_label character varying(255),
    category_id integer NOT NULL,
    issue_type character varying(50) NOT NULL,
    title character varying(200) NOT NULL,
    student_explanation text NOT NULL,
    student_expected_outcome text,
    submitted_at timestamp with time zone NOT NULL,
    related_transaction_id integer,
    related_record_type character varying(50),
    related_record_id integer,
    context_snapshot json,
    page_url character varying(500),
    system_metadata json,
    status character varying(50) NOT NULL,
    teacher_reviewed_at timestamp with time zone,
    teacher_notes text,
    teacher_resolution character varying(100),
    teacher_resolved_at timestamp with time zone,
    escalated_at timestamp with time zone,
    escalation_reason character varying(200),
    teacher_diagnostic_note text,
    support_permissions json DEFAULT '{}'::json NOT NULL,
    share_class_name_with_sysadmin boolean NOT NULL,
    eligible_for_reward boolean NOT NULL,
    sysadmin_reviewed_at timestamp with time zone,
    sysadmin_notes text,
    sysadmin_resolved_at timestamp with time zone,
    closed_at timestamp with time zone,
    closed_by_type character varying(20),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone
);

CREATE SEQUENCE public.issues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.issues_id_seq OWNED BY public.issues.id;

CREATE TABLE public.ledger_balance_snapshot (
    id integer NOT NULL,
    seat_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    join_code character varying(20),
    account_type character varying(20) NOT NULL,
    posted_balance_cents integer NOT NULL,
    reconciled_through_posting_sequence bigint,
    reconciled_through_transaction_id integer,
    last_settlement_at timestamp with time zone,
    updated_at timestamp with time zone
);

CREATE SEQUENCE public.ledger_balance_snapshot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.ledger_balance_snapshot_id_seq OWNED BY public.ledger_balance_snapshot.id;

CREATE TABLE public.ledger_command_reservation (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    feat_code character varying(100) NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    replay_fingerprint character varying(128) NOT NULL,
    fingerprint_version integer NOT NULL,
    accepted_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.ledger_command_reservation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.ledger_command_reservation_id_seq OWNED BY public.ledger_command_reservation.id;

CREATE TABLE public.ledger_transaction (
    id integer NOT NULL,
    seat_id integer NOT NULL,
    target_seat_id integer NOT NULL,
    actor_seat_id integer NOT NULL,
    join_code character varying(20),
    class_id character varying(36),
    mechanism public.ledger_mechanism_enum DEFAULT 'self'::public.ledger_mechanism_enum NOT NULL,
    amount numeric(12,2) NOT NULL,
    "timestamp" timestamp with time zone,
    account_type character varying(20),
    status public.transactionstatus DEFAULT 'POSTED'::public.transactionstatus NOT NULL,
    amount_cents integer NOT NULL,
    posted_at timestamp with time zone,
    effective_at timestamp with time zone,
    description character varying(255),
    correlation_id character varying(100) NOT NULL,
    feat_code character varying(100),
    idempotency_key character varying(128),
    original_transaction_id integer,
    reversal_transaction_id integer,
    policy_id integer,
    type character varying(50),
    compensation_subtype character varying(50),
    date_funds_available timestamp with time zone,
    lineage_event_id integer,
    lineage_token character varying(64),
    lineage_version integer,
    posting_sequence bigint,
    command_reservation_id integer
);

CREATE SEQUENCE public.ledger_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.ledger_transaction_id_seq OWNED BY public.ledger_transaction.id;

CREATE TABLE public.obligation_command_reservation (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    command_name character varying(100) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    internal_ref character varying(200) NOT NULL,
    replay_fingerprint character varying(128) NOT NULL,
    fingerprint_version integer NOT NULL,
    bill_cycle_id integer NOT NULL,
    created_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.obligation_command_reservation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.obligation_command_reservation_id_seq OWNED BY public.obligation_command_reservation.id;

CREATE TABLE public.passkey_credentials (
    id integer NOT NULL,
    user_id integer NOT NULL,
    credential_id text,
    authenticator_name character varying(100),
    created_at timestamp with time zone NOT NULL,
    last_used timestamp with time zone
);

CREATE SEQUENCE public.passkey_credentials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.passkey_credentials_id_seq OWNED BY public.passkey_credentials.id;

CREATE TABLE public.payroll_cycle_completion (
    id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    payroll_cycle_id character varying(36) NOT NULL,
    completed_at timestamp with time zone NOT NULL
);

CREATE TABLE public.payroll_event (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    target_seat_id integer NOT NULL,
    actor_seat_id integer NOT NULL,
    correlation_id character varying(100) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    policy_version_id integer,
    policy_uuid character varying(36),
    mechanism character varying(20) NOT NULL,
    payroll_event_type character varying(20) NOT NULL,
    recorded_at timestamp with time zone NOT NULL,
    payroll_cycle_id character varying(36),
    summary_json json,
    CONSTRAINT ck_payroll_event_payroll_policy CHECK ((((payroll_event_type)::text <> 'payroll'::text) OR ((policy_version_id IS NOT NULL) AND (policy_uuid IS NOT NULL))))
);

CREATE SEQUENCE public.payroll_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.payroll_event_id_seq OWNED BY public.payroll_event.id;

CREATE TABLE public.payroll_settings (
    id integer NOT NULL,
    policy_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    availability_state character varying(16) DEFAULT 'IN_USE'::character varying NOT NULL,
    block character varying(10),
    pay_rate numeric(18,8) NOT NULL,
    payroll_frequency_days integer NOT NULL,
    next_payroll_date timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    overtime_multiplier double precision,
    settings_mode character varying(20) NOT NULL,
    daily_limit_hours double precision,
    time_unit character varying(20) NOT NULL,
    overtime_enabled boolean NOT NULL,
    overtime_threshold double precision,
    overtime_threshold_unit character varying(20),
    overtime_threshold_period character varying(20),
    max_time_per_day double precision,
    max_time_per_day_unit character varying(20),
    pay_schedule_type character varying(20) NOT NULL,
    pay_schedule_custom_value integer,
    pay_schedule_custom_unit character varying(20),
    first_pay_date timestamp with time zone,
    rounding_mode character varying(20) NOT NULL,
    CONSTRAINT ck_payroll_settings_availability CHECK ((availability_state IN ('IN_USE', 'HIDDEN', 'RETIRED')))
);

CREATE SEQUENCE public.payroll_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.payroll_settings_id_seq OWNED BY public.payroll_settings.id;

CREATE TABLE public.pending_actions (
    pending_action_id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    seat_id integer NOT NULL,
    entitlement_id character varying(36) NOT NULL,
    correlation_id character varying(200) NOT NULL,
    authoritative_feat character varying(100) NOT NULL,
    payload json NOT NULL,
    submitted_at timestamp with time zone NOT NULL
);

CREATE TABLE public.policy_transitions (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    domain character varying(32) NOT NULL,
    source_policy_version_id integer,
    target_policy_version_id integer NOT NULL,
    activation_mode character varying(32) NOT NULL,
    status character varying(32) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    created_by_seat_id integer,
    applied_at timestamp with time zone,
    correlation_id character varying(64),
    superseded_by_transition_id integer,
    cancelled_at timestamp with time zone
);

CREATE SEQUENCE public.policy_transitions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.policy_transitions_id_seq OWNED BY public.policy_transitions.id;

CREATE TABLE public.policy_versions (
    id integer NOT NULL,
    policy_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    domain character varying(32) NOT NULL,
    version_number integer NOT NULL,
    policy_payload_json text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    activated_at timestamp with time zone,
    created_by_transition_id integer,
    is_active boolean NOT NULL
);

CREATE SEQUENCE public.policy_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.policy_versions_id_seq OWNED BY public.policy_versions.id;

CREATE TABLE public.recovery_class_challenges (
    recovery_request_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    proof_verified_at timestamp with time zone NOT NULL,
    selected_at timestamp with time zone,
    selected_count integer,
    satisfied_at timestamp with time zone,
    satisfied_round integer,
    received_round integer
);

CREATE TABLE public.recovery_requests (
    id integer NOT NULL,
    user_id integer NOT NULL,
    status public.recovery_request_status_enum NOT NULL,
    created_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    completed_at timestamp with time zone,
    partial_codes json,
    resume_pin_hash character varying(64),
    resume_new_username text,
    submission_round integer DEFAULT 0 NOT NULL,
    required_class_ids json NOT NULL,
    attempt_nonce_hash character varying(64),
    selection_started_at timestamp with time zone,
    setup_nonce_hash character varying(64),
    setup_totp_encrypted text,
    setup_username text
);

CREATE SEQUENCE public.recovery_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.recovery_requests_id_seq OWNED BY public.recovery_requests.id;

CREATE TABLE public.rent_settings (
    id integer NOT NULL,
    policy_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    availability_state character varying(16) DEFAULT 'IN_USE'::character varying NOT NULL,
    rent_amount numeric(12,2),
    frequency_type character varying(20),
    custom_frequency_value integer,
    custom_frequency_unit character varying(20),
    first_rent_due_date timestamp with time zone,
    due_day_of_month integer,
    grace_period_days integer,
    late_penalty_amount numeric(12,2),
    late_penalty_type character varying(20),
    late_penalty_frequency_days integer,
    bill_preview_enabled boolean,
    bill_preview_days integer,
    allow_incremental_payment boolean,
    prevent_purchase_when_late boolean,
    bypass_cwi_warnings boolean NOT NULL,
    satisfaction_benefits json,
    rent_configured_at timestamp with time zone,
    rent_effective_at timestamp with time zone,
    cycle_length_days integer NOT NULL,
    updated_at timestamp with time zone,
    CONSTRAINT ck_rent_settings_availability CHECK ((availability_state IN ('IN_USE', 'HIDDEN', 'RETIRED')))
);

CREATE SEQUENCE public.rent_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.rent_settings_id_seq OWNED BY public.rent_settings.id;

CREATE TABLE public.seats (
    id integer NOT NULL,
    public_id character varying(36) NOT NULL,
    user_id integer,
    class_id character varying(36),
    role character varying(20) NOT NULL,
    claim_generation integer DEFAULT 0 NOT NULL,
    roster_fingerprint character varying(128),
    dedupe_code character varying(8),
    claim_first_name_hash character varying(128),
    claim_last_name_hash character varying(128),
    claimed_at timestamp with time zone,
    has_received_rent_exemption boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);

CREATE SEQUENCE public.seats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.seats_id_seq OWNED BY public.seats.id;

CREATE TABLE public.store_items (
    id integer NOT NULL
);

CREATE SEQUENCE public.store_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.store_items_id_seq OWNED BY public.store_items.id;

CREATE TABLE public.student_recovery_codes (
    id integer NOT NULL,
    recovery_request_id integer NOT NULL,
    seat_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    issued_round integer,
    code_expires_at timestamp with time zone,
    code_hash character varying(64),
    verified_at timestamp with time zone,
    notified_at timestamp with time zone NOT NULL,
    dismissed boolean NOT NULL
);

CREATE SEQUENCE public.student_recovery_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.student_recovery_codes_id_seq OWNED BY public.student_recovery_codes.id;

CREATE TABLE public.teacher_signup_attempts (
    nonce_hash character varying(64) NOT NULL,
    payload_encrypted text NOT NULL,
    expires_at timestamp with time zone NOT NULL
);

CREATE TABLE public.ticket_correlation_pack (
    issue_id integer NOT NULL,
    correlation_version integer DEFAULT 1 NOT NULL,
    actor_type character varying(20) NOT NULL,
    actor_public_id character varying(64) NOT NULL,
    class_public_id character varying(36),
    request_trace_json json NOT NULL,
    error_refs_json json NOT NULL,
    created_at timestamp with time zone NOT NULL
);

CREATE TABLE public.users (
    id integer NOT NULL,
    user_role public.user_role_enum,
    username_hash character varying(64) NOT NULL,
    username_lookup_hash character varying(64),
    totp_secret_encrypted character varying(200),
    pin_hash text,
    passphrase_hash text,
    last_signed_in_at timestamp with time zone,
    current_session_started_at timestamp with time zone,
    current_session_expires_at timestamp with time zone,
    current_session_nonce character varying(128),
    reset_code character varying(8),
    reset_code_generated_at timestamp with time zone,
    reset_code_expires_at timestamp with time zone,
    recovery_setup_nonce_hash character varying(64),
    recovery_setup_expires_at timestamp with time zone,
    last_active_seat_id integer,
    last_active_class_id character varying(36),
    provisioning_expires_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    hall_pass_verify_token character varying(64)
);

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;

ALTER TABLE ONLY public.actor_request_trace ALTER COLUMN id SET DEFAULT nextval('public.actor_request_trace_id_seq'::regclass);

ALTER TABLE ONLY public.announcements ALTER COLUMN id SET DEFAULT nextval('public.announcements_id_seq'::regclass);

ALTER TABLE ONLY public.assessment_events ALTER COLUMN id SET DEFAULT nextval('public.assessment_events_id_seq'::regclass);

ALTER TABLE ONLY public.attendance_sessions ALTER COLUMN id SET DEFAULT nextval('public.attendance_sessions_id_seq'::regclass);

ALTER TABLE ONLY public.audit_events ALTER COLUMN id SET DEFAULT nextval('public.audit_events_id_seq'::regclass);

ALTER TABLE ONLY public.bill_cycles ALTER COLUMN id SET DEFAULT nextval('public.bill_cycles_id_seq'::regclass);

ALTER TABLE ONLY public.feature_settings ALTER COLUMN id SET DEFAULT nextval('public.feature_settings_id_seq'::regclass);

ALTER TABLE ONLY public.hall_pass_logs ALTER COLUMN id SET DEFAULT nextval('public.hall_pass_logs_id_seq'::regclass);

ALTER TABLE ONLY public.hall_pass_settings ALTER COLUMN id SET DEFAULT nextval('public.hall_pass_settings_id_seq'::regclass);

ALTER TABLE ONLY public.identity_profiles ALTER COLUMN id SET DEFAULT nextval('public.identity_profiles_id_seq'::regclass);

ALTER TABLE ONLY public.insurance_claim_productivity_dates ALTER COLUMN id SET DEFAULT nextval('public.insurance_claim_productivity_dates_id_seq'::regclass);

ALTER TABLE ONLY public.issue_categories ALTER COLUMN id SET DEFAULT nextval('public.issue_categories_id_seq'::regclass);

ALTER TABLE ONLY public.issue_resolution_actions ALTER COLUMN id SET DEFAULT nextval('public.issue_resolution_actions_id_seq'::regclass);

ALTER TABLE ONLY public.issue_status_history ALTER COLUMN id SET DEFAULT nextval('public.issue_status_history_id_seq'::regclass);

ALTER TABLE ONLY public.issues ALTER COLUMN id SET DEFAULT nextval('public.issues_id_seq'::regclass);

ALTER TABLE ONLY public.ledger_balance_snapshot ALTER COLUMN id SET DEFAULT nextval('public.ledger_balance_snapshot_id_seq'::regclass);

ALTER TABLE ONLY public.ledger_command_reservation ALTER COLUMN id SET DEFAULT nextval('public.ledger_command_reservation_id_seq'::regclass);

ALTER TABLE ONLY public.ledger_transaction ALTER COLUMN id SET DEFAULT nextval('public.ledger_transaction_id_seq'::regclass);

ALTER TABLE ONLY public.obligation_command_reservation ALTER COLUMN id SET DEFAULT nextval('public.obligation_command_reservation_id_seq'::regclass);

ALTER TABLE ONLY public.passkey_credentials ALTER COLUMN id SET DEFAULT nextval('public.passkey_credentials_id_seq'::regclass);

ALTER TABLE ONLY public.payroll_event ALTER COLUMN id SET DEFAULT nextval('public.payroll_event_id_seq'::regclass);

ALTER TABLE ONLY public.payroll_settings ALTER COLUMN id SET DEFAULT nextval('public.payroll_settings_id_seq'::regclass);

ALTER TABLE ONLY public.policy_transitions ALTER COLUMN id SET DEFAULT nextval('public.policy_transitions_id_seq'::regclass);

ALTER TABLE ONLY public.policy_versions ALTER COLUMN id SET DEFAULT nextval('public.policy_versions_id_seq'::regclass);

ALTER TABLE ONLY public.recovery_requests ALTER COLUMN id SET DEFAULT nextval('public.recovery_requests_id_seq'::regclass);

ALTER TABLE ONLY public.rent_settings ALTER COLUMN id SET DEFAULT nextval('public.rent_settings_id_seq'::regclass);

ALTER TABLE ONLY public.seats ALTER COLUMN id SET DEFAULT nextval('public.seats_id_seq'::regclass);

ALTER TABLE ONLY public.store_items ALTER COLUMN id SET DEFAULT nextval('public.store_items_id_seq'::regclass);

ALTER TABLE ONLY public.student_recovery_codes ALTER COLUMN id SET DEFAULT nextval('public.student_recovery_codes_id_seq'::regclass);

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);

ALTER TABLE ONLY public.actor_request_trace
    ADD CONSTRAINT actor_request_trace_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_event_hash_key UNIQUE (event_hash);

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT bill_cycles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.chain_heads
    ADD CONSTRAINT chain_heads_pkey PRIMARY KEY (chain_scope);

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_pkey PRIMARY KEY (class_id);

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT economic_engine_pkey PRIMARY KEY (economic_version_id);

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT entitlement_events_pkey PRIMARY KEY (event_id);

ALTER TABLE ONLY public.feature_settings
    ADD CONSTRAINT feature_settings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.hall_pass_settings
    ADD CONSTRAINT hall_pass_settings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT identity_profiles_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT insurance_claim_productivity_dates_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_pkey PRIMARY KEY (claim_id);

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT insurance_policies_pkey PRIMARY KEY (policy_uuid);

ALTER TABLE ONLY public.interpretation_cycle_record
    ADD CONSTRAINT interpretation_cycle_record_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.issue_categories
    ADD CONSTRAINT issue_categories_name_key UNIQUE (name);

ALTER TABLE ONLY public.issue_categories
    ADD CONSTRAINT issue_categories_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.issue_resolution_actions
    ADD CONSTRAINT issue_resolution_actions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.issue_status_history
    ADD CONSTRAINT issue_status_history_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.issues
    ADD CONSTRAINT issues_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.ledger_command_reservation
    ADD CONSTRAINT ledger_command_reservation_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT obligation_command_reservation_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.passkey_credentials
    ADD CONSTRAINT passkey_credentials_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.payroll_cycle_completion
    ADD CONSTRAINT payroll_cycle_completion_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.payroll_settings
    ADD CONSTRAINT payroll_settings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_pkey PRIMARY KEY (pending_action_id);

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT pk_class_features PRIMARY KEY (class_id, feature, effective_at);

ALTER TABLE ONLY public.policy_transitions
    ADD CONSTRAINT policy_transitions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.recovery_class_challenges
    ADD CONSTRAINT recovery_class_challenges_pkey PRIMARY KEY (recovery_request_id, class_id);

ALTER TABLE ONLY public.recovery_requests
    ADD CONSTRAINT recovery_requests_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.rent_settings
    ADD CONSTRAINT rent_settings_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.store_items
    ADD CONSTRAINT store_items_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY public.teacher_signup_attempts
    ADD CONSTRAINT teacher_signup_attempts_pkey PRIMARY KEY (nonce_hash);

ALTER TABLE ONLY public.ticket_correlation_pack
    ADD CONSTRAINT ticket_correlation_pack_pkey PRIMARY KEY (issue_id);

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT uq_audit_chain_position UNIQUE (chain_scope, sequence_number);

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT uq_balance_snapshot_scope UNIQUE (class_id, seat_id, account_type);

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT uq_bill_cycles_ref_cycle UNIQUE (internal_ref, cycle_number);

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT uq_economic_engine_class_version UNIQUE (class_id, economic_version_id);

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT uq_icpd_claim_date UNIQUE (claim_id, claim_date);

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT uq_icpd_entitlement_date UNIQUE (entitlement_id, claim_date);

ALTER TABLE ONLY public.interpretation_cycle_record
    ADD CONSTRAINT uq_interpretation_cycle_record_class_cycle UNIQUE (class_id, payroll_cycle_id);

ALTER TABLE ONLY public.ledger_command_reservation
    ADD CONSTRAINT uq_ledger_command_reservation_identity UNIQUE (class_id, feat_code, idempotency_key);

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT uq_ledger_transaction_class_posting_sequence UNIQUE (class_id, posting_sequence);

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT uq_obligation_command_reservation_identity UNIQUE (class_id, command_name, idempotency_key);

ALTER TABLE ONLY public.payroll_cycle_completion
    ADD CONSTRAINT uq_payroll_cycle_completion_class_key UNIQUE (class_id, idempotency_key);

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT uq_payroll_event_replay_guard UNIQUE (class_id, target_seat_id, correlation_id, idempotency_key, payroll_event_type);

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT uq_policy_versions_class_domain_version UNIQUE (class_id, domain, version_number);

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT uq_seats_user_class UNIQUE (user_id, class_id);

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

CREATE INDEX ix_actor_request_trace_actor_public_id ON public.actor_request_trace USING btree (actor_public_id);

CREATE INDEX ix_actor_request_trace_actor_type ON public.actor_request_trace USING btree (actor_type);

CREATE INDEX ix_actor_request_trace_class_id ON public.actor_request_trace USING btree (class_id);

CREATE INDEX ix_actor_request_trace_created_at ON public.actor_request_trace USING btree (created_at);

CREATE INDEX ix_actor_request_trace_request_id ON public.actor_request_trace USING btree (request_id);

CREATE INDEX ix_actor_trace_actor_public_created ON public.actor_request_trace USING btree (actor_type, actor_public_id, created_at);

CREATE INDEX ix_announcements_class_id ON public.announcements USING btree (class_id);

CREATE INDEX ix_assessment_events_bill_cycle_id ON public.assessment_events USING btree (bill_cycle_id);

CREATE INDEX ix_assessment_events_class_id ON public.assessment_events USING btree (class_id);

CREATE INDEX ix_assessment_events_correlation_id ON public.assessment_events USING btree (correlation_id);

CREATE INDEX ix_assessment_events_event_type ON public.assessment_events USING btree (event_type);

CREATE INDEX ix_assessment_events_internal_ref ON public.assessment_events USING btree (internal_ref);

CREATE INDEX ix_assessment_events_ledger_transaction_id ON public.assessment_events USING btree (ledger_transaction_id);

CREATE INDEX ix_assessment_events_obligation_type ON public.assessment_events USING btree (obligation_type);

CREATE INDEX ix_assessment_events_policy_uuid ON public.assessment_events USING btree (policy_uuid);

CREATE INDEX ix_assessment_events_policy_version_id ON public.assessment_events USING btree (policy_version_id);

CREATE INDEX ix_assessment_events_seat_class ON public.assessment_events USING btree (seat_id, class_id);

CREATE INDEX ix_assessment_events_seat_id ON public.assessment_events USING btree (seat_id);

CREATE INDEX ix_assessment_events_source_correlation_id ON public.assessment_events USING btree (source_correlation_id);

CREATE INDEX ix_attendance_sessions_actor_seat_id ON public.attendance_sessions USING btree (actor_seat_id);

CREATE INDEX ix_attendance_sessions_class_id ON public.attendance_sessions USING btree (class_id);

CREATE INDEX ix_attendance_sessions_hall_pass_id ON public.attendance_sessions USING btree (hall_pass_id);

CREATE INDEX ix_attendance_sessions_reason_code ON public.attendance_sessions USING btree (reason_code);

CREATE INDEX ix_attendance_sessions_target_seat_id ON public.attendance_sessions USING btree (target_seat_id);

CREATE INDEX ix_attendance_sessions_timestamp ON public.attendance_sessions USING btree ("timestamp");

CREATE INDEX ix_audit_events_chain_scope ON public.audit_events USING btree (chain_scope);

CREATE INDEX ix_audit_events_class_id ON public.audit_events USING btree (class_id);

CREATE INDEX ix_audit_events_correlation_id ON public.audit_events USING btree (correlation_id);

CREATE INDEX ix_audit_events_table_row ON public.audit_events USING btree (table_name, row_pk);

CREATE INDEX ix_bill_cycles_class_id ON public.bill_cycles USING btree (class_id);

CREATE INDEX ix_bill_cycles_internal_ref ON public.bill_cycles USING btree (internal_ref);

CREATE INDEX ix_bill_cycles_policy_uuid ON public.bill_cycles USING btree (policy_uuid);

CREATE INDEX ix_class_features_class_id ON public.class_features USING btree (class_id);

CREATE INDEX ix_class_features_economic_version_id ON public.class_features USING btree (economic_version_id);

CREATE UNIQUE INDEX ix_classes_class_public_id ON public.classes USING btree (class_public_id);

CREATE UNIQUE INDEX ix_classes_join_code ON public.classes USING btree (join_code);

CREATE INDEX ix_classes_teacher_user_id ON public.classes USING btree (teacher_user_id);

CREATE INDEX ix_economic_engine_class_id ON public.economic_engine USING btree (class_id);

CREATE INDEX ix_economic_engine_previous_version_id ON public.economic_engine USING btree (previous_version_id);

CREATE INDEX ix_entitlement_events_class_id ON public.entitlement_events USING btree (class_id);

CREATE INDEX ix_entitlement_events_correlation_id ON public.entitlement_events USING btree (correlation_id);

CREATE INDEX ix_entitlement_events_entitlement_id ON public.entitlement_events USING btree (entitlement_id);

CREATE INDEX ix_entitlement_events_entitlement_id_class ON public.entitlement_events USING btree (entitlement_id, class_id);

CREATE INDEX ix_entitlement_events_event_type ON public.entitlement_events USING btree (event_type);

CREATE UNIQUE INDEX ix_entitlement_events_one_terminal_per_lineage ON public.entitlement_events USING btree (entitlement_id, class_id) WHERE (event_type IN ('CONSUMED', 'EXPIRED', 'REVOKED'));

CREATE INDEX ix_entitlement_events_product_id ON public.entitlement_events USING btree (product_id);

CREATE INDEX ix_entitlement_events_seat_class ON public.entitlement_events USING btree (target_seat_id, class_id);

CREATE INDEX ix_entitlement_events_target_seat_id ON public.entitlement_events USING btree (target_seat_id);

CREATE UNIQUE INDEX ix_feature_settings_class_id ON public.feature_settings USING btree (class_id);

CREATE INDEX ix_hall_pass_logs_approved_by_seat_id ON public.hall_pass_logs USING btree (approved_by_seat_id);

CREATE INDEX ix_hall_pass_logs_class_id ON public.hall_pass_logs USING btree (class_id);

CREATE INDEX ix_hall_pass_logs_correlation_id ON public.hall_pass_logs USING btree (correlation_id);

CREATE INDEX ix_hall_pass_logs_hall_pass_id ON public.hall_pass_logs USING btree (hall_pass_id);

CREATE INDEX ix_hall_pass_logs_policy_uuid ON public.hall_pass_logs USING btree (policy_uuid);

CREATE INDEX ix_hall_pass_logs_requested_by_seat_id ON public.hall_pass_logs USING btree (requested_by_seat_id);

CREATE INDEX ix_hall_pass_settings_class_availability ON public.hall_pass_settings USING btree (class_id, availability_state);

CREATE INDEX ix_hall_pass_settings_class_id ON public.hall_pass_settings USING btree (class_id);

CREATE INDEX ix_hall_pass_settings_effective_date ON public.hall_pass_settings USING btree (effective_date);

CREATE UNIQUE INDEX ix_hall_pass_settings_policy_uuid ON public.hall_pass_settings USING btree (policy_uuid);

CREATE INDEX ix_icpd_claim_id ON public.insurance_claim_productivity_dates USING btree (claim_id);

CREATE INDEX ix_icpd_class_id ON public.insurance_claim_productivity_dates USING btree (class_id);

CREATE INDEX ix_icpd_entitlement_id ON public.insurance_claim_productivity_dates USING btree (entitlement_id);

CREATE INDEX ix_identity_profiles_class_id ON public.identity_profiles USING btree (class_id);

CREATE INDEX ix_identity_profiles_profile_type ON public.identity_profiles USING btree (profile_type);

CREATE UNIQUE INDEX ix_identity_profiles_seat_id ON public.identity_profiles USING btree (seat_id);

CREATE INDEX ix_identity_profiles_type_name ON public.identity_profiles USING btree (profile_type, last_name);

CREATE INDEX ix_insurance_claim_productivity_dates_claim_id ON public.insurance_claim_productivity_dates USING btree (claim_id);

CREATE INDEX ix_insurance_claim_productivity_dates_class_id ON public.insurance_claim_productivity_dates USING btree (class_id);

CREATE INDEX ix_insurance_claim_productivity_dates_entitlement_id ON public.insurance_claim_productivity_dates USING btree (entitlement_id);

CREATE INDEX ix_insurance_claims_class_id ON public.insurance_claims USING btree (class_id);

CREATE UNIQUE INDEX ix_insurance_claims_correlation_id ON public.insurance_claims USING btree (correlation_id);

CREATE INDEX ix_insurance_claims_entitlement_class ON public.insurance_claims USING btree (entitlement_id, class_id);

CREATE INDEX ix_insurance_claims_entitlement_id ON public.insurance_claims USING btree (entitlement_id);

CREATE INDEX ix_insurance_claims_seat_class ON public.insurance_claims USING btree (target_seat_id, class_id);

CREATE INDEX ix_insurance_claims_status ON public.insurance_claims USING btree (status);

CREATE INDEX ix_insurance_claims_status_class ON public.insurance_claims USING btree (status, class_id);

CREATE INDEX ix_insurance_claims_target_seat_id ON public.insurance_claims USING btree (target_seat_id);

CREATE INDEX ix_insurance_policies_class_avail ON public.insurance_policies USING btree (class_id, availability_state);

CREATE INDEX ix_insurance_policies_class_id ON public.insurance_policies USING btree (class_id);

CREATE INDEX ix_interpretation_cycle_record_class_id ON public.interpretation_cycle_record USING btree (class_id);

CREATE INDEX ix_interpretation_cycle_record_payroll_cycle_id ON public.interpretation_cycle_record USING btree (payroll_cycle_id);

CREATE INDEX ix_issue_resolution_actions_class_public_id ON public.issue_resolution_actions USING btree (class_public_id);

CREATE INDEX ix_issue_resolution_actions_issue_id ON public.issue_resolution_actions USING btree (issue_id);

CREATE INDEX ix_issue_status_history_class_public_id ON public.issue_status_history USING btree (class_public_id);

CREATE INDEX ix_issue_status_history_issue_id ON public.issue_status_history USING btree (issue_id);

CREATE INDEX ix_issues_actor_public_id ON public.issues USING btree (actor_public_id);

CREATE INDEX ix_issues_actor_status ON public.issues USING btree (actor_public_id, status);

CREATE INDEX ix_issues_class_public_id ON public.issues USING btree (class_public_id);

CREATE INDEX ix_issues_class_status ON public.issues USING btree (class_public_id, status);

CREATE INDEX ix_issues_reviewer_public_id ON public.issues USING btree (reviewer_public_id);

CREATE INDEX ix_issues_status ON public.issues USING btree (status);

CREATE INDEX ix_issues_submitted_at ON public.issues USING btree (submitted_at);

CREATE INDEX ix_ledger_balance_snapshot_class_id ON public.ledger_balance_snapshot USING btree (class_id);

CREATE INDEX ix_ledger_balance_snapshot_seat_id ON public.ledger_balance_snapshot USING btree (seat_id);

CREATE INDEX ix_ledger_transaction_actor_seat_id ON public.ledger_transaction USING btree (actor_seat_id);

CREATE INDEX ix_ledger_transaction_class_id ON public.ledger_transaction USING btree (class_id);

CREATE INDEX ix_ledger_transaction_command_reservation_id ON public.ledger_transaction USING btree (command_reservation_id);

CREATE INDEX ix_ledger_transaction_compensation_subtype ON public.ledger_transaction USING btree (compensation_subtype);

CREATE INDEX ix_ledger_transaction_correlation_id ON public.ledger_transaction USING btree (correlation_id);

CREATE INDEX ix_ledger_transaction_feat_code ON public.ledger_transaction USING btree (feat_code);

CREATE INDEX ix_ledger_transaction_idempotency_key ON public.ledger_transaction USING btree (idempotency_key);

CREATE INDEX ix_ledger_transaction_join_code ON public.ledger_transaction USING btree (join_code);

CREATE INDEX ix_ledger_transaction_lineage_event_id ON public.ledger_transaction USING btree (lineage_event_id);

CREATE INDEX ix_ledger_transaction_original_transaction_id ON public.ledger_transaction USING btree (original_transaction_id);

CREATE INDEX ix_ledger_transaction_policy_id ON public.ledger_transaction USING btree (policy_id);

CREATE INDEX ix_ledger_transaction_posting_sequence ON public.ledger_transaction USING btree (posting_sequence);

CREATE INDEX ix_ledger_transaction_reconstruction_scope ON public.ledger_transaction USING btree (class_id, seat_id, account_type, posting_sequence, status);

CREATE INDEX ix_ledger_transaction_reversal_transaction_id ON public.ledger_transaction USING btree (reversal_transaction_id);

CREATE INDEX ix_ledger_transaction_seat_id ON public.ledger_transaction USING btree (seat_id);

CREATE INDEX ix_ledger_transaction_target_seat_id ON public.ledger_transaction USING btree (target_seat_id);

CREATE INDEX ix_obligation_command_reservation_bill_cycle_id ON public.obligation_command_reservation USING btree (bill_cycle_id);

CREATE INDEX ix_obligation_command_reservation_class_id ON public.obligation_command_reservation USING btree (class_id);

CREATE INDEX ix_passkey_credentials_user_id ON public.passkey_credentials USING btree (user_id);

CREATE INDEX ix_payroll_cycle_completion_class_id ON public.payroll_cycle_completion USING btree (class_id);

CREATE INDEX ix_payroll_cycle_completion_payroll_cycle_id ON public.payroll_cycle_completion USING btree (payroll_cycle_id);

CREATE INDEX ix_payroll_event_actor_seat_id ON public.payroll_event USING btree (actor_seat_id);

CREATE INDEX ix_payroll_event_class_id ON public.payroll_event USING btree (class_id);

CREATE INDEX ix_payroll_event_correlation_id ON public.payroll_event USING btree (correlation_id);

CREATE INDEX ix_payroll_event_idempotency_key ON public.payroll_event USING btree (idempotency_key);

CREATE INDEX ix_payroll_event_payroll_cycle_id ON public.payroll_event USING btree (payroll_cycle_id);

CREATE INDEX ix_payroll_event_policy_uuid ON public.payroll_event USING btree (policy_uuid);

CREATE INDEX ix_payroll_event_policy_version_id ON public.payroll_event USING btree (policy_version_id);

CREATE INDEX ix_payroll_event_recorded_at ON public.payroll_event USING btree (recorded_at);

CREATE INDEX ix_payroll_event_target_seat_id ON public.payroll_event USING btree (target_seat_id);

CREATE INDEX ix_payroll_settings_class_availability ON public.payroll_settings USING btree (class_id, availability_state);

CREATE INDEX ix_payroll_settings_class_id ON public.payroll_settings USING btree (class_id);

CREATE UNIQUE INDEX ix_payroll_settings_policy_uuid ON public.payroll_settings USING btree (policy_uuid);

CREATE INDEX ix_pending_actions_authoritative_feat ON public.pending_actions USING btree (authoritative_feat);

CREATE INDEX ix_pending_actions_class ON public.pending_actions USING btree (class_id);

CREATE INDEX ix_pending_actions_class_id ON public.pending_actions USING btree (class_id);

CREATE UNIQUE INDEX ix_pending_actions_correlation_id ON public.pending_actions USING btree (correlation_id);

CREATE INDEX ix_pending_actions_entitlement_id ON public.pending_actions USING btree (entitlement_id);

CREATE INDEX ix_pending_actions_seat_id ON public.pending_actions USING btree (seat_id);

CREATE INDEX ix_policy_transitions_class_domain_status ON public.policy_transitions USING btree (class_id, domain, status);

CREATE INDEX ix_policy_transitions_class_id ON public.policy_transitions USING btree (class_id);

CREATE INDEX ix_policy_transitions_correlation_id ON public.policy_transitions USING btree (correlation_id);

CREATE INDEX ix_policy_versions_class_domain_active ON public.policy_versions USING btree (class_id, domain, is_active);

CREATE INDEX ix_policy_versions_class_id ON public.policy_versions USING btree (class_id);

CREATE UNIQUE INDEX ix_policy_versions_policy_uuid ON public.policy_versions USING btree (policy_uuid);

CREATE INDEX ix_recovery_requests_user_id ON public.recovery_requests USING btree (user_id);

CREATE INDEX ix_rent_settings_class_availability ON public.rent_settings USING btree (class_id, availability_state);

CREATE INDEX ix_rent_settings_class_id ON public.rent_settings USING btree (class_id);

CREATE UNIQUE INDEX ix_rent_settings_policy_uuid ON public.rent_settings USING btree (policy_uuid);

CREATE INDEX ix_rent_settings_rent_configured_at ON public.rent_settings USING btree (rent_configured_at);

CREATE INDEX ix_rent_settings_rent_effective_at ON public.rent_settings USING btree (rent_effective_at);

CREATE INDEX ix_seats_claim_first_name_hash ON public.seats USING btree (claim_first_name_hash);

CREATE INDEX ix_seats_claim_last_name_hash ON public.seats USING btree (claim_last_name_hash);

CREATE INDEX ix_seats_class_id ON public.seats USING btree (class_id);

CREATE UNIQUE INDEX ix_seats_public_id ON public.seats USING btree (public_id);

CREATE INDEX ix_seats_roster_fingerprint ON public.seats USING btree (roster_fingerprint);

CREATE INDEX ix_seats_user_id ON public.seats USING btree (user_id);

CREATE INDEX ix_student_recovery_codes_class_id ON public.student_recovery_codes USING btree (class_id);

CREATE INDEX ix_student_recovery_codes_recovery_request_id ON public.student_recovery_codes USING btree (recovery_request_id);

CREATE INDEX ix_student_recovery_codes_seat_id ON public.student_recovery_codes USING btree (seat_id);

CREATE INDEX ix_teacher_signup_attempts_expires_at ON public.teacher_signup_attempts USING btree (expires_at);

CREATE INDEX ix_ticket_correlation_actor_public ON public.ticket_correlation_pack USING btree (actor_type, actor_public_id);

CREATE INDEX ix_transaction_class_scope ON public.ledger_transaction USING btree (class_id, target_seat_id, actor_seat_id, account_type);

CREATE INDEX ix_transaction_seat_ledger ON public.ledger_transaction USING btree (join_code, seat_id, status, account_type);

CREATE INDEX ix_users_current_session_nonce ON public.users USING btree (current_session_nonce);

CREATE UNIQUE INDEX ix_users_hall_pass_verify_token ON public.users USING btree (hall_pass_verify_token);

CREATE INDEX ix_users_last_active_class_id ON public.users USING btree (last_active_class_id);

CREATE INDEX ix_users_last_active_seat_id ON public.users USING btree (last_active_seat_id);

CREATE INDEX ix_users_last_signed_in_at ON public.users USING btree (last_signed_in_at);

CREATE INDEX ix_users_provisioning_expires_at ON public.users USING btree (provisioning_expires_at);

CREATE INDEX ix_users_user_role ON public.users USING btree (user_role);

CREATE UNIQUE INDEX ix_users_username_hash ON public.users USING btree (username_hash);

CREATE UNIQUE INDEX ix_users_username_lookup_hash ON public.users USING btree (username_lookup_hash);

CREATE UNIQUE INDEX uq_hall_pass_settings_active_scope ON public.hall_pass_settings USING btree (class_id) WHERE ((availability_state)::text = 'IN_USE'::text);

CREATE UNIQUE INDEX uq_insurance_policies_group_rank_in_use ON public.insurance_policies USING btree (class_id, tier_group, tier_level) WHERE (((availability_state)::text = 'IN_USE'::text) AND (tier_group IS NOT NULL));

CREATE UNIQUE INDEX uq_payroll_settings_active_scope ON public.payroll_settings USING btree (class_id) WHERE ((availability_state)::text = 'IN_USE'::text);

ALTER TABLE ONLY public.actor_request_trace
    ADD CONSTRAINT actor_request_trace_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_created_by_seat_id_fkey FOREIGN KEY (created_by_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_bill_cycle_id_fkey FOREIGN KEY (bill_cycle_id) REFERENCES public.bill_cycles(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_ledger_transaction_id_fkey FOREIGN KEY (ledger_transaction_id) REFERENCES public.ledger_transaction(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_policy_version_id_fkey FOREIGN KEY (policy_version_id) REFERENCES public.policy_versions(id);

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT bill_cycles_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT class_features_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_teacher_user_id_fkey FOREIGN KEY (teacher_user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT economic_engine_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT entitlement_events_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT entitlement_events_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT entitlement_events_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.feature_settings
    ADD CONSTRAINT feature_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT fk_class_features_economic_version FOREIGN KEY (class_id, economic_version_id) REFERENCES public.economic_engine(class_id, economic_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT fk_economic_engine_previous_version FOREIGN KEY (class_id, previous_version_id) REFERENCES public.economic_engine(class_id, economic_version_id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_last_active_seat_id_seats FOREIGN KEY (last_active_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_approved_by_seat_id_fkey FOREIGN KEY (approved_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_requested_by_seat_id_fkey FOREIGN KEY (requested_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.hall_pass_settings
    ADD CONSTRAINT hall_pass_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT identity_profiles_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT identity_profiles_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT insurance_claim_productivity_dates_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.insurance_claims(claim_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT insurance_claim_productivity_dates_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_decided_by_seat_id_fkey FOREIGN KEY (decided_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT insurance_policies_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT insurance_policies_created_by_seat_id_fkey FOREIGN KEY (created_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.interpretation_cycle_record
    ADD CONSTRAINT interpretation_cycle_record_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.issue_resolution_actions
    ADD CONSTRAINT issue_resolution_actions_issue_id_fkey FOREIGN KEY (issue_id) REFERENCES public.issues(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.issue_resolution_actions
    ADD CONSTRAINT issue_resolution_actions_related_transaction_id_fkey FOREIGN KEY (related_transaction_id) REFERENCES public.ledger_transaction(id);

ALTER TABLE ONLY public.issue_status_history
    ADD CONSTRAINT issue_status_history_issue_id_fkey FOREIGN KEY (issue_id) REFERENCES public.issues(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.issues
    ADD CONSTRAINT issues_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.issue_categories(id);

ALTER TABLE ONLY public.issues
    ADD CONSTRAINT issues_related_transaction_id_fkey FOREIGN KEY (related_transaction_id) REFERENCES public.ledger_transaction(id);

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_reconciled_through_transaction_id_fkey FOREIGN KEY (reconciled_through_transaction_id) REFERENCES public.ledger_transaction(id);

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ledger_command_reservation
    ADD CONSTRAINT ledger_command_reservation_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_command_reservation_id_fkey FOREIGN KEY (command_reservation_id) REFERENCES public.ledger_command_reservation(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_lineage_event_id_fkey FOREIGN KEY (lineage_event_id) REFERENCES public.audit_events(id);

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT obligation_command_reservation_bill_cycle_id_fkey FOREIGN KEY (bill_cycle_id) REFERENCES public.bill_cycles(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT obligation_command_reservation_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.passkey_credentials
    ADD CONSTRAINT passkey_credentials_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.payroll_cycle_completion
    ADD CONSTRAINT payroll_cycle_completion_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_policy_version_id_fkey FOREIGN KEY (policy_version_id) REFERENCES public.policy_versions(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.payroll_settings
    ADD CONSTRAINT payroll_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.policy_transitions
    ADD CONSTRAINT policy_transitions_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.policy_transitions
    ADD CONSTRAINT policy_transitions_created_by_seat_id_fkey FOREIGN KEY (created_by_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.policy_transitions
    ADD CONSTRAINT policy_transitions_source_policy_version_id_fkey FOREIGN KEY (source_policy_version_id) REFERENCES public.policy_versions(id);

ALTER TABLE ONLY public.policy_transitions
    ADD CONSTRAINT policy_transitions_superseded_by_transition_id_fkey FOREIGN KEY (superseded_by_transition_id) REFERENCES public.policy_transitions(id);

ALTER TABLE ONLY public.policy_transitions
    ADD CONSTRAINT policy_transitions_target_policy_version_id_fkey FOREIGN KEY (target_policy_version_id) REFERENCES public.policy_versions(id);

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.policy_versions
    ADD CONSTRAINT policy_versions_created_by_transition_id_fkey FOREIGN KEY (created_by_transition_id) REFERENCES public.policy_transitions(id);

ALTER TABLE ONLY public.recovery_class_challenges
    ADD CONSTRAINT recovery_class_challenges_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.recovery_class_challenges
    ADD CONSTRAINT recovery_class_challenges_recovery_request_id_fkey FOREIGN KEY (recovery_request_id) REFERENCES public.recovery_requests(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.recovery_requests
    ADD CONSTRAINT recovery_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);

ALTER TABLE ONLY public.rent_settings
    ADD CONSTRAINT rent_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_recovery_request_id_fkey FOREIGN KEY (recovery_request_id) REFERENCES public.recovery_requests(id);

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id);

ALTER TABLE ONLY public.ticket_correlation_pack
    ADD CONSTRAINT ticket_correlation_pack_issue_id_fkey FOREIGN KEY (issue_id) REFERENCES public.issues(id) ON DELETE CASCADE;

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_last_active_class_id_fkey FOREIGN KEY (last_active_class_id) REFERENCES public.classes(class_id) ON DELETE SET NULL;
