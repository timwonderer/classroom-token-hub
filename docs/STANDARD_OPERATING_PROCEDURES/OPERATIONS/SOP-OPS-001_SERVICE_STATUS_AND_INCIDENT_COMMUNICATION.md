# SOP-OPS-001: Service Status and Incident Communication

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-OPS-001 | 1.2 | 2026-09-21 | 1.1 | Normative |

## I. Purpose

Define the human procedures for operating independent external status infrastructure and communicating service incidents in a manner consistent with the canonical Operations domain.

## II. Scope

This procedure governs external health observation, status-page publication, incident communication, operator escalation, and recovery communication for Classroom Token Hub. It applies to status infrastructure outside the CTH application runtime, including its monitoring, storage, deployment, and operator interfaces.

This procedure does not authorize the external service to mutate CTH business state, access tenant data, or establish domain truth.

## III. Authority Level

Normative (SOP Tier). Subordinate to `INV-CORE-000`, `INV-CORE-001`, `INV-ARC-009`, `INV-ARC-016`, `DOM-OPS-001`, and `DOM-OPS-002`.

`DOM-OPS-001` owns Operational Truth and Status Page Publication State. This SOP defines how operators carry out that purpose; it does not create an additional authority layer.

## IV. Dependencies

- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `SOP-CORE-000_Sop_Foundation.md`
- `SOP-DOC-000_DOCUMENTATION_STANDARD.md`
- `SPEC-OPS-006_PUBLIC_REQUEST_MONITORING.md`

## V. Operating Boundary

1. The status service is an independent observation and communication surface.
2. It may observe externally available behavior and record its own observations.
3. It must not receive PostgreSQL, application-admin, teacher, student, class-scoped, or mutation credentials.
4. It must not ingest or publish `class_id`, `seat_id`, `user_id`, join codes, names, contact methods, financial values, or other tenant-linked data.
5. It must not recompute or replace business-domain truth. Operational interpretations must remain consistent with `DOM-OPS` contracts.
6. Liveness, readiness, and correctness must remain distinguishable; a reachable endpoint is not sufficient evidence of correctness.

### Public measurements and internal verification

Public request monitoring follows SPEC-OPS-006. Verify the fixed route grouping,
query window, counts, quantiles, source timestamps, thresholds and coverage before
publishing. HTTP response distributions are observations, not feature correctness
or semantic execution outcomes. Missing and stale measurements remain explicit.
Internal feature-integrity verification remains governed by SPEC-OPS-005 and its
one-class authorization, affirmative proof, freshness and redaction requirements.
Those internal evaluator registrations do not gate numerical public cards.

## VI. Observation and Publication Procedure

For each scheduled or manually initiated observation:

1. Generate and preserve a correlation identity for the observation workflow.
2. Record the observation as an append-only operational event with timestamp, component, outcome, and bounded diagnostic detail.
3. Classify public request snapshots using SPEC-OPS-006; preserve the separate liveness, readiness and correctness classifications for internal evidence.
4. Compare the result with the applicable Operations-domain health semantics.
5. Publish only the approved user-facing status and actionable communication; keep sensitive diagnostic detail operator-only.
6. Preserve internal failures, retries, skipped executions and recovery observations as distinct events. Public request snapshot redelivery is idempotent by source minute under SPEC-OPS-006; transport retries never inflate measurement history.

## VII. Incident Procedure

When a condition requires incident communication:

1. Confirm the observation and its originating correlation context.
2. Publish investigated user impact through an operator notice under DOM-OPS-001 during normal operation or service unavailability. Record an investigation evidence note/reference; automated snapshot links are optional. Canonical incidents, when created, retain their independent append-only lifecycle; a notice never implies that one exists.
3. Publish the minimum clear message needed by teachers and students: affected capability, current impact, recommended user action (including “no action required” when appropriate), recovery expectation, and next update expectation.
4. When recovery timing is known or reasonably estimated, identify the recovery expectation as estimated where applicable. When recovery timing cannot be reasonably established, do not infer one from historical incidents; state that no recovery estimate is currently available and provide the next-update expectation.
5. Escalate integrity failures, audit-lineage failures, privacy concerns, or uncertainty about canonical interpretation to the responsible operator.
6. On recovery, record the recovery observation, append the resolution event, and publish a resolution message.
7. Never delete, rewrite, or conceal prior incident, health, retry, or recovery evidence.

External status notices must remain distinguishable from canonical incidents. When canonical service becomes available, reconcile or link the notice to canonical incident lineage where applicable; do not rewrite the original notice, observation, or publication history.

## VIII. Failure and Recovery Boundaries

- If CTH is unavailable but the status service is available, continue publishing bounded observations and incident updates.
- If the status service is unavailable, CTH remains the authority for its own runtime behavior; restore status infrastructure through its documented deployment and recovery procedure.
- If monitoring sources disagree, preserve both observations, avoid an unjustified healthy declaration, and escalate for Operations-domain adjudication.
- Automatic remediation requires explicit authorization, separate logging, and a distinct remediation classification; detection alone never authorizes business-state repair.

## IX. Prohibited Operations

- Treating the status service as a CTH domain authority.
- Accessing tenant-scoped records or credentials from external status infrastructure.
- Publishing PII, class-linked data, financial data, raw internal errors, secrets, or opaque diagnostic payloads.
- Declaring healthy solely from liveness when readiness or correctness is failing or unevaluated.
- Deleting or mutating operational history to make the public status appear healthier.

## X. Amendment

Revisions require incrementing the version, updating the Effective Date and Supersedes fields, preserving subordination to the listed `INV` and `DOM-OPS` documents, and updating the documentation index. Changes that alter Operational Truth or status authority must be made in the governing `DOM-OPS` or higher-level documents before this procedure is amended.
