--
-- PostgreSQL database dump
--



SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: credential_operation_purpose_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.credential_operation_purpose_enum AS ENUM (
    'totp_replace',
    'passkey_enroll',
    'passkey_replace',
    'passkey_revoke'
);


--
-- Name: credential_operation_stage_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.credential_operation_stage_enum AS ENUM (
    'authorized',
    'registration_pending',
    'candidate_verified',
    'retirement_committed',
    'provider_uncertain',
    'completed',
    'cancelled',
    'awaiting_step_up'
);


--
-- Name: disposition_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.disposition_enum AS ENUM (
    'CONSUMED',
    'EXPIRED',
    'REVOKED'
);


--
-- Name: grant_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.grant_type_enum AS ENUM (
    'PURCHASE',
    'MANUAL_GRANT',
    'OBLIGATION'
);


--
-- Name: insurance_claim_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.insurance_claim_status_enum AS ENUM (
    'SUBMITTED',
    'APPROVED',
    'REJECTED'
);


--
-- Name: ledger_mechanism_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.ledger_mechanism_enum AS ENUM (
    'self',
    'teacher',
    'system'
);


--
-- Name: recovery_request_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.recovery_request_status_enum AS ENUM (
    'pending',
    'verified',
    'expired',
    'cancelled'
);


--
-- Name: redemption_event_action_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.redemption_event_action_enum AS ENUM (
    'REQUEST',
    'APPROVED',
    'REJECTED'
);


--
-- Name: redemption_event_source_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.redemption_event_source_enum AS ENUM (
    'live'
);


--
-- Name: transactionstatus; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.transactionstatus AS ENUM (
    'PENDING',
    'POSTED',
    'VOID'
);


--
-- Name: user_role_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role_enum AS ENUM (
    'student',
    'teacher',
    'sysadmin'
);


--
-- Name: economic_engine_default_effective_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.economic_engine_default_effective_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.effective_at IS NULL THEN
                NEW.effective_at := NEW.created_at;
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: enforce_ledger_recovery_cap(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.enforce_ledger_recovery_cap() RETURNS trigger
    LANGUAGE plpgsql
    AS $_$
    DECLARE origin ledger_transaction%ROWTYPE; recovered bigint;
    BEGIN
      IF NEW.type='REVERSAL' THEN
        IF NEW.original_transaction_id IS NULL THEN
          RAISE EXCEPTION 'Exact reversal requires an immutable original locator';
        END IF;
        SELECT * INTO origin FROM ledger_transaction
          WHERE id=NEW.original_transaction_id FOR UPDATE;
        IF NOT FOUND OR origin.type='REVERSAL'
          OR origin.class_id IS DISTINCT FROM NEW.class_id
          OR origin.seat_id IS DISTINCT FROM NEW.seat_id
          OR origin.target_seat_id IS DISTINCT FROM NEW.target_seat_id
          OR origin.account_type IS DISTINCT FROM NEW.account_type
          OR origin.correlation_id IS DISTINCT FROM NEW.correlation_id
          OR origin.amount_cents IS NULL OR origin.amount_cents=0
          OR NEW.amount_cents IS DISTINCT FROM -origin.amount_cents THEN
          RAISE EXCEPTION 'Exact reversal must negate its original in the same scope and correlation';
        END IF;
      END IF;
      IF NEW.compensation_amount_cents IS NULL OR NEW.compensation_amount_cents < 0 THEN
        RAISE EXCEPTION 'New Ledger effect requires explicit attributable recovery';
      END IF;
      IF NEW.compensation_amount_cents = 0 THEN
        IF NEW.type='REVERSAL' AND NEW.amount_cents<0 THEN RAISE EXCEPTION 'Credit reversal requires attributable recovery'; END IF;
        IF NEW.compensation_origin_locator IS NOT NULL OR NEW.correction_intent_locator IS NOT NULL THEN
          RAISE EXCEPTION 'Non-recovery Ledger effect cannot claim recovery lineage';
        END IF; RETURN NEW;
      END IF;
      IF NEW.compensation_origin_locator !~ '^ledger-credit:v1:[1-9][0-9]*$' THEN RAISE EXCEPTION 'Invalid Ledger origin locator'; END IF;
      SELECT * INTO origin FROM ledger_transaction WHERE id=split_part(NEW.compensation_origin_locator,':',3)::bigint
        AND class_id=NEW.class_id AND target_seat_id=NEW.target_seat_id AND seat_id=NEW.seat_id FOR UPDATE;
      IF NOT FOUND OR origin.amount_cents <= 0 OR origin.account_type IS DISTINCT FROM NEW.account_type
        OR NEW.amount_cents <> -NEW.compensation_amount_cents THEN RAISE EXCEPTION 'Invalid attributable Ledger recovery'; END IF;
      IF EXISTS(SELECT 1 FROM ledger_transaction prior WHERE prior.class_id=NEW.class_id AND prior.seat_id=NEW.seat_id
        AND prior.amount_cents<0 AND prior.posting_sequence>origin.posting_sequence AND COALESCE(prior.lineage_version,0)<3
        AND (prior.type IN ('REVERSAL','payroll','payroll_correction') OR prior.correlation_id=origin.correlation_id
          OR prior.id=origin.reversal_transaction_id OR prior.original_transaction_id=origin.id)) THEN
        RAISE EXCEPTION 'Historical Ledger recovery provenance unavailable'; END IF;
      SELECT COALESCE(SUM(compensation_amount_cents),0) INTO recovered FROM ledger_transaction
        WHERE class_id=NEW.class_id AND target_seat_id=NEW.target_seat_id AND compensation_origin_locator=NEW.compensation_origin_locator;
      IF NEW.type='REVERSAL' AND (recovered<>0 OR NEW.compensation_amount_cents<>origin.amount_cents
        OR NEW.original_transaction_id IS DISTINCT FROM origin.id) THEN
        RAISE EXCEPTION 'Credit REVERSAL requires the uncompensated whole original transaction'; END IF;
      IF recovered + NEW.compensation_amount_cents > origin.amount_cents THEN RAISE EXCEPTION 'Ledger recovery cap exceeded'; END IF;
      RETURN NEW;
    END; $_$;


--
-- Name: guard_attendance_invalidation_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.guard_attendance_invalidation_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
      IF COALESCE(current_setting('cth.class_universe_destroying',true),'')='on'
        OR NOT EXISTS (SELECT 1 FROM seats WHERE id=OLD.target_seat_id) THEN RETURN OLD; END IF;
      RAISE EXCEPTION 'Attendance invalidation belongs to surviving target; lifecycle destruction only';
    END; $$;


--
-- Name: guard_attendance_invalidation_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.guard_attendance_invalidation_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
      IF NEW.lineage_event_id IS NOT NULL OR NEW.lineage_token IS NOT NULL OR NEW.lineage_version IS NOT NULL THEN
        RAISE EXCEPTION 'Invalidation lineage initializes after INSERT only';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM seats a WHERE a.id=NEW.actor_seat_id AND a.class_id=NEW.class_id AND a.role='teacher')
        OR NOT EXISTS (SELECT 1 FROM seats t WHERE t.id=NEW.target_seat_id AND t.class_id=NEW.class_id AND t.role='student')
        OR NOT EXISTS (SELECT 1 FROM attendance_sessions a JOIN attendance_sessions b ON b.id=NEW.closing_event_id
          WHERE a.id=NEW.opening_event_id AND a.class_id=NEW.class_id AND b.class_id=NEW.class_id
            AND a.target_seat_id=NEW.target_seat_id AND b.target_seat_id=NEW.target_seat_id
            AND a.status='active' AND b.status='inactive' AND b.timestamp>=a.timestamp) THEN
        RAISE EXCEPTION 'Invalidation source and seats must share canonical class/target scope';
      END IF;
      RETURN NEW;
    END; $$;


--
-- Name: guard_attendance_invalidation_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.guard_attendance_invalidation_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    BEGIN
      IF NOT payroll_creator_is_uncommitted(OLD.xmin) OR OLD.lineage_event_id IS NOT NULL
        OR OLD.lineage_token IS NOT NULL OR OLD.lineage_version IS NOT NULL
        OR NEW.lineage_event_id IS NULL OR NEW.lineage_token IS NULL OR NEW.lineage_version IS NULL
        OR NEW.receipt_json::text IS DISTINCT FROM OLD.receipt_json::text
        OR (to_jsonb(NEW)-ARRAY['lineage_event_id','lineage_token','lineage_version']) IS DISTINCT FROM
           (to_jsonb(OLD)-ARRAY['lineage_event_id','lineage_token','lineage_version']) THEN
        RAISE EXCEPTION 'Attendance invalidation is immutable; lineage initializes once in creating transaction only';
      END IF;
      RETURN NEW;
    END; $$;


--
-- Name: payroll_creator_is_uncommitted(xid); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.payroll_creator_is_uncommitted(row_xid xid) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
        DECLARE current_xid bigint := txid_current();
                distance bigint;
                expanded bigint;
        BEGIN
            -- Expand PostgreSQL's 32-bit row xmin to the nearest xid8 epoch.
            -- A savepoint xid can be greater than its parent's txid_current;
            -- snapshot xmax is the parent xid and is not an allocation bound.
            distance := row_xid::text::bigint - (current_xid % 4294967296);
            IF distance > 2147483647 THEN distance := distance - 4294967296; END IF;
            IF distance < -2147483648 THEN distance := distance + 4294967296; END IF;
            expanded := current_xid + distance;
            IF expanded < 3 THEN RETURN false; END IF;
            RETURN COALESCE(pg_xact_status(expanded::text::xid8) = 'in progress', false);
        END;
        $$;


