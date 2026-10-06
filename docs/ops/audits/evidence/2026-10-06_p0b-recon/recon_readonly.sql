-- P0B production-state reconnaissance: read-only, aggregate-only queries.
--
-- Record: docs/ops/audits/RECON_2026-10-06_P0B_PRODUCTION_STATE.md
-- Q0-Q12 ran 2026-10-06 06:08:34Z to 06:11:30Z UTC; Q13 ran after Q12 in the same session
-- (it selects no timestamp). All ran against the production database
-- (`classroom_economy`, revision f9a3c7d1e620), through the TablePlus read-only query
-- surface, which rejects any statement that is not a read.
--
-- Rules for reruns (SOP-DB-004 §IX.1.7 and §IX.5.2):
--   * SELECT only. Run inside `BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;` ... `ROLLBACK;`
--     when using psql directly.
--   * No PII. No query selects a name, free-text column (descriptions, notes,
--     explanations, titles, messages, destinations), credential, hash, token, or join code.
--     Classes are identified only by the first eight characters of `class_id`.
--   * Compare a rerun with the recorded results by query id (Q0-Q14). Q14 ran after the owner ruling of 2026-10-06.

-- Q0 revision, server, table set
SELECT now() AT TIME ZONE 'UTC' AS observed_at_utc,
       (SELECT string_agg(version_num, ',') FROM alembic_version) AS alembic_rev,
       current_setting('server_version') AS pg,
       (SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE') AS n_tables,
       (SELECT string_agg(table_name, ',' ORDER BY table_name) FROM information_schema.tables
         WHERE table_schema='public' AND table_type='BASE TABLE') AS tables;

-- Q1 exact row count per table (44 domain tables plus alembic_version from Q0)
SELECT now() AT TIME ZONE 'UTC' observed_at_utc, t, n FROM (
SELECT 'actor_request_trace' t, count(*) n FROM actor_request_trace UNION ALL
SELECT 'announcements', count(*) FROM announcements UNION ALL
SELECT 'assessment_events', count(*) FROM assessment_events UNION ALL
SELECT 'attendance_interval_invalidation', count(*) FROM attendance_interval_invalidation UNION ALL
SELECT 'attendance_sessions', count(*) FROM attendance_sessions UNION ALL
SELECT 'audit_events', count(*) FROM audit_events UNION ALL
SELECT 'bill_cycles', count(*) FROM bill_cycles UNION ALL
SELECT 'chain_heads', count(*) FROM chain_heads UNION ALL
SELECT 'class_features', count(*) FROM class_features UNION ALL
SELECT 'classes', count(*) FROM classes UNION ALL
SELECT 'economic_engine', count(*) FROM economic_engine UNION ALL
SELECT 'entitlement_events', count(*) FROM entitlement_events UNION ALL
SELECT 'feature_settings', count(*) FROM feature_settings UNION ALL
SELECT 'hall_pass_logs', count(*) FROM hall_pass_logs UNION ALL
SELECT 'hall_pass_settings', count(*) FROM hall_pass_settings UNION ALL
SELECT 'identity_profiles', count(*) FROM identity_profiles UNION ALL
SELECT 'insurance_claim_productivity_dates', count(*) FROM insurance_claim_productivity_dates UNION ALL
SELECT 'insurance_claims', count(*) FROM insurance_claims UNION ALL
SELECT 'insurance_policies', count(*) FROM insurance_policies UNION ALL
SELECT 'interpretation_cycle_record', count(*) FROM interpretation_cycle_record UNION ALL
SELECT 'issue_categories', count(*) FROM issue_categories UNION ALL
SELECT 'issue_resolution_actions', count(*) FROM issue_resolution_actions UNION ALL
SELECT 'issue_status_history', count(*) FROM issue_status_history UNION ALL
SELECT 'issues', count(*) FROM issues UNION ALL
SELECT 'ledger_balance_snapshot', count(*) FROM ledger_balance_snapshot UNION ALL
SELECT 'ledger_command_reservation', count(*) FROM ledger_command_reservation UNION ALL
SELECT 'ledger_transaction', count(*) FROM ledger_transaction UNION ALL
SELECT 'obligation_command_reservation', count(*) FROM obligation_command_reservation UNION ALL
SELECT 'operational_events', count(*) FROM operational_events UNION ALL
SELECT 'passkey_credentials', count(*) FROM passkey_credentials UNION ALL
SELECT 'payroll_cycle_completion', count(*) FROM payroll_cycle_completion UNION ALL
SELECT 'payroll_event', count(*) FROM payroll_event UNION ALL
SELECT 'payroll_settings', count(*) FROM payroll_settings UNION ALL
SELECT 'pending_actions', count(*) FROM pending_actions UNION ALL
SELECT 'recovery_class_challenges', count(*) FROM recovery_class_challenges UNION ALL
SELECT 'recovery_requests', count(*) FROM recovery_requests UNION ALL
SELECT 'rent_settings', count(*) FROM rent_settings UNION ALL
SELECT 'seats', count(*) FROM seats UNION ALL
SELECT 'store_item_visibility', count(*) FROM store_item_visibility UNION ALL
SELECT 'store_products', count(*) FROM store_products UNION ALL
SELECT 'student_recovery_codes', count(*) FROM student_recovery_codes UNION ALL
SELECT 'teacher_signup_attempts', count(*) FROM teacher_signup_attempts UNION ALL
SELECT 'ticket_correlation_pack', count(*) FROM ticket_correlation_pack UNION ALL
SELECT 'users', count(*) FROM users) x ORDER BY t;

-- Q2 money baseline: ledger sum vs posted snapshot sum, per class and account
WITH l AS (SELECT class_id, account_type, count(*) n, sum(amount_cents) cents, max(posting_sequence) max_seq,
                  count(*) FILTER (WHERE amount_cents IS NULL) null_cents
           FROM ledger_transaction GROUP BY 1,2),
     s AS (SELECT class_id, account_type, count(*) n_snap, sum(posted_balance_cents) snap_cents
           FROM ledger_balance_snapshot GROUP BY 1,2)
SELECT now() AT TIME ZONE 'UTC' observed_at_utc, left(coalesce(l.class_id,s.class_id),8) class8,
       coalesce(l.account_type,s.account_type) acct, l.n ledger_rows, l.cents ledger_cents, s.n_snap, s.snap_cents,
       (coalesce(l.cents,0)=coalesce(s.snap_cents,0)) agree, l.max_seq, l.null_cents
FROM l FULL JOIN s ON l.class_id=s.class_id AND l.account_type=s.account_type ORDER BY 2,3;

-- Q3 ledger semantics: type x feat_code x mechanism x signature version x account
SELECT type, feat_code, mechanism::text mech, lineage_version, account_type, count(*) n, sum(amount_cents) cents,
       count(*) FILTER (WHERE amount_cents=0) zero_amt,
       count(*) FILTER (WHERE original_transaction_id IS NOT NULL) has_orig,
       count(*) FILTER (WHERE reversal_transaction_id IS NOT NULL) has_rev,
       count(*) FILTER (WHERE command_reservation_id IS NULL) no_resv,
       count(*) FILTER (WHERE lineage_event_id IS NULL) no_lineage,
       count(*) FILTER (WHERE compensation_amount_cents IS NULL) null_comp,
       count(*) FILTER (WHERE join_code IS NOT NULL) has_join,
       count(*) FILTER (WHERE policy_id IS NOT NULL) has_policy,
       count(*) FILTER (WHERE compensation_subtype IS NOT NULL) has_subtype,
       min(timestamp) first_ts, max(timestamp) last_ts
FROM ledger_transaction GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5;

-- Q4 audit chain composition
SELECT table_name, operation, feat_id, signature_version, actor_type, count(*) n, count(DISTINCT row_pk) rows,
       count(*) FILTER (WHERE class_id IS NULL) no_class,
       count(*) FILTER (WHERE hmac_signature IS DISTINCT FROM event_hash) hmac_ne_hash,
       min(created_at_utc) first, max(created_at_utc) last
FROM audit_events GROUP BY 1,2,3,4,5 ORDER BY 1,2,3,4,5;

-- Q5 stored ledger feat_code vs the FEAT recorded by the row's creation audit event
SELECT t.lineage_version, t.feat_code ledger_feat, a.feat_id audit_feat, a.signature_version sigv, t.type,
       (t.lineage_event_id = a.id) ptr_ok, count(*) n
FROM ledger_transaction t
LEFT JOIN audit_events a ON a.table_name='ledger_transaction' AND a.row_pk = t.id::text AND a.operation='INSERT'
GROUP BY 1,2,3,4,5,6 ORDER BY 1,2,3,5;

-- Q6 other protected / PROD records
SELECT 'payroll_event' t, payroll_event_type k, mechanism m, lineage_version v, count(*) n,
       count(*) FILTER (WHERE lineage_event_id IS NULL) no_lineage, min(recorded_at) first, max(recorded_at) last
FROM payroll_event GROUP BY 1,2,3,4
UNION ALL SELECT 'attendance_interval_invalidation', reason_code, NULL, lineage_version, count(*),
       count(*) FILTER (WHERE lineage_event_id IS NULL), min(recorded_at), max(recorded_at)
FROM attendance_interval_invalidation GROUP BY 1,2,3,4
UNION ALL SELECT 'payroll_cycle_completion', NULL, NULL, NULL, count(*), NULL, min(completed_at), max(completed_at) FROM payroll_cycle_completion
UNION ALL SELECT 'interpretation_cycle_record', NULL, NULL, NULL, count(*), NULL, min(computed_at), max(computed_at) FROM interpretation_cycle_record
ORDER BY 1,2,3;

-- Q7 entitlement event mix
SELECT event_type, entitlement_type, acquisition_type, payload->>'source' src, payload->>'reason' rsn,
       payload->>'outcome' outc, (entitlement_id LIKE 'hpent\_%') hpent, (payload->>'policy_uuid') IS NOT NULL has_pol,
       count(*) n, count(DISTINCT class_id) classes, min(timestamp) first, max(timestamp) last
FROM entitlement_events GROUP BY 1,2,3,4,5,6,7,8 ORDER BY 2,1,9 DESC;

-- Q8 hall-pass double record, hall-pass policy references, attendance shape, REVOKED actors, pending queue
WITH c AS (SELECT class_id, entitlement_id FROM entitlement_events WHERE entitlement_type='HALL_PASS' AND event_type='CONSUMED'),
     l AS (SELECT class_id, hall_pass_id, count(*) n FROM hall_pass_logs WHERE hall_pass_id IS NOT NULL GROUP BY 1,2)
SELECT 'consumed_vs_log' q, (c.entitlement_id IS NOT NULL)::text a, (l.hall_pass_id IS NOT NULL)::text b,
       (COALESCE(l.n,0)>1)::text c, count(*) n
FROM c FULL JOIN l ON l.class_id=c.class_id AND l.hall_pass_id=c.entitlement_id GROUP BY 1,2,3,4
UNION ALL SELECT 'log_policy_shape', (policy_uuid='default')::text, (hall_pass_id IS NULL)::text,
       (EXISTS (SELECT 1 FROM hall_pass_settings s WHERE s.policy_uuid=h.policy_uuid))::text, count(*)
FROM hall_pass_logs h GROUP BY 1,2,3,4
UNION ALL SELECT 'attendance', status, reason_code, mechanism || '/' || (hall_pass_id IS NULL)::text, count(*)
FROM attendance_sessions GROUP BY 1,2,3,4
UNION ALL SELECT 'revoked_actor', e.entitlement_type, coalesce(e.payload->>'source',''),
       s.role || '/self=' || (e.actor_seat_id=e.target_seat_id)::text, count(*)
FROM entitlement_events e LEFT JOIN seats s ON s.id=e.actor_seat_id WHERE e.event_type='REVOKED' GROUP BY 1,2,3,4
UNION ALL SELECT 'pending', authoritative_feat, coalesce(payload->>'kind','<null>'),
       ((payload->>'outcome') IS NOT NULL)::text || '/age_d=' || floor(extract(epoch FROM now()-submitted_at)/86400)::text
       || '/terminal=' || (EXISTS (SELECT 1 FROM entitlement_events t WHERE t.class_id=p.class_id
          AND t.entitlement_id=p.entitlement_id AND t.event_type IN ('CONSUMED','EXPIRED','REVOKED')))::text, count(*)
FROM pending_actions p GROUP BY 1,2,3,4
ORDER BY 1,2,3,4;

-- Q9 idempotency-key shape classes (shape only; no key is printed)
SELECT 'ledger' t, type || '/' || feat_code k,
       CASE WHEN idempotency_key IS NULL THEN 'null' WHEN idempotency_key ~ '[0-9a-f]{32}' THEN 'uuid4hex'
            WHEN idempotency_key ~ '[0-9a-f]{8}-[0-9a-f]{4}-' THEN 'uuid4' WHEN idempotency_key ~ '[0-9a-f]{24}$' THEN 'token_hex12'
            ELSE 'det:' || split_part(idempotency_key,':',1) END cls, count(*) n
FROM ledger_transaction GROUP BY 1,2,3
UNION ALL SELECT 'reservation', feat_code || '/fpv' || fingerprint_version,
       CASE WHEN idempotency_key ~ '[0-9a-f]{32}' THEN 'uuid4hex' WHEN idempotency_key ~ '[0-9a-f]{8}-[0-9a-f]{4}-' THEN 'uuid4'
            WHEN idempotency_key ~ '[0-9a-f]{24}$' THEN 'token_hex12' ELSE 'det:' || split_part(idempotency_key,':',1) END, count(*)
FROM ledger_command_reservation GROUP BY 1,2,3
UNION ALL SELECT 'reservation_unused', feat_code, '', count(*) FROM ledger_command_reservation r
WHERE NOT EXISTS (SELECT 1 FROM ledger_transaction x WHERE x.command_reservation_id=r.id) GROUP BY 1,2,3
UNION ALL SELECT 'payroll_event', payroll_event_type,
       CASE WHEN idempotency_key IS NULL THEN 'null' WHEN idempotency_key ~ '[0-9a-f]{32}' THEN 'uuid4hex'
            WHEN idempotency_key ~ '[0-9a-f]{24}$' THEN 'token_hex12' ELSE 'det:' || split_part(idempotency_key,':',1) END, count(*)
FROM payroll_event GROUP BY 1,2,3
UNION ALL SELECT 'cycle_completion', '', split_part(idempotency_key,':',1), count(*) FROM payroll_cycle_completion GROUP BY 1,2,3
UNION ALL SELECT 'interest_key', '', CASE WHEN idempotency_key ~ ':weekly:\d{4}-\d{2}-\d{2}$' THEN 'weekly'
       WHEN idempotency_key ~ ':monthly:\d{4}-\d{2}$' THEN 'monthly' ELSE 'legacy/other' END, count(*)
FROM ledger_transaction WHERE type='Interest' GROUP BY 1,2,3
UNION ALL SELECT 'snapshot', account_type, 'jc=' || count(*) FILTER (WHERE join_code IS NOT NULL)
       || ' rtt=' || count(*) FILTER (WHERE reconciled_through_transaction_id IS NOT NULL)
       || ' nocursor=' || count(*) FILTER (WHERE reconciled_through_posting_sequence IS NULL), count(*)
FROM ledger_balance_snapshot GROUP BY 1,2
ORDER BY 1,2,3;

-- Q10 policy families and class configuration, per class
SELECT 'rent' fam, left(class_id,8) c, availability_state st, count(*) n, count(*) FILTER (WHERE rent_effective_at > now()) future,
       min(rent_effective_at)::text first, max(rent_effective_at)::text last FROM rent_settings GROUP BY 1,2,3
UNION ALL SELECT 'hall', left(class_id,8), availability_state, count(*), count(*) FILTER (WHERE effective_date>now()),
       min(effective_date)::text, max(effective_date)::text FROM hall_pass_settings GROUP BY 1,2,3
UNION ALL SELECT 'payroll', left(class_id,8), NULL, count(*), count(*) FILTER (WHERE effective_date>now()),
       min(effective_date)::text, max(effective_date)::text FROM payroll_settings GROUP BY 1,2,3
UNION ALL SELECT 'store', left(class_id,8), availability_state || '/' || item_type, count(*), count(DISTINCT product_lineage_uuid),
       count(*) FILTER (WHERE availability_state='RETIRED' AND retired_at IS NULL)::text || ' retired_no_ts',
       count(*) FILTER (WHERE availability_state<>'RETIRED' AND retired_at IS NOT NULL)::text || ' resurrected'
FROM store_products GROUP BY 1,2,3
UNION ALL SELECT 'engine', left(class_id,8), coalesce(economy_policy_mode,'<null>'), count(*), count(*) FILTER (WHERE effective_at>now()),
       min(effective_at)::text, max(effective_at)::text FROM economic_engine GROUP BY 1,2,3
UNION ALL SELECT 'feature_settings', left(class_id,8), coalesce(economy_policy_mode,'<null>') || '/' || coalesce(economy_policy_alignment_status,'<null>'),
       count(*), NULL, (economy_policy_updated_at IS NOT NULL)::text, (economy_last_rebalanced_at IS NOT NULL)::text
FROM feature_settings GROUP BY 1,2,3,6,7
UNION ALL SELECT 'class_features', left(class_id,8), feature || '/' || (economic_version_id IS NULL)::text, count(*), NULL, NULL, NULL
FROM class_features GROUP BY 1,2,3
ORDER BY 1,2,3;

-- Q11a obligations: policy references, terminal cycles, command reservations
SELECT 'bill_cycles' q, split_part(b.internal_ref,':',1) a, (b.next_assessment_at IS NULL)::text b,
       CASE WHEN b.policy_uuid IS NULL THEN 'null_ref' WHEN r.id IS NOT NULL THEN CASE WHEN r.class_id=b.class_id THEN 'rent_ok' ELSE 'rent_xclass' END
            WHEN i.policy_uuid IS NOT NULL THEN 'ins' ELSE 'orphan' END c, count(*) n
FROM bill_cycles b LEFT JOIN rent_settings r ON r.policy_uuid=b.policy_uuid LEFT JOIN insurance_policies i ON i.policy_uuid=b.policy_uuid GROUP BY 1,2,3,4
UNION ALL SELECT 'bill_cycles_no_resv', '', '', '', count(*) FROM bill_cycles b
WHERE NOT EXISTS (SELECT 1 FROM obligation_command_reservation o WHERE o.bill_cycle_id=b.id)
UNION ALL SELECT 'obl_resv', command_name, fingerprint_version::text, split_part(idempotency_key,':',1), count(*)
FROM obligation_command_reservation GROUP BY 1,2,3,4
UNION ALL SELECT 'assessment', a.event_type, a.obligation_type,
       CASE WHEN a.policy_uuid IS NULL THEN 'null_ref' WHEN r.id IS NOT NULL THEN CASE WHEN r.class_id=a.class_id THEN
            CASE WHEN r.availability_state='IN_USE' THEN 'rent_ok_current' ELSE 'rent_ok_retired' END ELSE 'rent_xclass' END
            WHEN i.policy_uuid IS NOT NULL THEN 'ins' ELSE 'orphan' END
       || '/ledger=' || (a.ledger_transaction_id IS NOT NULL)::text || '/cycle=' || (a.bill_cycle_id IS NOT NULL)::text, count(*)
FROM assessment_events a LEFT JOIN rent_settings r ON r.policy_uuid=a.policy_uuid LEFT JOIN insurance_policies i ON i.policy_uuid=a.policy_uuid
GROUP BY 1,2,3,4
ORDER BY 1,2,3,4;

-- Q11b identity, support, operations (states and counts only)
SELECT 'users' q, user_role::text a, (provisioning_expires_at IS NOT NULL)::text b, '' c, count(*) n FROM users GROUP BY 1,2,3
UNION ALL SELECT 'seats', role, 'no_user=' || (user_id IS NULL)::text,
       'no_claimed_at=' || (claimed_at IS NULL)::text || '/no_name_hash=' || (claim_first_name_hash IS NULL)::text, count(*) FROM seats GROUP BY 1,2,3,4
UNION ALL SELECT 'seats_per_class', '', '', 'teacher_seats_gt1', count(*) FROM (SELECT class_id FROM seats WHERE role='teacher' GROUP BY 1 HAVING count(*)>1) x
UNION ALL SELECT 'profiles', coalesce(profile_type,'<null>'), 'unbound=' || (seat_id IS NULL)::text, 'no_class=' || (class_id IS NULL)::text, count(*)
FROM identity_profiles GROUP BY 1,2,3,4
UNION ALL SELECT 'issues', status, CASE WHEN status IN ('OPEN','TEACHER_REVIEW','ESCALATED_TO_DEV','DEV_RESOLVED','TEACHER_FINAL_REVIEW','CLOSED')
       THEN 'canonical' ELSE 'LEGACY' END, coalesce(issue_type,''), count(*) FROM issues GROUP BY 1,2,3,4
UNION ALL SELECT 'issue_history', coalesce(previous_status,'<null>') || '->' || new_status,
       CASE WHEN new_status IN ('OPEN','TEACHER_REVIEW','ESCALATED_TO_DEV','DEV_RESOLVED','TEACHER_FINAL_REVIEW','CLOSED') THEN 'canonical' ELSE 'LEGACY' END,
       changed_by_type, count(*) FROM issue_status_history GROUP BY 1,2,3,4
UNION ALL SELECT 'issue_actions', action_type, performed_by_type, (related_transaction_id IS NOT NULL)::text, count(*) FROM issue_resolution_actions GROUP BY 1,2,3,4
UNION ALL SELECT 'tcp', correlation_version::text, actor_type, '', count(*) FROM ticket_correlation_pack GROUP BY 1,2,3,4
UNION ALL SELECT 'chain_heads', (chain_scope='system')::text, '', 'events=' || sum(event_count)::text, count(*) FROM chain_heads GROUP BY 1,2,3
UNION ALL SELECT 'chain_mismatch', '', '', '', count(*) FROM chain_heads h
WHERE h.event_count <> (SELECT count(*) FROM audit_events e WHERE e.chain_scope=h.chain_scope)
   OR h.latest_sequence <> (SELECT max(sequence_number) FROM audit_events e WHERE e.chain_scope=h.chain_scope)
UNION ALL SELECT 'audit_signer', coalesce(signer_key_id,'<null>'), '', '', count(*) FROM audit_events GROUP BY 1,2
UNION ALL SELECT 'actor_trace', actor_type, '', '', count(*) FROM actor_request_trace GROUP BY 1,2
UNION ALL SELECT 'announcements', priority, is_active::text, '', count(*) FROM announcements GROUP BY 1,2,3
UNION ALL SELECT 'passkeys', '', '', '', count(*) FROM passkey_credentials
ORDER BY 1,2,3,4;

-- Q12 per-class row-count baseline for class-scoped tables (the repeatable SOP-DB-004 §IX.1.7 query)
WITH x AS (
SELECT 'seats' t, class_id FROM seats UNION ALL SELECT 'ledger_transaction', class_id FROM ledger_transaction
UNION ALL SELECT 'ledger_balance_snapshot', class_id FROM ledger_balance_snapshot UNION ALL SELECT 'ledger_command_reservation', class_id FROM ledger_command_reservation
UNION ALL SELECT 'entitlement_events', class_id FROM entitlement_events UNION ALL SELECT 'pending_actions', class_id FROM pending_actions
UNION ALL SELECT 'attendance_sessions', class_id FROM attendance_sessions UNION ALL SELECT 'hall_pass_logs', class_id FROM hall_pass_logs
UNION ALL SELECT 'payroll_event', class_id FROM payroll_event UNION ALL SELECT 'payroll_cycle_completion', class_id FROM payroll_cycle_completion
UNION ALL SELECT 'attendance_interval_invalidation', class_id FROM attendance_interval_invalidation
UNION ALL SELECT 'assessment_events', class_id FROM assessment_events UNION ALL SELECT 'bill_cycles', class_id FROM bill_cycles
UNION ALL SELECT 'interpretation_cycle_record', class_id FROM interpretation_cycle_record UNION ALL SELECT 'audit_events', class_id FROM audit_events
UNION ALL SELECT 'store_products', class_id FROM store_products UNION ALL SELECT 'rent_settings', class_id FROM rent_settings
UNION ALL SELECT 'hall_pass_settings', class_id FROM hall_pass_settings UNION ALL SELECT 'payroll_settings', class_id FROM payroll_settings
UNION ALL SELECT 'economic_engine', class_id FROM economic_engine UNION ALL SELECT 'class_features', class_id FROM class_features)
SELECT now() AT TIME ZONE 'UTC' observed_at_utc, t, string_agg(left(class_id,8) || '=' || n, ' ' ORDER BY class_id) per_class, sum(n) total
FROM (SELECT t, class_id, count(*) n FROM x GROUP BY 1,2) y GROUP BY t ORDER BY t;

-- Q13 hall-pass logs carrying the literal "default" policy reference, against each class's first policy row
SELECT left(h.class_id,8) class8, (h.policy_uuid='default') dflt,
       (SELECT min(effective_date) FROM hall_pass_settings s WHERE s.class_id=h.class_id) first_policy_at,
       count(*) n, min(h.timestamp) first, max(h.timestamp) last
FROM hall_pass_logs h GROUP BY 1,2,3 ORDER BY 1,2;

-- Q14 creation-evidence linkage and actor context for every ledger row (run after the owner's §5.1 ruling).
-- Structural agreement only; it does not authenticate HMACs or walk the chain.
SELECT t.lineage_version, a.feat_id, t.mechanism::text mech, (a.actor_type IS NULL) no_actor_type,
       (a.actor_id_hash IS NULL) no_actor_hash, (a.context_digest IS NULL) no_ctx, (a.seat_id IS NULL) no_seat,
       (a.seat_id = t.actor_seat_id) seat_is_actor, (a.seat_id = t.target_seat_id) seat_is_target,
       (a.class_id = t.class_id) class_ok, (a.chain_scope = 'class:' || t.class_id) scope_ok,
       (t.lineage_token = a.hmac_signature) token_ok, count(*) n
FROM ledger_transaction t JOIN audit_events a ON a.id = t.lineage_event_id
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12 ORDER BY 1,2,3;