--
-- Name: prevent_attendance_session_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_attendance_session_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Class or teacher-account destruction declares itself (SET LOCAL).
    IF coalesce(current_setting('app.attendance_teardown', true), 'off') = 'on' THEN
        RETURN OLD;
    END IF;
    -- Lawful seat removal: the row's seat is already deleted and this DELETE is
    -- the FK cascade destroying the seat's attendance with it
    -- (INV-CORE-000 §III.6, DOM-PROD-001 §VII.1.a).
    IF NOT EXISTS (SELECT 1 FROM seats WHERE id = OLD.target_seat_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION
        'attendance_sessions is append-only (DOM-PROD-001 §184). '
        'A seat''s attendance is removed only with the seat itself, or when the '
        'class or teacher account is destroyed. To remedy an incorrect payroll '
        'outcome, reverse the payroll through FEAT-PROD-003.';
END;
$$;


--
-- Name: prevent_attendance_session_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_attendance_session_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                RAISE EXCEPTION
                    'attendance_sessions is append-only (DOM-PROD-001 §108). '
                    'An attendance row is never edited or corrected in place. '
                    'To remedy an incorrect payroll outcome, reverse the payroll '
                    'through FEAT-PROD-003.';
            END;
            $$;


--
-- Name: prevent_audit_event_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_audit_event_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only (INV-ARC-016 VIII). Deletions are not permitted in any environment.';
            END;
            $$;


--
-- Name: prevent_audit_event_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_audit_event_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only (INV-ARC-016 VIII). Updates are not permitted in any environment.';
            END;
            $$;


--
-- Name: prevent_immutable_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_immutable_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF current_setting('cth.class_universe_destroying', true) = 'on' THEN
                RETURN OLD;
            END IF;
            RAISE EXCEPTION 'This table is immutable. Deletions are not permitted. These are permanent historical records.';
        END;
        $$;


--
-- Name: prevent_immutable_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_immutable_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
            BEGIN
                RAISE EXCEPTION 'This table is immutable (append-only). Updates are not permitted.';
            END;
            $$;


--
-- Name: prevent_ledger_transaction_rewrite(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_ledger_transaction_rewrite() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN IF OLD.seat_id IS DISTINCT FROM NEW.seat_id THEN RAISE EXCEPTION 'Immutable Ledger field: seat_id'; END IF;
IF OLD.target_seat_id IS DISTINCT FROM NEW.target_seat_id THEN RAISE EXCEPTION 'Immutable Ledger field: target_seat_id'; END IF;
IF OLD.actor_seat_id IS DISTINCT FROM NEW.actor_seat_id THEN RAISE EXCEPTION 'Immutable Ledger field: actor_seat_id'; END IF;
IF OLD.class_id IS DISTINCT FROM NEW.class_id THEN RAISE EXCEPTION 'Immutable Ledger field: class_id'; END IF;
IF OLD.join_code IS DISTINCT FROM NEW.join_code THEN RAISE EXCEPTION 'Immutable Ledger field: join_code'; END IF;
IF OLD.mechanism IS DISTINCT FROM NEW.mechanism THEN RAISE EXCEPTION 'Immutable Ledger field: mechanism'; END IF;
IF OLD.amount IS DISTINCT FROM NEW.amount THEN RAISE EXCEPTION 'Immutable Ledger field: amount'; END IF;
IF OLD.amount_cents IS DISTINCT FROM NEW.amount_cents THEN RAISE EXCEPTION 'Immutable Ledger field: amount_cents'; END IF;
IF OLD.timestamp IS DISTINCT FROM NEW.timestamp THEN RAISE EXCEPTION 'Immutable Ledger field: timestamp'; END IF;
IF OLD.account_type IS DISTINCT FROM NEW.account_type THEN RAISE EXCEPTION 'Immutable Ledger field: account_type'; END IF;
IF OLD.effective_at IS DISTINCT FROM NEW.effective_at THEN RAISE EXCEPTION 'Immutable Ledger field: effective_at'; END IF;
IF OLD.date_funds_available IS DISTINCT FROM NEW.date_funds_available THEN RAISE EXCEPTION 'Immutable Ledger field: date_funds_available'; END IF;
IF OLD.description IS DISTINCT FROM NEW.description THEN RAISE EXCEPTION 'Immutable Ledger field: description'; END IF;
IF OLD.correlation_id IS DISTINCT FROM NEW.correlation_id THEN RAISE EXCEPTION 'Immutable Ledger field: correlation_id'; END IF;
IF OLD.original_transaction_id IS DISTINCT FROM NEW.original_transaction_id THEN RAISE EXCEPTION 'Immutable Ledger field: original_transaction_id'; END IF;
IF OLD.policy_id IS DISTINCT FROM NEW.policy_id THEN RAISE EXCEPTION 'Immutable Ledger field: policy_id'; END IF;
IF OLD.type IS DISTINCT FROM NEW.type THEN RAISE EXCEPTION 'Immutable Ledger field: type'; END IF;
IF OLD.compensation_subtype IS DISTINCT FROM NEW.compensation_subtype THEN RAISE EXCEPTION 'Immutable Ledger field: compensation_subtype'; END IF;
IF OLD.command_reservation_id IS DISTINCT FROM NEW.command_reservation_id THEN RAISE EXCEPTION 'Immutable Ledger field: command_reservation_id'; END IF;
IF OLD.posting_sequence IS DISTINCT FROM NEW.posting_sequence THEN RAISE EXCEPTION 'Immutable Ledger field: posting_sequence'; END IF;
IF OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key THEN RAISE EXCEPTION 'Immutable Ledger field: idempotency_key'; END IF;
IF OLD.feat_code IS DISTINCT FROM NEW.feat_code THEN RAISE EXCEPTION 'Immutable Ledger field: feat_code'; END IF;
IF OLD.reversal_transaction_id IS DISTINCT FROM NEW.reversal_transaction_id THEN RAISE EXCEPTION 'Immutable Ledger field: reversal_transaction_id'; END IF;
IF OLD.compensation_origin_locator IS DISTINCT FROM NEW.compensation_origin_locator THEN RAISE EXCEPTION 'Immutable Ledger field: compensation_origin_locator'; END IF;
IF OLD.compensation_amount_cents IS DISTINCT FROM NEW.compensation_amount_cents THEN RAISE EXCEPTION 'Immutable Ledger field: compensation_amount_cents'; END IF;
IF OLD.correction_intent_locator IS DISTINCT FROM NEW.correction_intent_locator THEN RAISE EXCEPTION 'Immutable Ledger field: correction_intent_locator'; END IF;
IF OLD.posted_at IS NOT NULL AND OLD.posted_at IS DISTINCT FROM NEW.posted_at THEN RAISE EXCEPTION 'Write-once Ledger field: posted_at'; END IF;
IF OLD.lineage_event_id IS NOT NULL AND OLD.lineage_event_id IS DISTINCT FROM NEW.lineage_event_id THEN RAISE EXCEPTION 'Write-once Ledger field: lineage_event_id'; END IF;
IF OLD.lineage_token IS NOT NULL AND OLD.lineage_token IS DISTINCT FROM NEW.lineage_token THEN RAISE EXCEPTION 'Write-once Ledger field: lineage_token'; END IF;
IF OLD.lineage_version IS NOT NULL AND OLD.lineage_version IS DISTINCT FROM NEW.lineage_version THEN RAISE EXCEPTION 'Write-once Ledger field: lineage_version'; END IF; RETURN NEW; END; $$;


--
-- Name: prevent_payroll_event_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_payroll_event_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Class or teacher-account destruction declares itself (SET LOCAL).
    IF coalesce(current_setting('cth.class_universe_destroying', true), 'off') = 'on' THEN
        RETURN OLD;
    END IF;
    -- Lawful seat removal: the row's seat is already deleted and this DELETE is
    -- the FK cascade destroying the seat's payroll history with it
    -- (INV-ARC-013, INV-CORE-000 §III.6, DOM-PROD-001 §XI.3).
    IF NOT EXISTS (SELECT 1 FROM seats WHERE id = OLD.target_seat_id) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'payroll_event is append-only (DOM-PROD-001 §XI.3). Correct a payroll outcome with a reversal through FEAT-PROD-003. Rows are removed only with their seat, or when the class universe is destroyed.';
END;
$$;


--
-- Name: prevent_payroll_event_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_payroll_event_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NOT payroll_creator_is_uncommitted(OLD.xmin)
               OR OLD.lineage_event_id IS NOT NULL
               OR OLD.lineage_token IS NOT NULL
               OR OLD.lineage_version IS NOT NULL
               OR NEW.lineage_event_id IS NULL
               OR NEW.lineage_token IS NULL
               OR NEW.lineage_version IS NULL
               OR NEW.summary_json::text IS DISTINCT FROM OLD.summary_json::text
               OR (to_jsonb(NEW) - ARRAY['lineage_event_id','lineage_token','lineage_version'])
                    IS DISTINCT FROM
                  (to_jsonb(OLD) - ARRAY['lineage_event_id','lineage_token','lineage_version'])
            THEN
                RAISE EXCEPTION 'payroll_event is append-only; lineage initializes once in the creating transaction only';
            END IF;
            RETURN NEW;
        END;
        $$;


--
-- Name: prevent_payroll_settings_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_payroll_settings_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Class or teacher-account destruction declares itself (SET LOCAL).
    IF coalesce(current_setting('cth.class_universe_destroying', true), 'off') = 'on' THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION 'payroll_settings is append-only (DOM-POL-001 §VI.2). A payroll change is a new row effective at the next payroll date. Rows are removed only when the class universe is destroyed.';
END;
$$;


--
-- Name: prevent_payroll_settings_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.prevent_payroll_settings_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    RAISE EXCEPTION 'payroll_settings is append-only (DOM-POL-001 §VI.2). A payroll change is a new row effective at the next payroll date.';
                END;
                $$;


--
-- Name: require_attendance_invalidation_lineage(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.require_attendance_invalidation_lineage() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE final_row attendance_interval_invalidation%ROWTYPE;
    BEGIN
      SELECT * INTO final_row FROM attendance_interval_invalidation WHERE id=NEW.id;
      IF NOT FOUND THEN RETURN NULL; END IF;
      IF final_row.lineage_event_id IS NULL OR final_row.lineage_token IS NULL OR final_row.lineage_version IS NULL
        OR NOT EXISTS (SELECT 1 FROM audit_events a WHERE a.id=final_row.lineage_event_id
          AND payroll_creator_is_uncommitted(a.xmin) AND a.table_name='attendance_interval_invalidation'
          AND a.row_pk=final_row.id::text AND a.class_id=final_row.class_id AND a.chain_scope='class:'||final_row.class_id
          AND a.operation='INSERT' AND a.feat_id='FEAT-PROD-005'
          AND a.hmac_signature=final_row.lineage_token AND a.signature_version=final_row.lineage_version) THEN
        RAISE EXCEPTION 'New attendance invalidation requires matching creation lineage before commit';
      END IF;
      RETURN NULL;
    END; $$;


--
-- Name: require_ledger_creation_sequence(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.require_ledger_creation_sequence() RETURNS trigger
    LANGUAGE plpgsql
    AS $$ BEGIN
        IF NEW.posting_sequence IS NULL OR NEW.posting_sequence <= 0 THEN
            RAISE EXCEPTION 'New Ledger effects require immutable creation sequence';
        END IF; RETURN NEW; END; $$;


--
-- Name: require_ledger_v3_creation_lineage(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.require_ledger_v3_creation_lineage() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
    DECLARE saved ledger_transaction%ROWTYPE;
    BEGIN
      SELECT * INTO saved FROM ledger_transaction WHERE id=NEW.id;
      IF NOT FOUND THEN RETURN NEW; END IF;
      IF saved.lineage_event_id IS NULL OR saved.lineage_token IS NULL OR saved.lineage_version <> 3
        OR NOT EXISTS(SELECT 1 FROM audit_events a WHERE a.id=saved.lineage_event_id AND a.table_name='ledger_transaction'
          AND a.row_pk=saved.id::text AND a.class_id=saved.class_id AND a.operation='INSERT'
          AND a.chain_scope='class:'||saved.class_id AND a.signature_version=3 AND a.hmac_signature=saved.lineage_token)
        THEN RAISE EXCEPTION 'New Ledger effect requires canonical version-three creation lineage'; END IF;
      RETURN NEW;
    END; $$;


--
-- Name: require_payroll_lineage_at_commit(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.require_payroll_lineage_at_commit() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE final_row payroll_event%ROWTYPE;
        BEGIN
            SELECT * INTO final_row FROM payroll_event WHERE id = NEW.id;
            -- Existing lifecycle guards alone authorize removal; an INSERT
            -- followed by lawful seat/class destruction leaves no row to attest.
            IF NOT FOUND THEN RETURN NULL; END IF;
            IF final_row.lineage_event_id IS NULL
               OR final_row.lineage_token IS NULL
               OR final_row.lineage_version IS NULL
               OR NOT EXISTS (
                   SELECT 1 FROM audit_events a
                   WHERE a.id = final_row.lineage_event_id
                     AND payroll_creator_is_uncommitted(a.xmin)
                     AND a.table_name = 'payroll_event'
                     AND a.row_pk = final_row.id::text
                     AND a.operation = 'INSERT'
                     AND a.class_id = final_row.class_id
                     AND a.chain_scope = 'class:' || final_row.class_id
                     AND a.hmac_signature = final_row.lineage_token
                     AND a.signature_version = final_row.lineage_version
                     AND (a.feat_id IN ('FEAT-PROD-003','FEAT-PROD-004','FEAT-PROD-005')
                          OR (a.feat_id = 'FEAT-STOR-003' AND final_row.payroll_event_type = 'manual_credit'))
               ) THEN
                RAISE EXCEPTION 'new payroll_event requires matching creation audit lineage before commit';
            END IF;
            RETURN NULL;
        END;
        $$;


--
-- Name: require_payroll_lineage_at_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.require_payroll_lineage_at_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        BEGIN
            IF NEW.lineage_event_id IS NOT NULL OR NEW.lineage_token IS NOT NULL
               OR NEW.lineage_version IS NOT NULL THEN
                RAISE EXCEPTION 'payroll lineage must initialize after INSERT';
            END IF;
            RETURN NEW;
        END;
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: actor_request_trace; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: actor_request_trace_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.actor_request_trace_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: actor_request_trace_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.actor_request_trace_id_seq OWNED BY public.actor_request_trace.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: announcements; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: announcements_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.announcements_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: announcements_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.announcements_id_seq OWNED BY public.announcements.id;


--
-- Name: assessment_events; Type: TABLE; Schema: public; Owner: -
--

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
    "timestamp" timestamp with time zone NOT NULL,
    bill_cycle_id integer,
    ledger_transaction_id integer,
    notes text,
    reason text,
    reversed_by_seat_id integer
);


--
-- Name: assessment_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.assessment_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: assessment_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.assessment_events_id_seq OWNED BY public.assessment_events.id;


--
-- Name: attendance_interval_invalidation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attendance_interval_invalidation (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    target_seat_id integer NOT NULL,
    actor_seat_id integer NOT NULL,
    opening_event_id integer NOT NULL,
    closing_event_id integer NOT NULL,
    recorded_at timestamp with time zone NOT NULL,
    reason_code character varying(32) NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    correlation_id character varying(100) NOT NULL,
    receipt_json json NOT NULL,
    lineage_event_id integer,
    lineage_token character varying(64),
    lineage_version integer,
    CONSTRAINT ck_attendance_invalidation_reason CHECK ((reason_code IN ('INVALID_ATTENDANCE', 'NON_WORK_ACTIVITY', 'DUPLICATE_PARTICIPATION')))
);


--
-- Name: attendance_interval_invalidation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attendance_interval_invalidation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attendance_interval_invalidation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attendance_interval_invalidation_id_seq OWNED BY public.attendance_interval_invalidation.id;


--
-- Name: attendance_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.attendance_sessions (
    id integer NOT NULL,
    target_seat_id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    actor_seat_id integer NOT NULL,
    mechanism character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    reason_code character varying(32) NOT NULL,
    hall_pass_id character varying(100),
    "timestamp" timestamp with time zone NOT NULL,
    seat_id integer
);


--
-- Name: attendance_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.attendance_sessions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: attendance_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.attendance_sessions_id_seq OWNED BY public.attendance_sessions.id;


--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: audit_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_events_id_seq OWNED BY public.audit_events.id;


--
-- Name: bill_cycles; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: bill_cycles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bill_cycles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bill_cycles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bill_cycles_id_seq OWNED BY public.bill_cycles.id;


--
-- Name: chain_heads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.chain_heads (
    chain_scope character varying(64) NOT NULL,
    latest_hash character varying(64) NOT NULL,
    latest_sequence integer NOT NULL,
    event_count integer NOT NULL,
    last_updated_utc timestamp with time zone NOT NULL
);


--
-- Name: class_features; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.class_features (
    class_id character varying(36) NOT NULL,
    feature character varying(32) NOT NULL,
    economic_version_id character varying(36),
    effective_at timestamp with time zone NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_class_features_feature CHECK ((feature IN ('payroll', 'insurance', 'banking', 'rent', 'hall_pass', 'store')))
);


--
-- Name: classes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.classes (
    class_id character varying(36) NOT NULL,
    class_public_id character varying(36) NOT NULL,
    join_code character varying(20) NOT NULL,
    section character varying(50),
    display_name character varying(100),
    class_timezone character varying(64) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    join_code_token character varying(20),
    teacher_user_id uuid,
    unpaid_work_notice_acknowledged_at timestamp with time zone
);


--
-- Name: configuration_import_receipts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.configuration_import_receipts (
    class_id character varying(36) NOT NULL,
    operation_id character varying(36) NOT NULL,
    actor_seat_id integer NOT NULL,
    fingerprint character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    accepted_at timestamp with time zone NOT NULL,
    result json NOT NULL
);


--
-- Name: credential_operations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credential_operations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    purpose public.credential_operation_purpose_enum NOT NULL,
    stage public.credential_operation_stage_enum NOT NULL,
    authorized_generation integer NOT NULL,
    session_binding_hash character varying(64) NOT NULL,
    deadline_at timestamp with time zone NOT NULL,
    pending_totp_encrypted character varying(200),
    old_credential_id text,
    new_credential_id text,
    retirement_intent_at timestamp with time zone,
    retry_after_at timestamp with time zone,
    attempt_count integer DEFAULT 0 NOT NULL,
    error_category character varying(64),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    step_up_challenge_hash character varying(64),
    step_up_issued_at timestamp with time zone,
    step_up_challenge_expires_at timestamp with time zone,
    step_up_token_id uuid,
    step_up_retain_until timestamp with time zone
);


--
-- Name: economic_engine; Type: TABLE; Schema: public; Owner: -
--

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
    effective_at timestamp with time zone NOT NULL,
    CONSTRAINT ck_economic_engine_accrual_freq CHECK (((interest_accrual_frequency IS NULL) OR (interest_accrual_frequency IN ('daily', 'weekly', 'monthly')))),
    CONSTRAINT ck_economic_engine_calc_type CHECK (((interest_calculation_type IS NULL) OR (interest_calculation_type IN ('simple', 'compound')))),
    CONSTRAINT ck_economic_engine_compound_freq CHECK (((compound_frequency IS NULL) OR (compound_frequency IN ('never', 'daily', 'weekly', 'monthly')))),
    CONSTRAINT ck_economic_engine_flat_overdraft_fee CHECK (((flat_overdraft_fee IS NULL) OR (flat_overdraft_fee >= (0)::numeric))),
    CONSTRAINT ck_economic_engine_hours CHECK (((expected_weekly_hours IS NULL) OR (expected_weekly_hours > (0)::double precision))),
    CONSTRAINT ck_economic_engine_mode CHECK ((economy_policy_mode IN ('tight', 'default', 'comfortable'))),
    CONSTRAINT ck_economic_engine_not_retroactive CHECK ((effective_at >= created_at)),
    CONSTRAINT ck_economic_engine_overdraft_fee_exclusive CHECK ((NOT ((flat_overdraft_fee IS NOT NULL) AND (progressive_overdraft_fee IS NOT NULL)))),
    CONSTRAINT ck_economic_engine_payout_freq CHECK (((interest_payout_frequency IS NULL) OR (interest_payout_frequency IN ('weekly', 'monthly')))),
    CONSTRAINT ck_economic_engine_rate CHECK (((interest_rate IS NULL) OR ((interest_rate >= (0)::numeric) AND (interest_rate <= 1.0))))
);


--
-- Name: entitlement_events; Type: TABLE; Schema: public; Owner: -
--

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
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL
);


--
-- Name: feature_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.feature_settings (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    economy_policy_mode character varying(20) NOT NULL,
    economy_policy_updated_at timestamp with time zone NOT NULL,
    economy_policy_alignment_status character varying(32),
    economy_last_rebalanced_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: feature_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.feature_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: feature_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.feature_settings_id_seq OWNED BY public.feature_settings.id;


--
-- Name: hall_pass_logs; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: hall_pass_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hall_pass_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hall_pass_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hall_pass_logs_id_seq OWNED BY public.hall_pass_logs.id;


--
-- Name: hall_pass_settings; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: hall_pass_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.hall_pass_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hall_pass_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.hall_pass_settings_id_seq OWNED BY public.hall_pass_settings.id;


--
-- Name: identity_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.identity_profiles (
    id integer NOT NULL,
    seat_id integer NOT NULL,
    class_id character varying(36),
    profile_type character varying(32) NOT NULL,
    first_name bytea NOT NULL,
    last_name bytea NOT NULL,
    notes bytea,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL
);


--
-- Name: identity_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.identity_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: identity_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.identity_profiles_id_seq OWNED BY public.identity_profiles.id;


--
-- Name: insurance_claim_productivity_dates; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.insurance_claim_productivity_dates (
    id integer NOT NULL,
    claim_id character varying(36) NOT NULL,
    entitlement_id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    claim_date date NOT NULL,
    student_claimed_hours numeric(6,2) NOT NULL,
    teacher_approved_hours numeric(6,2),
    adjustment_note text,
    recognized_payout numeric(12,2),
    student_explanation text NOT NULL
);


--
-- Name: insurance_claim_productivity_dates_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.insurance_claim_productivity_dates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: insurance_claim_productivity_dates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.insurance_claim_productivity_dates_id_seq OWNED BY public.insurance_claim_productivity_dates.id;


--
-- Name: insurance_claims; Type: TABLE; Schema: public; Owner: -
--

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
    result_amount numeric(12,2),
    payroll_event_id integer,
    ledger_transaction_id integer,
    filing_window_override_reason text
);


--
-- Name: insurance_policies; Type: TABLE; Schema: public; Owner: -
--

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
    title character varying(120),
    description text,
    tier_name character varying(60),
    tier_group character varying(60),
    availability_state character varying(16) DEFAULT 'IN_USE'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    created_by_seat_id integer,
    retired_at timestamp with time zone,
    bill_preview_days integer,
    nonpayment_mode character varying(24),
    cancel_after_days integer,
    marketing_badge character varying(40),
    supersedes_policy_uuid character varying(36),
    tier_group_id character varying(36),
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


--
-- Name: insurance_tier_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.insurance_tier_groups (
    class_id character varying(36) NOT NULL,
    group_id character varying(36) NOT NULL,
    name character varying(60) NOT NULL
);


--
-- Name: interpretation_cycle_record; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: issue_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.issue_categories (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    category_type character varying(50) NOT NULL,
    is_active boolean NOT NULL,
    display_order integer,
    created_at timestamp with time zone
);


--
-- Name: issue_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.issue_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: issue_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.issue_categories_id_seq OWNED BY public.issue_categories.id;


--
-- Name: issue_resolution_actions; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: issue_resolution_actions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.issue_resolution_actions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: issue_resolution_actions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.issue_resolution_actions_id_seq OWNED BY public.issue_resolution_actions.id;


--
-- Name: issue_status_history; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: issue_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.issue_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: issue_status_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.issue_status_history_id_seq OWNED BY public.issue_status_history.id;


--
-- Name: issues; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.issues (
    id integer NOT NULL,
    actor_public_id character varying(64) NOT NULL,
    reviewer_public_id character varying(64),
    class_public_id character varying(36) NOT NULL,
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
    sysadmin_reviewed_at timestamp with time zone,
    sysadmin_notes text,
    sysadmin_resolved_at timestamp with time zone,
    closed_at timestamp with time zone,
    closed_by_type character varying(20),
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone,
    class_label character varying(255)
);


--
-- Name: issues_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.issues_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: issues_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.issues_id_seq OWNED BY public.issues.id;


--
-- Name: ledger_balance_snapshot; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: ledger_balance_snapshot_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ledger_balance_snapshot_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ledger_balance_snapshot_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ledger_balance_snapshot_id_seq OWNED BY public.ledger_balance_snapshot.id;


--
-- Name: ledger_command_reservation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ledger_command_reservation (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    feat_code character varying(100) NOT NULL,
    idempotency_key character varying(128) NOT NULL,
    replay_fingerprint character varying(128) NOT NULL,
    fingerprint_version integer NOT NULL,
    accepted_at timestamp with time zone NOT NULL
);


--
-- Name: ledger_command_reservation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ledger_command_reservation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ledger_command_reservation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ledger_command_reservation_id_seq OWNED BY public.ledger_command_reservation.id;


--
-- Name: ledger_transaction; Type: TABLE; Schema: public; Owner: -
--

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
    command_reservation_id integer,
    compensation_origin_locator character varying(128),
    compensation_amount_cents integer,
    correction_intent_locator character varying(128),
    CONSTRAINT ck_ledger_attributable_recovery CHECK (((compensation_amount_cents IS NULL) OR ((compensation_amount_cents >= 0) AND ((compensation_amount_cents = 0) OR ((amount_cents = (- compensation_amount_cents)) AND (compensation_origin_locator IS NOT NULL) AND (correction_intent_locator IS NOT NULL))))))
);


--
-- Name: ledger_transaction_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ledger_transaction_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ledger_transaction_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ledger_transaction_id_seq OWNED BY public.ledger_transaction.id;


--
-- Name: obligation_command_reservation; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: obligation_command_reservation_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.obligation_command_reservation_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: obligation_command_reservation_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.obligation_command_reservation_id_seq OWNED BY public.obligation_command_reservation.id;


--
-- Name: operational_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operational_events (
    id character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    correlation_id character varying(64),
    domain character varying(100) NOT NULL,
    level character varying(20) NOT NULL,
    message text,
    payload json
);


--
-- Name: passkey_credentials; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.passkey_credentials (
    id integer NOT NULL,
    credential_id text NOT NULL,
    authenticator_name character varying(100),
    created_at timestamp with time zone NOT NULL,
    last_used timestamp with time zone,
    user_id uuid NOT NULL
);


--
-- Name: passkey_credentials_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.passkey_credentials_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: passkey_credentials_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.passkey_credentials_id_seq OWNED BY public.passkey_credentials.id;


--
-- Name: payroll_cycle_completion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_cycle_completion (
    id character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    payroll_cycle_id character varying(36) NOT NULL,
    completed_at timestamp with time zone NOT NULL
);


--
-- Name: payroll_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_event (
    id integer NOT NULL,
    class_id character varying(36) NOT NULL,
    target_seat_id integer NOT NULL,
    actor_seat_id integer NOT NULL,
    correlation_id character varying(100) NOT NULL,
    idempotency_key character varying(255) NOT NULL,
    policy_uuid character varying(36),
    mechanism character varying(20) NOT NULL,
    payroll_event_type character varying(20) NOT NULL,
    recorded_at timestamp with time zone NOT NULL,
    payroll_cycle_id character varying(36),
    summary_json json,
    lineage_event_id integer,
    lineage_token character varying(64),
    lineage_version integer,
    CONSTRAINT ck_payroll_event_payroll_policy CHECK ((((payroll_event_type)::text <> 'payroll'::text) OR (policy_uuid IS NOT NULL)))
);


--
-- Name: payroll_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payroll_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payroll_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payroll_event_id_seq OWNED BY public.payroll_event.id;


--
-- Name: payroll_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payroll_settings (
    policy_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    pay_rate numeric(18,8) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    overtime_threshold double precision,
    overtime_threshold_unit character varying(20),
    max_time_per_day double precision,
    max_time_per_day_unit character varying(20),
    pay_schedule_type character varying(20) NOT NULL,
    first_pay_date timestamp with time zone NOT NULL,
    rounding_mode character varying(20),
    effective_date timestamp with time zone NOT NULL,
    CONSTRAINT ck_payroll_settings_not_retroactive CHECK ((effective_date >= created_at)),
    CONSTRAINT ck_payroll_settings_schedule_type CHECK ((pay_schedule_type IN ('weekly', 'biweekly', 'monthly')))
);


--
-- Name: pending_actions; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: recovery_class_challenges; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: recovery_requests; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recovery_requests (
    id integer NOT NULL,
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
    setup_username text,
    user_id uuid NOT NULL
);


--
-- Name: recovery_requests_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recovery_requests_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recovery_requests_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recovery_requests_id_seq OWNED BY public.recovery_requests.id;


--
-- Name: rent_settings; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: rent_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rent_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rent_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rent_settings_id_seq OWNED BY public.rent_settings.id;


--
-- Name: seats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.seats (
    id integer NOT NULL,
    public_id character varying(36) NOT NULL,
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
    updated_at timestamp with time zone NOT NULL,
    user_id uuid
);


--
-- Name: seats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.seats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: seats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.seats_id_seq OWNED BY public.seats.id;


--
-- Name: store_item_visibility; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.store_item_visibility (
    id integer NOT NULL,
    seat_id integer NOT NULL,
    product_lineage_uuid character varying(36) NOT NULL
);


--
-- Name: store_item_visibility_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.store_item_visibility_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: store_item_visibility_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.store_item_visibility_id_seq OWNED BY public.store_item_visibility.id;


--
-- Name: store_products; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.store_products (
    policy_uuid character varying(36) NOT NULL,
    product_lineage_uuid character varying(36) NOT NULL,
    class_id character varying(36) NOT NULL,
    name character varying(100) NOT NULL,
    description text,
    price numeric(12,2),
    item_type character varying(20) DEFAULT 'delayed'::character varying NOT NULL,
    inventory_total integer,
    auto_delist_date timestamp with time zone,
    auto_expiry_days integer,
    is_long_term_goal boolean DEFAULT false NOT NULL,
    bypass_cwi_warnings boolean DEFAULT false NOT NULL,
    is_bundle boolean DEFAULT false NOT NULL,
    bundle_quantity integer,
    bulk_discount_enabled boolean DEFAULT false NOT NULL,
    bulk_discount_quantity integer,
    bulk_discount_percentage double precision,
    collective_goal_type character varying(20),
    collective_goal_target integer,
    collective_goal_expires_at timestamp with time zone,
    collective_goal_instance_code character varying(36),
    redemption_prompt text,
    availability_state character varying(16) DEFAULT 'IN_USE'::character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    created_by_seat_id integer,
    retired_at timestamp with time zone,
    holding_limit integer,
    direct_purchase_allowed boolean DEFAULT true NOT NULL,
    available_with_overdue_obligations boolean DEFAULT false NOT NULL,
    activation_at timestamp with time zone,
    economic_role character varying(20) NOT NULL,
    CONSTRAINT ck_store_products_availability_state CHECK ((availability_state IN ('IN_USE', 'HIDDEN', 'RETIRED'))),
    CONSTRAINT ck_store_products_economic_role CHECK ((economic_role IN ('necessity', 'convenience', 'add_on'))),
    CONSTRAINT ck_store_products_holding_limit_positive CHECK (((holding_limit IS NULL) OR (holding_limit > 0))),
    CONSTRAINT ck_store_products_item_type CHECK ((item_type IN ('immediate', 'delayed', 'collective', 'hall_pass', 'privilege')))
);


--
-- Name: student_recovery_codes; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: student_recovery_codes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.student_recovery_codes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: student_recovery_codes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.student_recovery_codes_id_seq OWNED BY public.student_recovery_codes.id;


--
-- Name: teacher_signup_attempts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.teacher_signup_attempts (
    nonce_hash character varying(64) NOT NULL,
    payload_encrypted text NOT NULL,
    expires_at timestamp with time zone NOT NULL
);


--
-- Name: ticket_correlation_pack; Type: TABLE; Schema: public; Owner: -
--

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


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
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
    hall_pass_verify_token character varying(64),
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    configuration_export_verifier character varying(64),
    configuration_export_expires_at timestamp with time zone,
    credential_generation integer DEFAULT 1 NOT NULL
);


--
-- Name: actor_request_trace id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actor_request_trace ALTER COLUMN id SET DEFAULT nextval('public.actor_request_trace_id_seq'::regclass);


--
-- Name: announcements id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements ALTER COLUMN id SET DEFAULT nextval('public.announcements_id_seq'::regclass);


--
-- Name: assessment_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events ALTER COLUMN id SET DEFAULT nextval('public.assessment_events_id_seq'::regclass);


--
-- Name: attendance_interval_invalidation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation ALTER COLUMN id SET DEFAULT nextval('public.attendance_interval_invalidation_id_seq'::regclass);


--
-- Name: attendance_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_sessions ALTER COLUMN id SET DEFAULT nextval('public.attendance_sessions_id_seq'::regclass);


--
-- Name: audit_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events ALTER COLUMN id SET DEFAULT nextval('public.audit_events_id_seq'::regclass);


--
-- Name: bill_cycles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_cycles ALTER COLUMN id SET DEFAULT nextval('public.bill_cycles_id_seq'::regclass);


--
-- Name: feature_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feature_settings ALTER COLUMN id SET DEFAULT nextval('public.feature_settings_id_seq'::regclass);


--
-- Name: hall_pass_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_logs ALTER COLUMN id SET DEFAULT nextval('public.hall_pass_logs_id_seq'::regclass);


--
-- Name: hall_pass_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_settings ALTER COLUMN id SET DEFAULT nextval('public.hall_pass_settings_id_seq'::regclass);


--
-- Name: identity_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_profiles ALTER COLUMN id SET DEFAULT nextval('public.identity_profiles_id_seq'::regclass);


--
-- Name: insurance_claim_productivity_dates id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claim_productivity_dates ALTER COLUMN id SET DEFAULT nextval('public.insurance_claim_productivity_dates_id_seq'::regclass);


--
-- Name: issue_categories id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_categories ALTER COLUMN id SET DEFAULT nextval('public.issue_categories_id_seq'::regclass);


--
-- Name: issue_resolution_actions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_resolution_actions ALTER COLUMN id SET DEFAULT nextval('public.issue_resolution_actions_id_seq'::regclass);


--
-- Name: issue_status_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_status_history ALTER COLUMN id SET DEFAULT nextval('public.issue_status_history_id_seq'::regclass);


--
-- Name: issues id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issues ALTER COLUMN id SET DEFAULT nextval('public.issues_id_seq'::regclass);


--
-- Name: ledger_balance_snapshot id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot ALTER COLUMN id SET DEFAULT nextval('public.ledger_balance_snapshot_id_seq'::regclass);


--
-- Name: ledger_command_reservation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_command_reservation ALTER COLUMN id SET DEFAULT nextval('public.ledger_command_reservation_id_seq'::regclass);


--
-- Name: ledger_transaction id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction ALTER COLUMN id SET DEFAULT nextval('public.ledger_transaction_id_seq'::regclass);


--
-- Name: obligation_command_reservation id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_command_reservation ALTER COLUMN id SET DEFAULT nextval('public.obligation_command_reservation_id_seq'::regclass);


--
-- Name: passkey_credentials id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey_credentials ALTER COLUMN id SET DEFAULT nextval('public.passkey_credentials_id_seq'::regclass);


--
-- Name: payroll_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_event ALTER COLUMN id SET DEFAULT nextval('public.payroll_event_id_seq'::regclass);


--
-- Name: recovery_requests id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_requests ALTER COLUMN id SET DEFAULT nextval('public.recovery_requests_id_seq'::regclass);


--
-- Name: rent_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rent_settings ALTER COLUMN id SET DEFAULT nextval('public.rent_settings_id_seq'::regclass);


--
-- Name: seats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats ALTER COLUMN id SET DEFAULT nextval('public.seats_id_seq'::regclass);


--
-- Name: store_item_visibility id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_item_visibility ALTER COLUMN id SET DEFAULT nextval('public.store_item_visibility_id_seq'::regclass);


--
-- Name: student_recovery_codes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes ALTER COLUMN id SET DEFAULT nextval('public.student_recovery_codes_id_seq'::regclass);


--
-- Name: actor_request_trace actor_request_trace_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actor_request_trace
    ADD CONSTRAINT actor_request_trace_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: announcements announcements_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_pkey PRIMARY KEY (id);


--
-- Name: assessment_events assessment_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_pkey PRIMARY KEY (id);


--
-- Name: attendance_interval_invalidation attendance_interval_invalidation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT attendance_interval_invalidation_pkey PRIMARY KEY (id);


--
-- Name: attendance_sessions attendance_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_event_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_event_hash_key UNIQUE (event_hash);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: bill_cycles bill_cycles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT bill_cycles_pkey PRIMARY KEY (id);


--
-- Name: chain_heads chain_heads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.chain_heads
    ADD CONSTRAINT chain_heads_pkey PRIMARY KEY (chain_scope);


--
-- Name: ledger_transaction ck_ledger_transaction_type_closed_vocabulary; Type: CHECK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE public.ledger_transaction
    ADD CONSTRAINT ck_ledger_transaction_type_closed_vocabulary CHECK (((type IS NULL) OR (type IN ('interest', 'Interest', 'reversal', 'REVERSAL', 'withdrawal', 'Withdrawal', 'deposit', 'Deposit', 'internal_transfer', 'insurance_reimbursement', 'insurance_premium', 'purchase', 'refund', 'overdraft_fee', 'payroll', 'payroll_correction', 'manual_payment', 'penalty', 'issue_reversal', 'issue_compensation', 'rent_payment', 'void_item_removed')))) NOT VALID;


--
-- Name: classes classes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_pkey PRIMARY KEY (class_id);


--
-- Name: configuration_import_receipts configuration_import_receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuration_import_receipts
    ADD CONSTRAINT configuration_import_receipts_pkey PRIMARY KEY (class_id, operation_id);


--
-- Name: credential_operations credential_operations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credential_operations
    ADD CONSTRAINT credential_operations_pkey PRIMARY KEY (id);


--
-- Name: economic_engine economic_engine_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT economic_engine_pkey PRIMARY KEY (economic_version_id);


--
-- Name: entitlement_events entitlement_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT entitlement_events_pkey PRIMARY KEY (event_id);


--
-- Name: feature_settings feature_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feature_settings
    ADD CONSTRAINT feature_settings_pkey PRIMARY KEY (id);


--
-- Name: hall_pass_logs hall_pass_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_pkey PRIMARY KEY (id);


--
-- Name: hall_pass_settings hall_pass_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_settings
    ADD CONSTRAINT hall_pass_settings_pkey PRIMARY KEY (id);


--
-- Name: identity_profiles identity_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT identity_profiles_pkey PRIMARY KEY (id);


--
-- Name: insurance_claim_productivity_dates insurance_claim_productivity_dates_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT insurance_claim_productivity_dates_pkey PRIMARY KEY (id);


--
-- Name: insurance_claims insurance_claims_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_pkey PRIMARY KEY (claim_id);


--
-- Name: insurance_policies insurance_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT insurance_policies_pkey PRIMARY KEY (policy_uuid);


--
-- Name: insurance_tier_groups insurance_tier_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_tier_groups
    ADD CONSTRAINT insurance_tier_groups_pkey PRIMARY KEY (class_id, group_id);


--
-- Name: interpretation_cycle_record interpretation_cycle_record_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interpretation_cycle_record
    ADD CONSTRAINT interpretation_cycle_record_pkey PRIMARY KEY (id);


--
-- Name: issue_categories issue_categories_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_categories
    ADD CONSTRAINT issue_categories_name_key UNIQUE (name);


--
-- Name: issue_categories issue_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_categories
    ADD CONSTRAINT issue_categories_pkey PRIMARY KEY (id);


--
-- Name: issue_resolution_actions issue_resolution_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_resolution_actions
    ADD CONSTRAINT issue_resolution_actions_pkey PRIMARY KEY (id);


--
-- Name: issue_status_history issue_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_status_history
    ADD CONSTRAINT issue_status_history_pkey PRIMARY KEY (id);


--
-- Name: issues issues_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issues
    ADD CONSTRAINT issues_pkey PRIMARY KEY (id);


--
-- Name: ledger_balance_snapshot ledger_balance_snapshot_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_pkey PRIMARY KEY (id);


--
-- Name: ledger_command_reservation ledger_command_reservation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_command_reservation
    ADD CONSTRAINT ledger_command_reservation_pkey PRIMARY KEY (id);


--
-- Name: ledger_transaction ledger_transaction_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_pkey PRIMARY KEY (id);


--
-- Name: obligation_command_reservation obligation_command_reservation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT obligation_command_reservation_pkey PRIMARY KEY (id);


--
-- Name: operational_events operational_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operational_events
    ADD CONSTRAINT operational_events_pkey PRIMARY KEY (id);


--
-- Name: passkey_credentials passkey_credentials_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey_credentials
    ADD CONSTRAINT passkey_credentials_pkey PRIMARY KEY (id);


--
-- Name: payroll_cycle_completion payroll_cycle_completion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_cycle_completion
    ADD CONSTRAINT payroll_cycle_completion_pkey PRIMARY KEY (id);


--
-- Name: payroll_event payroll_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_pkey PRIMARY KEY (id);


--
-- Name: payroll_settings payroll_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_settings
    ADD CONSTRAINT payroll_settings_pkey PRIMARY KEY (policy_uuid);


--
-- Name: pending_actions pending_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_pkey PRIMARY KEY (pending_action_id);


--
-- Name: class_features pk_class_features; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT pk_class_features PRIMARY KEY (class_id, feature, effective_at);


--
-- Name: recovery_class_challenges recovery_class_challenges_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_class_challenges
    ADD CONSTRAINT recovery_class_challenges_pkey PRIMARY KEY (recovery_request_id, class_id);


--
-- Name: recovery_requests recovery_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_requests
    ADD CONSTRAINT recovery_requests_pkey PRIMARY KEY (id);


--
-- Name: rent_settings rent_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rent_settings
    ADD CONSTRAINT rent_settings_pkey PRIMARY KEY (id);


--
-- Name: seats seats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_pkey PRIMARY KEY (id);


--
-- Name: store_item_visibility store_item_visibility_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_item_visibility
    ADD CONSTRAINT store_item_visibility_pkey PRIMARY KEY (id);


--
-- Name: store_products store_products_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_products
    ADD CONSTRAINT store_products_pkey PRIMARY KEY (policy_uuid);


--
-- Name: student_recovery_codes student_recovery_codes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_pkey PRIMARY KEY (id);


--
-- Name: teacher_signup_attempts teacher_signup_attempts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.teacher_signup_attempts
    ADD CONSTRAINT teacher_signup_attempts_pkey PRIMARY KEY (nonce_hash);


--
-- Name: ticket_correlation_pack ticket_correlation_pack_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_correlation_pack
    ADD CONSTRAINT ticket_correlation_pack_pkey PRIMARY KEY (issue_id);


--
-- Name: attendance_interval_invalidation uq_attendance_invalidation_command; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT uq_attendance_invalidation_command UNIQUE (class_id, idempotency_key);


--
-- Name: attendance_interval_invalidation uq_attendance_invalidation_interval; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT uq_attendance_invalidation_interval UNIQUE (class_id, target_seat_id, opening_event_id, closing_event_id);


--
-- Name: audit_events uq_audit_chain_position; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT uq_audit_chain_position UNIQUE (chain_scope, sequence_number);


--
-- Name: ledger_balance_snapshot uq_balance_snapshot_scope; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT uq_balance_snapshot_scope UNIQUE (class_id, seat_id, account_type);


--
-- Name: bill_cycles uq_bill_cycles_ref_cycle; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT uq_bill_cycles_ref_cycle UNIQUE (internal_ref, cycle_number);


--
-- Name: economic_engine uq_economic_engine_class_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT uq_economic_engine_class_version UNIQUE (class_id, economic_version_id);


--
-- Name: hall_pass_settings uq_hall_pass_settings_policy_uuid; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_settings
    ADD CONSTRAINT uq_hall_pass_settings_policy_uuid UNIQUE (policy_uuid);


--
-- Name: insurance_claim_productivity_dates uq_icpd_claim_date; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT uq_icpd_claim_date UNIQUE (claim_id, claim_date);


--
-- Name: interpretation_cycle_record uq_interpretation_cycle_record_class_cycle; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interpretation_cycle_record
    ADD CONSTRAINT uq_interpretation_cycle_record_class_cycle UNIQUE (class_id, payroll_cycle_id);


--
-- Name: ledger_command_reservation uq_ledger_command_reservation_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_command_reservation
    ADD CONSTRAINT uq_ledger_command_reservation_identity UNIQUE (class_id, feat_code, idempotency_key);


--
-- Name: ledger_transaction uq_ledger_transaction_class_posting_sequence; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT uq_ledger_transaction_class_posting_sequence UNIQUE (class_id, posting_sequence);


--
-- Name: obligation_command_reservation uq_obligation_command_reservation_identity; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT uq_obligation_command_reservation_identity UNIQUE (class_id, command_name, idempotency_key);


--
-- Name: passkey_credentials uq_passkey_credentials_credential_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey_credentials
    ADD CONSTRAINT uq_passkey_credentials_credential_id UNIQUE (credential_id);


--
-- Name: payroll_cycle_completion uq_payroll_cycle_completion_class_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_cycle_completion
    ADD CONSTRAINT uq_payroll_cycle_completion_class_key UNIQUE (class_id, idempotency_key);


--
-- Name: payroll_event uq_payroll_event_replay_guard; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT uq_payroll_event_replay_guard UNIQUE (class_id, target_seat_id, correlation_id, idempotency_key, payroll_event_type);


--
-- Name: payroll_settings uq_payroll_settings_class_effective_created; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_settings
    ADD CONSTRAINT uq_payroll_settings_class_effective_created UNIQUE (class_id, effective_date, created_at);


--
-- Name: seats uq_seats_user_class; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT uq_seats_user_class UNIQUE (user_id, class_id);


--
-- Name: store_item_visibility uq_store_item_visibility_lineage_seat; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_item_visibility
    ADD CONSTRAINT uq_store_item_visibility_lineage_seat UNIQUE (product_lineage_uuid, seat_id);


--
-- Name: users uq_users_id; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT uq_users_id UNIQUE (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_actor_request_trace_actor_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actor_request_trace_actor_public_id ON public.actor_request_trace USING btree (actor_public_id);


--
-- Name: ix_actor_request_trace_actor_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actor_request_trace_actor_type ON public.actor_request_trace USING btree (actor_type);


--
-- Name: ix_actor_request_trace_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actor_request_trace_class_id ON public.actor_request_trace USING btree (class_id);


--
-- Name: ix_actor_request_trace_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actor_request_trace_created_at ON public.actor_request_trace USING btree (created_at);


--
-- Name: ix_actor_request_trace_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actor_request_trace_request_id ON public.actor_request_trace USING btree (request_id);


--
-- Name: ix_actor_trace_actor_public_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_actor_trace_actor_public_created ON public.actor_request_trace USING btree (actor_type, actor_public_id, created_at);


--
-- Name: ix_announcements_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_announcements_class_id ON public.announcements USING btree (class_id);


--
-- Name: ix_assessment_events_bill_cycle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_bill_cycle_id ON public.assessment_events USING btree (bill_cycle_id);


--
-- Name: ix_assessment_events_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_class_id ON public.assessment_events USING btree (class_id);


--
-- Name: ix_assessment_events_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_correlation_id ON public.assessment_events USING btree (correlation_id);


--
-- Name: ix_assessment_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_event_type ON public.assessment_events USING btree (event_type);


--
-- Name: ix_assessment_events_internal_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_internal_ref ON public.assessment_events USING btree (internal_ref);


--
-- Name: ix_assessment_events_ledger_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_ledger_transaction_id ON public.assessment_events USING btree (ledger_transaction_id);


--
-- Name: ix_assessment_events_obligation_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_obligation_type ON public.assessment_events USING btree (obligation_type);


--
-- Name: ix_assessment_events_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_policy_uuid ON public.assessment_events USING btree (policy_uuid);


--
-- Name: ix_assessment_events_reversed_by_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_reversed_by_seat_id ON public.assessment_events USING btree (reversed_by_seat_id);


--
-- Name: ix_assessment_events_seat_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_seat_class ON public.assessment_events USING btree (seat_id, class_id);


--
-- Name: ix_assessment_events_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_seat_id ON public.assessment_events USING btree (seat_id);


--
-- Name: ix_assessment_events_source_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_assessment_events_source_correlation_id ON public.assessment_events USING btree (source_correlation_id);


--
-- Name: ix_attendance_interval_invalidation_actor_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_interval_invalidation_actor_seat_id ON public.attendance_interval_invalidation USING btree (actor_seat_id);


--
-- Name: ix_attendance_interval_invalidation_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_interval_invalidation_class_id ON public.attendance_interval_invalidation USING btree (class_id);


--
-- Name: ix_attendance_interval_invalidation_target_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_interval_invalidation_target_seat_id ON public.attendance_interval_invalidation USING btree (target_seat_id);


--
-- Name: ix_attendance_sessions_actor_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_sessions_actor_seat_id ON public.attendance_sessions USING btree (actor_seat_id);


--
-- Name: ix_attendance_sessions_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_sessions_class_id ON public.attendance_sessions USING btree (class_id);


--
-- Name: ix_attendance_sessions_hall_pass_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_sessions_hall_pass_id ON public.attendance_sessions USING btree (hall_pass_id);


--
-- Name: ix_attendance_sessions_reason_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_sessions_reason_code ON public.attendance_sessions USING btree (reason_code);


--
-- Name: ix_attendance_sessions_target_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_sessions_target_seat_id ON public.attendance_sessions USING btree (target_seat_id);


--
-- Name: ix_attendance_sessions_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_attendance_sessions_timestamp ON public.attendance_sessions USING btree ("timestamp");


--
-- Name: ix_audit_events_chain_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_chain_scope ON public.audit_events USING btree (chain_scope);


--
-- Name: ix_audit_events_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_class_id ON public.audit_events USING btree (class_id);


--
-- Name: ix_audit_events_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_correlation_id ON public.audit_events USING btree (correlation_id);


--
-- Name: ix_audit_events_table_row; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_audit_events_table_row ON public.audit_events USING btree (table_name, row_pk);


--
-- Name: ix_bill_cycles_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bill_cycles_class_id ON public.bill_cycles USING btree (class_id);


--
-- Name: ix_bill_cycles_internal_ref; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bill_cycles_internal_ref ON public.bill_cycles USING btree (internal_ref);


--
-- Name: ix_bill_cycles_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_bill_cycles_policy_uuid ON public.bill_cycles USING btree (policy_uuid);


--
-- Name: ix_class_features_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_features_class_id ON public.class_features USING btree (class_id);


--
-- Name: ix_class_features_economic_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_class_features_economic_version_id ON public.class_features USING btree (economic_version_id);


--
-- Name: ix_classes_class_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_classes_class_public_id ON public.classes USING btree (class_public_id);


--
-- Name: ix_classes_join_code; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_classes_join_code ON public.classes USING btree (join_code);


--
-- Name: ix_classes_join_code_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_classes_join_code_token ON public.classes USING btree (join_code_token);


--
-- Name: ix_classes_teacher_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_classes_teacher_user_id ON public.classes USING btree (teacher_user_id);


--
-- Name: ix_configuration_import_receipts_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_configuration_import_receipts_expires_at ON public.configuration_import_receipts USING btree (expires_at);


--
-- Name: ix_credential_operations_deadline_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credential_operations_deadline_at ON public.credential_operations USING btree (deadline_at);


--
-- Name: ix_credential_operations_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_credential_operations_user_id ON public.credential_operations USING btree (user_id);


--
-- Name: ix_economic_engine_class_effective; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_economic_engine_class_effective ON public.economic_engine USING btree (class_id, effective_at);


--
-- Name: ix_economic_engine_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_economic_engine_class_id ON public.economic_engine USING btree (class_id);


--
-- Name: ix_economic_engine_previous_version_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_economic_engine_previous_version_id ON public.economic_engine USING btree (previous_version_id);


--
-- Name: ix_entitlement_events_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_class_id ON public.entitlement_events USING btree (class_id);


--
-- Name: ix_entitlement_events_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_correlation_id ON public.entitlement_events USING btree (correlation_id);


--
-- Name: ix_entitlement_events_entitlement_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_entitlement_id ON public.entitlement_events USING btree (entitlement_id);


--
-- Name: ix_entitlement_events_entitlement_id_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_entitlement_id_class ON public.entitlement_events USING btree (entitlement_id, class_id);


--
-- Name: ix_entitlement_events_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_event_type ON public.entitlement_events USING btree (event_type);


--
-- Name: ix_entitlement_events_one_terminal_per_lineage; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_entitlement_events_one_terminal_per_lineage ON public.entitlement_events USING btree (entitlement_id, class_id) WHERE (event_type IN ('CONSUMED', 'EXPIRED', 'REVOKED'));


--
-- Name: ix_entitlement_events_product_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_product_id ON public.entitlement_events USING btree (product_id);


--
-- Name: ix_entitlement_events_seat_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_seat_class ON public.entitlement_events USING btree (target_seat_id, class_id);


--
-- Name: ix_entitlement_events_target_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_entitlement_events_target_seat_id ON public.entitlement_events USING btree (target_seat_id);


--
-- Name: ix_feature_settings_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_feature_settings_class_id ON public.feature_settings USING btree (class_id);


--
-- Name: ix_hall_pass_logs_approved_by_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_logs_approved_by_seat_id ON public.hall_pass_logs USING btree (approved_by_seat_id);


--
-- Name: ix_hall_pass_logs_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_logs_class_id ON public.hall_pass_logs USING btree (class_id);


--
-- Name: ix_hall_pass_logs_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_logs_correlation_id ON public.hall_pass_logs USING btree (correlation_id);


--
-- Name: ix_hall_pass_logs_hall_pass_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_logs_hall_pass_id ON public.hall_pass_logs USING btree (hall_pass_id);


--
-- Name: ix_hall_pass_logs_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_logs_policy_uuid ON public.hall_pass_logs USING btree (policy_uuid);


--
-- Name: ix_hall_pass_logs_requested_by_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_logs_requested_by_seat_id ON public.hall_pass_logs USING btree (requested_by_seat_id);


--
-- Name: ix_hall_pass_settings_class_availability; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_settings_class_availability ON public.hall_pass_settings USING btree (class_id, availability_state);


--
-- Name: ix_hall_pass_settings_effective_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_hall_pass_settings_effective_date ON public.hall_pass_settings USING btree (effective_date);


--
-- Name: ix_hall_pass_settings_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_hall_pass_settings_policy_uuid ON public.hall_pass_settings USING btree (policy_uuid);


--
-- Name: ix_icpd_claim_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_icpd_claim_id ON public.insurance_claim_productivity_dates USING btree (claim_id);


--
-- Name: ix_icpd_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_icpd_class_id ON public.insurance_claim_productivity_dates USING btree (class_id);


--
-- Name: ix_icpd_entitlement_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_icpd_entitlement_id ON public.insurance_claim_productivity_dates USING btree (entitlement_id);


--
-- Name: ix_identity_profiles_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_identity_profiles_class_id ON public.identity_profiles USING btree (class_id);


--
-- Name: ix_identity_profiles_profile_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_identity_profiles_profile_type ON public.identity_profiles USING btree (profile_type);


--
-- Name: ix_identity_profiles_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_identity_profiles_seat_id ON public.identity_profiles USING btree (seat_id);


--
-- Name: ix_identity_profiles_type_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_identity_profiles_type_name ON public.identity_profiles USING btree (profile_type, last_name);


--
-- Name: ix_insurance_claims_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_class_id ON public.insurance_claims USING btree (class_id);


--
-- Name: ix_insurance_claims_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_insurance_claims_correlation_id ON public.insurance_claims USING btree (correlation_id);


--
-- Name: ix_insurance_claims_entitlement_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_entitlement_class ON public.insurance_claims USING btree (entitlement_id, class_id);


--
-- Name: ix_insurance_claims_entitlement_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_entitlement_id ON public.insurance_claims USING btree (entitlement_id);


--
-- Name: ix_insurance_claims_seat_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_seat_class ON public.insurance_claims USING btree (target_seat_id, class_id);


--
-- Name: ix_insurance_claims_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_status ON public.insurance_claims USING btree (status);


--
-- Name: ix_insurance_claims_status_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_status_class ON public.insurance_claims USING btree (status, class_id);


--
-- Name: ix_insurance_claims_target_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_claims_target_seat_id ON public.insurance_claims USING btree (target_seat_id);


--
-- Name: ix_insurance_policies_class_avail; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_policies_class_avail ON public.insurance_policies USING btree (class_id, availability_state);


--
-- Name: ix_insurance_policies_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_policies_class_id ON public.insurance_policies USING btree (class_id);


--
-- Name: ix_insurance_policies_supersedes_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_insurance_policies_supersedes_policy_uuid ON public.insurance_policies USING btree (supersedes_policy_uuid);


--
-- Name: ix_interpretation_cycle_record_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interpretation_cycle_record_class_id ON public.interpretation_cycle_record USING btree (class_id);


--
-- Name: ix_interpretation_cycle_record_payroll_cycle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_interpretation_cycle_record_payroll_cycle_id ON public.interpretation_cycle_record USING btree (payroll_cycle_id);


--
-- Name: ix_issue_resolution_actions_class_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issue_resolution_actions_class_public_id ON public.issue_resolution_actions USING btree (class_public_id);


--
-- Name: ix_issue_resolution_actions_issue_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issue_resolution_actions_issue_id ON public.issue_resolution_actions USING btree (issue_id);


--
-- Name: ix_issue_status_history_class_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issue_status_history_class_public_id ON public.issue_status_history USING btree (class_public_id);


--
-- Name: ix_issue_status_history_issue_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issue_status_history_issue_id ON public.issue_status_history USING btree (issue_id);


--
-- Name: ix_issues_actor_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_actor_public_id ON public.issues USING btree (actor_public_id);


--
-- Name: ix_issues_actor_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_actor_status ON public.issues USING btree (actor_public_id, status);


--
-- Name: ix_issues_class_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_class_public_id ON public.issues USING btree (class_public_id);


--
-- Name: ix_issues_class_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_class_status ON public.issues USING btree (class_public_id, status);


--
-- Name: ix_issues_reviewer_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_reviewer_public_id ON public.issues USING btree (reviewer_public_id);


--
-- Name: ix_issues_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_status ON public.issues USING btree (status);


--
-- Name: ix_issues_submitted_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_issues_submitted_at ON public.issues USING btree (submitted_at);


--
-- Name: ix_ledger_balance_snapshot_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_balance_snapshot_class_id ON public.ledger_balance_snapshot USING btree (class_id);


--
-- Name: ix_ledger_balance_snapshot_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_balance_snapshot_seat_id ON public.ledger_balance_snapshot USING btree (seat_id);


--
-- Name: ix_ledger_transaction_actor_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_actor_seat_id ON public.ledger_transaction USING btree (actor_seat_id);


--
-- Name: ix_ledger_transaction_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_class_id ON public.ledger_transaction USING btree (class_id);


--
-- Name: ix_ledger_transaction_command_reservation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_command_reservation_id ON public.ledger_transaction USING btree (command_reservation_id);


--
-- Name: ix_ledger_transaction_compensation_origin_locator; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_compensation_origin_locator ON public.ledger_transaction USING btree (compensation_origin_locator);


--
-- Name: ix_ledger_transaction_compensation_subtype; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_compensation_subtype ON public.ledger_transaction USING btree (compensation_subtype);


--
-- Name: ix_ledger_transaction_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_correlation_id ON public.ledger_transaction USING btree (correlation_id);


--
-- Name: ix_ledger_transaction_feat_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_feat_code ON public.ledger_transaction USING btree (feat_code);


--
-- Name: ix_ledger_transaction_idempotency_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_idempotency_key ON public.ledger_transaction USING btree (idempotency_key);


--
-- Name: ix_ledger_transaction_join_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_join_code ON public.ledger_transaction USING btree (join_code);


--
-- Name: ix_ledger_transaction_lineage_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_lineage_event_id ON public.ledger_transaction USING btree (lineage_event_id);


--
-- Name: ix_ledger_transaction_original_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_original_transaction_id ON public.ledger_transaction USING btree (original_transaction_id);


--
-- Name: ix_ledger_transaction_policy_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_policy_id ON public.ledger_transaction USING btree (policy_id);


--
-- Name: ix_ledger_transaction_posting_sequence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_posting_sequence ON public.ledger_transaction USING btree (posting_sequence);


--
-- Name: ix_ledger_transaction_reconstruction_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_reconstruction_scope ON public.ledger_transaction USING btree (class_id, seat_id, account_type, posting_sequence);


--
-- Name: ix_ledger_transaction_reversal_transaction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_reversal_transaction_id ON public.ledger_transaction USING btree (reversal_transaction_id);


--
-- Name: ix_ledger_transaction_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_seat_id ON public.ledger_transaction USING btree (seat_id);


--
-- Name: ix_ledger_transaction_target_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ledger_transaction_target_seat_id ON public.ledger_transaction USING btree (target_seat_id);


--
-- Name: ix_obligation_command_reservation_bill_cycle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_obligation_command_reservation_bill_cycle_id ON public.obligation_command_reservation USING btree (bill_cycle_id);


--
-- Name: ix_obligation_command_reservation_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_obligation_command_reservation_class_id ON public.obligation_command_reservation USING btree (class_id);


--
-- Name: ix_operational_events_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_operational_events_correlation_id ON public.operational_events USING btree (correlation_id);


--
-- Name: ix_operational_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_operational_events_created_at ON public.operational_events USING btree (created_at);


--
-- Name: ix_operational_events_domain; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_operational_events_domain ON public.operational_events USING btree (domain);


--
-- Name: ix_operational_events_level; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_operational_events_level ON public.operational_events USING btree (level);


--
-- Name: ix_passkey_credentials_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_passkey_credentials_user_id ON public.passkey_credentials USING btree (user_id);


--
-- Name: ix_payroll_cycle_completion_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_cycle_completion_class_id ON public.payroll_cycle_completion USING btree (class_id);


--
-- Name: ix_payroll_cycle_completion_payroll_cycle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_cycle_completion_payroll_cycle_id ON public.payroll_cycle_completion USING btree (payroll_cycle_id);


--
-- Name: ix_payroll_event_actor_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_actor_seat_id ON public.payroll_event USING btree (actor_seat_id);


--
-- Name: ix_payroll_event_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_class_id ON public.payroll_event USING btree (class_id);


--
-- Name: ix_payroll_event_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_correlation_id ON public.payroll_event USING btree (correlation_id);


--
-- Name: ix_payroll_event_idempotency_key; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_idempotency_key ON public.payroll_event USING btree (idempotency_key);


--
-- Name: ix_payroll_event_lineage_event_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_lineage_event_id ON public.payroll_event USING btree (lineage_event_id);


--
-- Name: ix_payroll_event_payroll_cycle_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_payroll_cycle_id ON public.payroll_event USING btree (payroll_cycle_id);


--
-- Name: ix_payroll_event_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_policy_uuid ON public.payroll_event USING btree (policy_uuid);


--
-- Name: ix_payroll_event_recorded_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_recorded_at ON public.payroll_event USING btree (recorded_at);


--
-- Name: ix_payroll_event_target_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_event_target_seat_id ON public.payroll_event USING btree (target_seat_id);


--
-- Name: ix_payroll_settings_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_payroll_settings_class_id ON public.payroll_settings USING btree (class_id);


--
-- Name: ix_pending_actions_authoritative_feat; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_actions_authoritative_feat ON public.pending_actions USING btree (authoritative_feat);


--
-- Name: ix_pending_actions_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_actions_class ON public.pending_actions USING btree (class_id);


--
-- Name: ix_pending_actions_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_actions_class_id ON public.pending_actions USING btree (class_id);


--
-- Name: ix_pending_actions_correlation_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_pending_actions_correlation_id ON public.pending_actions USING btree (correlation_id);


--
-- Name: ix_pending_actions_entitlement_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_actions_entitlement_id ON public.pending_actions USING btree (entitlement_id);


--
-- Name: ix_pending_actions_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_pending_actions_seat_id ON public.pending_actions USING btree (seat_id);


--
-- Name: ix_recovery_requests_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recovery_requests_user_id ON public.recovery_requests USING btree (user_id);


--
-- Name: ix_rent_settings_class_availability; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rent_settings_class_availability ON public.rent_settings USING btree (class_id, availability_state);


--
-- Name: ix_rent_settings_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rent_settings_class_id ON public.rent_settings USING btree (class_id);


--
-- Name: ix_rent_settings_policy_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_rent_settings_policy_uuid ON public.rent_settings USING btree (policy_uuid);


--
-- Name: ix_rent_settings_rent_configured_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rent_settings_rent_configured_at ON public.rent_settings USING btree (rent_configured_at);


--
-- Name: ix_rent_settings_rent_effective_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_rent_settings_rent_effective_at ON public.rent_settings USING btree (rent_effective_at);


--
-- Name: ix_seats_claim_first_name_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seats_claim_first_name_hash ON public.seats USING btree (claim_first_name_hash);


--
-- Name: ix_seats_claim_last_name_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seats_claim_last_name_hash ON public.seats USING btree (claim_last_name_hash);


--
-- Name: ix_seats_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seats_class_id ON public.seats USING btree (class_id);


--
-- Name: ix_seats_public_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_seats_public_id ON public.seats USING btree (public_id);


--
-- Name: ix_seats_roster_fingerprint; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seats_roster_fingerprint ON public.seats USING btree (roster_fingerprint);


--
-- Name: ix_seats_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_seats_user_id ON public.seats USING btree (user_id);


--
-- Name: ix_store_item_visibility_product_lineage_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_item_visibility_product_lineage_uuid ON public.store_item_visibility USING btree (product_lineage_uuid);


--
-- Name: ix_store_item_visibility_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_item_visibility_seat_id ON public.store_item_visibility USING btree (seat_id);


--
-- Name: ix_store_products_class_availability; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_products_class_availability ON public.store_products USING btree (class_id, availability_state);


--
-- Name: ix_store_products_class_created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_products_class_created ON public.store_products USING btree (class_id, created_at);


--
-- Name: ix_store_products_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_products_class_id ON public.store_products USING btree (class_id);


--
-- Name: ix_store_products_collective_goal_instance_code; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_products_collective_goal_instance_code ON public.store_products USING btree (collective_goal_instance_code);


--
-- Name: ix_store_products_product_lineage_uuid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_store_products_product_lineage_uuid ON public.store_products USING btree (product_lineage_uuid);


--
-- Name: ix_student_recovery_codes_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_student_recovery_codes_class_id ON public.student_recovery_codes USING btree (class_id);


--
-- Name: ix_student_recovery_codes_recovery_request_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_student_recovery_codes_recovery_request_id ON public.student_recovery_codes USING btree (recovery_request_id);


--
-- Name: ix_student_recovery_codes_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_student_recovery_codes_seat_id ON public.student_recovery_codes USING btree (seat_id);


--
-- Name: ix_teacher_signup_attempts_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_teacher_signup_attempts_expires_at ON public.teacher_signup_attempts USING btree (expires_at);


--
-- Name: ix_ticket_correlation_actor_public; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ticket_correlation_actor_public ON public.ticket_correlation_pack USING btree (actor_type, actor_public_id);


--
-- Name: ix_transaction_class_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaction_class_scope ON public.ledger_transaction USING btree (class_id, target_seat_id, actor_seat_id, account_type);


--
-- Name: ix_transaction_seat_ledger; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_transaction_seat_ledger ON public.ledger_transaction USING btree (join_code, seat_id, account_type);


--
-- Name: ix_users_current_session_nonce; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_current_session_nonce ON public.users USING btree (current_session_nonce);


--
-- Name: ix_users_hall_pass_verify_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_hall_pass_verify_token ON public.users USING btree (hall_pass_verify_token);


--
-- Name: ix_users_last_active_class_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_last_active_class_id ON public.users USING btree (last_active_class_id);


--
-- Name: ix_users_last_active_seat_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_last_active_seat_id ON public.users USING btree (last_active_seat_id);


--
-- Name: ix_users_last_signed_in_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_last_signed_in_at ON public.users USING btree (last_signed_in_at);


--
-- Name: ix_users_provisioning_expires_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_provisioning_expires_at ON public.users USING btree (provisioning_expires_at);


--
-- Name: ix_users_user_role; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_user_role ON public.users USING btree (user_role);


--
-- Name: ix_users_username_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_username_hash ON public.users USING btree (username_hash);


--
-- Name: ix_users_username_lookup_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_username_lookup_hash ON public.users USING btree (username_lookup_hash);


--
-- Name: uq_assessment_events_assessment_internal_ref_correlation; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_assessment_events_assessment_internal_ref_correlation ON public.assessment_events USING btree (internal_ref, correlation_id) WHERE ((event_type)::text = 'ASSESSMENT'::text);


--
-- Name: uq_credential_operations_one_open_per_user; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_credential_operations_one_open_per_user ON public.credential_operations USING btree (user_id) WHERE (stage <> ALL (ARRAY['completed'::public.credential_operation_stage_enum, 'cancelled'::public.credential_operation_stage_enum]));


--
-- Name: uq_credential_operations_step_up_token_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_credential_operations_step_up_token_id ON public.credential_operations USING btree (step_up_token_id);


--
-- Name: uq_hall_pass_logs_hall_pass_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_hall_pass_logs_hall_pass_id ON public.hall_pass_logs USING btree (hall_pass_id) WHERE (hall_pass_id IS NOT NULL);


--
-- Name: uq_hall_pass_settings_active_scope; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_hall_pass_settings_active_scope ON public.hall_pass_settings USING btree (class_id) WHERE ((availability_state)::text = 'IN_USE'::text);


--
-- Name: uq_insurance_policies_group_rank_in_use; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_insurance_policies_group_rank_in_use ON public.insurance_policies USING btree (class_id, tier_group_id, tier_level) WHERE (((availability_state)::text = 'IN_USE'::text) AND (tier_group_id IS NOT NULL));


--
-- Name: uq_ledger_exact_reversal_origin; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ledger_exact_reversal_origin ON public.ledger_transaction USING btree (original_transaction_id) WHERE ((type)::text = 'REVERSAL'::text);


--
-- Name: uq_ledger_recovery_intent; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_ledger_recovery_intent ON public.ledger_transaction USING btree (class_id, target_seat_id, compensation_origin_locator, correction_intent_locator) WHERE (compensation_amount_cents > 0);


--
-- Name: uq_store_products_one_live_per_lineage; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_store_products_one_live_per_lineage ON public.store_products USING btree (product_lineage_uuid) WHERE ((availability_state)::text = 'IN_USE'::text);


--
-- Name: attendance_interval_invalidation attendance_invalidation_delete_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER attendance_invalidation_delete_guard BEFORE DELETE ON public.attendance_interval_invalidation FOR EACH ROW EXECUTE FUNCTION public.guard_attendance_invalidation_delete();


--
-- Name: attendance_interval_invalidation attendance_invalidation_insert_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER attendance_invalidation_insert_guard BEFORE INSERT ON public.attendance_interval_invalidation FOR EACH ROW EXECUTE FUNCTION public.guard_attendance_invalidation_insert();


--
-- Name: attendance_interval_invalidation attendance_invalidation_lineage_required; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER attendance_invalidation_lineage_required AFTER INSERT ON public.attendance_interval_invalidation DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.require_attendance_invalidation_lineage();


--
-- Name: attendance_interval_invalidation attendance_invalidation_update_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER attendance_invalidation_update_guard BEFORE UPDATE ON public.attendance_interval_invalidation FOR EACH ROW EXECUTE FUNCTION public.guard_attendance_invalidation_update();


--
-- Name: attendance_sessions attendance_sessions_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER attendance_sessions_no_delete BEFORE DELETE ON public.attendance_sessions FOR EACH ROW EXECUTE FUNCTION public.prevent_attendance_session_delete();


--
-- Name: attendance_sessions attendance_sessions_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER attendance_sessions_no_update BEFORE UPDATE ON public.attendance_sessions FOR EACH ROW EXECUTE FUNCTION public.prevent_attendance_session_update();


--
-- Name: audit_events audit_events_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON public.audit_events FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_event_delete();


--
-- Name: audit_events audit_events_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER audit_events_no_update BEFORE UPDATE ON public.audit_events FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_event_update();


--
-- Name: class_features class_features_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER class_features_no_delete BEFORE DELETE ON public.class_features FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_delete();


--
-- Name: class_features class_features_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER class_features_no_update BEFORE UPDATE ON public.class_features FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_update();


--
-- Name: economic_engine economic_engine_default_effective_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER economic_engine_default_effective_at BEFORE INSERT ON public.economic_engine FOR EACH ROW EXECUTE FUNCTION public.economic_engine_default_effective_at();


--
-- Name: economic_engine economic_engine_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER economic_engine_no_delete BEFORE DELETE ON public.economic_engine FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_delete();


--
-- Name: economic_engine economic_engine_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER economic_engine_no_update BEFORE UPDATE ON public.economic_engine FOR EACH ROW EXECUTE FUNCTION public.prevent_immutable_update();


--
-- Name: ledger_transaction ledger_creation_sequence_required; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ledger_creation_sequence_required BEFORE INSERT ON public.ledger_transaction FOR EACH ROW EXECUTE FUNCTION public.require_ledger_creation_sequence();


--
-- Name: ledger_transaction ledger_recovery_cap; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ledger_recovery_cap BEFORE INSERT ON public.ledger_transaction FOR EACH ROW EXECUTE FUNCTION public.enforce_ledger_recovery_cap();


--
-- Name: ledger_transaction ledger_transaction_no_rewrite; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ledger_transaction_no_rewrite BEFORE UPDATE ON public.ledger_transaction FOR EACH ROW EXECUTE FUNCTION public.prevent_ledger_transaction_rewrite();


--
-- Name: ledger_transaction ledger_v3_creation_lineage_required; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER ledger_v3_creation_lineage_required AFTER INSERT ON public.ledger_transaction DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.require_ledger_v3_creation_lineage();


--
-- Name: payroll_event payroll_event_creation_lineage_required; Type: TRIGGER; Schema: public; Owner: -
--

CREATE CONSTRAINT TRIGGER payroll_event_creation_lineage_required AFTER INSERT ON public.payroll_event DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.require_payroll_lineage_at_commit();


--
-- Name: payroll_event payroll_event_lineage_initially_empty; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payroll_event_lineage_initially_empty BEFORE INSERT ON public.payroll_event FOR EACH ROW EXECUTE FUNCTION public.require_payroll_lineage_at_insert();


--
-- Name: payroll_event payroll_event_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payroll_event_no_delete BEFORE DELETE ON public.payroll_event FOR EACH ROW EXECUTE FUNCTION public.prevent_payroll_event_delete();


--
-- Name: payroll_event payroll_event_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payroll_event_no_update BEFORE UPDATE ON public.payroll_event FOR EACH ROW EXECUTE FUNCTION public.prevent_payroll_event_update();


--
-- Name: payroll_settings payroll_settings_no_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payroll_settings_no_delete BEFORE DELETE ON public.payroll_settings FOR EACH ROW EXECUTE FUNCTION public.prevent_payroll_settings_delete();


--
-- Name: payroll_settings payroll_settings_no_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER payroll_settings_no_update BEFORE UPDATE ON public.payroll_settings FOR EACH ROW EXECUTE FUNCTION public.prevent_payroll_settings_update();


--
-- Name: actor_request_trace actor_request_trace_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.actor_request_trace
    ADD CONSTRAINT actor_request_trace_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: announcements announcements_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: announcements announcements_created_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.announcements
    ADD CONSTRAINT announcements_created_by_seat_id_fkey FOREIGN KEY (created_by_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: assessment_events assessment_events_bill_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_bill_cycle_id_fkey FOREIGN KEY (bill_cycle_id) REFERENCES public.bill_cycles(id) ON DELETE SET NULL;


--
-- Name: assessment_events assessment_events_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: assessment_events assessment_events_ledger_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_ledger_transaction_id_fkey FOREIGN KEY (ledger_transaction_id) REFERENCES public.ledger_transaction(id) ON DELETE SET NULL;


--
-- Name: assessment_events assessment_events_reversed_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_reversed_by_seat_id_fkey FOREIGN KEY (reversed_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: assessment_events assessment_events_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.assessment_events
    ADD CONSTRAINT assessment_events_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: attendance_interval_invalidation attendance_interval_invalidation_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT attendance_interval_invalidation_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: attendance_interval_invalidation attendance_interval_invalidation_closing_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT attendance_interval_invalidation_closing_event_id_fkey FOREIGN KEY (closing_event_id) REFERENCES public.attendance_sessions(id) ON DELETE CASCADE;


--
-- Name: attendance_interval_invalidation attendance_interval_invalidation_opening_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT attendance_interval_invalidation_opening_event_id_fkey FOREIGN KEY (opening_event_id) REFERENCES public.attendance_sessions(id) ON DELETE CASCADE;


--
-- Name: attendance_interval_invalidation attendance_interval_invalidation_target_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_interval_invalidation
    ADD CONSTRAINT attendance_interval_invalidation_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: attendance_sessions attendance_sessions_actor_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: attendance_sessions attendance_sessions_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: attendance_sessions attendance_sessions_target_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.attendance_sessions
    ADD CONSTRAINT attendance_sessions_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: bill_cycles bill_cycles_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT bill_cycles_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: class_features class_features_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT class_features_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: classes classes_teacher_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.classes
    ADD CONSTRAINT classes_teacher_user_id_fkey FOREIGN KEY (teacher_user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: configuration_import_receipts configuration_import_receipts_actor_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuration_import_receipts
    ADD CONSTRAINT configuration_import_receipts_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: configuration_import_receipts configuration_import_receipts_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.configuration_import_receipts
    ADD CONSTRAINT configuration_import_receipts_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: credential_operations credential_operations_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credential_operations
    ADD CONSTRAINT credential_operations_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: economic_engine economic_engine_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT economic_engine_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: feature_settings feature_settings_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.feature_settings
    ADD CONSTRAINT feature_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: bill_cycles fk_bill_cycles_class_id_classes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_cycles
    ADD CONSTRAINT fk_bill_cycles_class_id_classes FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: class_features fk_class_features_economic_version; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT fk_class_features_economic_version FOREIGN KEY (class_id, economic_version_id) REFERENCES public.economic_engine(class_id, economic_version_id) ON DELETE RESTRICT;


--
-- Name: class_features fk_class_features_economic_version_composite; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.class_features
    ADD CONSTRAINT fk_class_features_economic_version_composite FOREIGN KEY (class_id, economic_version_id) REFERENCES public.economic_engine(class_id, economic_version_id) ON DELETE RESTRICT;


--
-- Name: economic_engine fk_economic_engine_previous_version; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT fk_economic_engine_previous_version FOREIGN KEY (class_id, previous_version_id) REFERENCES public.economic_engine(class_id, economic_version_id) ON DELETE RESTRICT;


--
-- Name: economic_engine fk_economic_engine_previous_version_composite; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.economic_engine
    ADD CONSTRAINT fk_economic_engine_previous_version_composite FOREIGN KEY (class_id, previous_version_id) REFERENCES public.economic_engine(class_id, economic_version_id) ON DELETE RESTRICT;


--
-- Name: entitlement_events fk_entitlement_events_actor_seat_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT fk_entitlement_events_actor_seat_id FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: entitlement_events fk_entitlement_events_class_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT fk_entitlement_events_class_id FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: entitlement_events fk_entitlement_events_target_seat_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entitlement_events
    ADD CONSTRAINT fk_entitlement_events_target_seat_id FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: identity_profiles fk_identity_profiles_class_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT fk_identity_profiles_class_id FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: identity_profiles fk_identity_profiles_seat_id_seats; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT fk_identity_profiles_seat_id_seats FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: insurance_policies fk_insurance_policy_group; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT fk_insurance_policy_group FOREIGN KEY (class_id, tier_group_id) REFERENCES public.insurance_tier_groups(class_id, group_id);


--
-- Name: ledger_balance_snapshot fk_ledger_balance_snapshot_reconciled_through_transaction_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT fk_ledger_balance_snapshot_reconciled_through_transaction_id FOREIGN KEY (reconciled_through_transaction_id) REFERENCES public.ledger_transaction(id);


--
-- Name: ledger_transaction fk_ledger_transaction_command_reservation; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT fk_ledger_transaction_command_reservation FOREIGN KEY (command_reservation_id) REFERENCES public.ledger_command_reservation(id) ON DELETE RESTRICT;


--
-- Name: seats fk_seats_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT fk_seats_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: student_recovery_codes fk_student_recovery_codes_class_id_classes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT fk_student_recovery_codes_class_id_classes FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: student_recovery_codes fk_student_recovery_codes_seat_id_seats; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT fk_student_recovery_codes_seat_id_seats FOREIGN KEY (seat_id) REFERENCES public.seats(id);


--
-- Name: users fk_users_last_active_class_id_classes; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_last_active_class_id_classes FOREIGN KEY (last_active_class_id) REFERENCES public.classes(class_id) ON DELETE SET NULL;


--
-- Name: users fk_users_last_active_seat_id_seats; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_last_active_seat_id_seats FOREIGN KEY (last_active_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: hall_pass_logs hall_pass_logs_approved_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_approved_by_seat_id_fkey FOREIGN KEY (approved_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: hall_pass_logs hall_pass_logs_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: hall_pass_logs hall_pass_logs_requested_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_logs
    ADD CONSTRAINT hall_pass_logs_requested_by_seat_id_fkey FOREIGN KEY (requested_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: hall_pass_settings hall_pass_settings_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hall_pass_settings
    ADD CONSTRAINT hall_pass_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: identity_profiles identity_profiles_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT identity_profiles_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: identity_profiles identity_profiles_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.identity_profiles
    ADD CONSTRAINT identity_profiles_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: insurance_claim_productivity_dates insurance_claim_productivity_dates_claim_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT insurance_claim_productivity_dates_claim_id_fkey FOREIGN KEY (claim_id) REFERENCES public.insurance_claims(claim_id) ON DELETE CASCADE;


--
-- Name: insurance_claim_productivity_dates insurance_claim_productivity_dates_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claim_productivity_dates
    ADD CONSTRAINT insurance_claim_productivity_dates_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: insurance_claims insurance_claims_actor_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: insurance_claims insurance_claims_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: insurance_claims insurance_claims_decided_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_decided_by_seat_id_fkey FOREIGN KEY (decided_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: insurance_claims insurance_claims_target_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_claims
    ADD CONSTRAINT insurance_claims_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: insurance_policies insurance_policies_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT insurance_policies_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: insurance_policies insurance_policies_created_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_policies
    ADD CONSTRAINT insurance_policies_created_by_seat_id_fkey FOREIGN KEY (created_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: insurance_tier_groups insurance_tier_groups_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.insurance_tier_groups
    ADD CONSTRAINT insurance_tier_groups_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: interpretation_cycle_record interpretation_cycle_record_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.interpretation_cycle_record
    ADD CONSTRAINT interpretation_cycle_record_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: issue_resolution_actions issue_resolution_actions_issue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_resolution_actions
    ADD CONSTRAINT issue_resolution_actions_issue_id_fkey FOREIGN KEY (issue_id) REFERENCES public.issues(id) ON DELETE CASCADE;


--
-- Name: issue_resolution_actions issue_resolution_actions_related_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_resolution_actions
    ADD CONSTRAINT issue_resolution_actions_related_transaction_id_fkey FOREIGN KEY (related_transaction_id) REFERENCES public.ledger_transaction(id);


--
-- Name: issue_status_history issue_status_history_issue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issue_status_history
    ADD CONSTRAINT issue_status_history_issue_id_fkey FOREIGN KEY (issue_id) REFERENCES public.issues(id) ON DELETE CASCADE;


--
-- Name: issues issues_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issues
    ADD CONSTRAINT issues_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.issue_categories(id);


--
-- Name: issues issues_related_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.issues
    ADD CONSTRAINT issues_related_transaction_id_fkey FOREIGN KEY (related_transaction_id) REFERENCES public.ledger_transaction(id);


--
-- Name: ledger_balance_snapshot ledger_balance_snapshot_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: ledger_balance_snapshot ledger_balance_snapshot_reconciled_through_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_reconciled_through_transaction_id_fkey FOREIGN KEY (reconciled_through_transaction_id) REFERENCES public.ledger_transaction(id);


--
-- Name: ledger_balance_snapshot ledger_balance_snapshot_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_balance_snapshot
    ADD CONSTRAINT ledger_balance_snapshot_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: ledger_command_reservation ledger_command_reservation_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_command_reservation
    ADD CONSTRAINT ledger_command_reservation_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: ledger_transaction ledger_transaction_actor_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: ledger_transaction ledger_transaction_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: ledger_transaction ledger_transaction_command_reservation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_command_reservation_id_fkey FOREIGN KEY (command_reservation_id) REFERENCES public.ledger_command_reservation(id) ON DELETE RESTRICT;


--
-- Name: ledger_transaction ledger_transaction_lineage_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_lineage_event_id_fkey FOREIGN KEY (lineage_event_id) REFERENCES public.audit_events(id);


--
-- Name: ledger_transaction ledger_transaction_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: ledger_transaction ledger_transaction_target_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ledger_transaction
    ADD CONSTRAINT ledger_transaction_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: obligation_command_reservation obligation_command_reservation_bill_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT obligation_command_reservation_bill_cycle_id_fkey FOREIGN KEY (bill_cycle_id) REFERENCES public.bill_cycles(id) ON DELETE CASCADE;


--
-- Name: obligation_command_reservation obligation_command_reservation_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.obligation_command_reservation
    ADD CONSTRAINT obligation_command_reservation_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: passkey_credentials passkey_credentials_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.passkey_credentials
    ADD CONSTRAINT passkey_credentials_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: payroll_cycle_completion payroll_cycle_completion_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_cycle_completion
    ADD CONSTRAINT payroll_cycle_completion_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: payroll_event payroll_event_actor_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_actor_seat_id_fkey FOREIGN KEY (actor_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: payroll_event payroll_event_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: payroll_event payroll_event_target_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_event
    ADD CONSTRAINT payroll_event_target_seat_id_fkey FOREIGN KEY (target_seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: payroll_settings payroll_settings_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payroll_settings
    ADD CONSTRAINT payroll_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: pending_actions pending_actions_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: pending_actions pending_actions_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pending_actions
    ADD CONSTRAINT pending_actions_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: recovery_class_challenges recovery_class_challenges_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_class_challenges
    ADD CONSTRAINT recovery_class_challenges_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: recovery_class_challenges recovery_class_challenges_recovery_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_class_challenges
    ADD CONSTRAINT recovery_class_challenges_recovery_request_id_fkey FOREIGN KEY (recovery_request_id) REFERENCES public.recovery_requests(id) ON DELETE CASCADE;


--
-- Name: recovery_requests recovery_requests_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recovery_requests
    ADD CONSTRAINT recovery_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: rent_settings rent_settings_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rent_settings
    ADD CONSTRAINT rent_settings_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: seats seats_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.seats
    ADD CONSTRAINT seats_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: store_item_visibility store_item_visibility_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_item_visibility
    ADD CONSTRAINT store_item_visibility_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id) ON DELETE CASCADE;


--
-- Name: store_products store_products_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_products
    ADD CONSTRAINT store_products_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: store_products store_products_created_by_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.store_products
    ADD CONSTRAINT store_products_created_by_seat_id_fkey FOREIGN KEY (created_by_seat_id) REFERENCES public.seats(id) ON DELETE SET NULL;


--
-- Name: student_recovery_codes student_recovery_codes_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_class_id_fkey FOREIGN KEY (class_id) REFERENCES public.classes(class_id) ON DELETE CASCADE;


--
-- Name: student_recovery_codes student_recovery_codes_recovery_request_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_recovery_request_id_fkey FOREIGN KEY (recovery_request_id) REFERENCES public.recovery_requests(id);


--
-- Name: student_recovery_codes student_recovery_codes_seat_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.student_recovery_codes
    ADD CONSTRAINT student_recovery_codes_seat_id_fkey FOREIGN KEY (seat_id) REFERENCES public.seats(id);


--
-- Name: ticket_correlation_pack ticket_correlation_pack_issue_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ticket_correlation_pack
    ADD CONSTRAINT ticket_correlation_pack_issue_id_fkey FOREIGN KEY (issue_id) REFERENCES public.issues(id) ON DELETE CASCADE;


--
-- Name: users users_last_active_class_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_last_active_class_id_fkey FOREIGN KEY (last_active_class_id) REFERENCES public.classes(class_id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--


