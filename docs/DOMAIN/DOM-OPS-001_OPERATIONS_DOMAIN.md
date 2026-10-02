# DOM-OPS-001: Operations Domain

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-OPS-001      | 2.12    | 2026-10-02     | 2.11       | Normative       |

*Revision 2.12 (2026-10-02; ratified by the owner 2026-10-02): §1 Public Request Monitoring — the closed component registry gains `hall_pass`. A 404 on a request-resolution route that `SPEC-OPS-006` designates is a failed request. It is never an outage or an incident. When such 404s reach `SPEC-OPS-006`'s rate-plus-minimum rule, they are a signal of a possible problem: they are reported on that component, and they qualify the overall summary as `Detected problems`, as a fresh 5xx does. Motivated by 2026-10-01, when a teacher's Approve or Reject and a student's Cancel answered 404 "Pending request not found." about half the time while the status page showed nothing: hall passes had no component, and no 404 counted.*

## 0. Authority Level and Dependencies

Normative. Subordinate to `INV-CORE-000` and `INV-ARC-009`.

### Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-009_DOMAIN_AUTHORITY_FOR_STATE.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-004_CROSS_TENANT_ISOLATION.md`

---

## 1. Domain Authority

The Operations domain is the single authority over the **Operational Truth** of the system. It governs how the system observes itself, records its behavior, and communicates its status to external actors.

### Operations OWNS Authority Over:
*   **Health Status**: The aggregated state of system liveness, readiness, and correctness.
*   **Invariant Execution Records**: The trace and result of every runtime invariant check.
*   **Incident Records**: The lifecycle and historical record of system failures.
*   **Structured Operational Logs**: The standard and storage for system-level telemetry.
*   **Audit Trail Standards**: The high-integrity record of security-sensitive and financial side effects.
*   **Background Job Execution Traces**: The history of scheduled or asynchronous work.
*   **Correlation / Trace Identity**: The generation and propagation of workflow identifiers.
*   **Alert State**: The lifecycle of notifications triggered by operational events.
*   **Status Page Publication State**: The public-facing representation of system health and incidents.
*   **Retention Policy State**: The rules governing the lifespan of operational data.

### Independent Operator Publication

Independent status infrastructure MAY maintain and publish bounded operator communication records during normal operation and canonical-service unavailability. Operators may report independently investigated user impact and explicitly bounded guidance without requiring a fabricated automated observation or canonical incident.

An `ExternalStatusNotice` is a communication artifact, not Operational Truth and not a canonical incident. It:

*   may report independently observed service conditions, investigated user impact and explicitly bounded operator guidance;
*   MUST NOT infer internal domain state, internal cause, or a canonical incident solely from telemetry; human interpretations must be grounded in the operator's investigation and identified as operator communication;
*   MUST remain distinguishable from `incident_events` and `incident_summary`;
*   MUST preserve its original observation and publication history without rewriting;
*   MAY be reconciled with or linked to canonical incident lineage when canonical service becomes available, where applicable.

An operator notice records its investigation evidence note or reference; links to automated snapshots are optional. This channel preserves useful independent public communication without creating a second Operations authority.

### Operations Explicitly DOES NOT Own:
*   **Business Domain Truth**: It does not define what a balance is, whether a student is present, or if an item is purchased.
*   **Feature Policy**: It does not decide which features are enabled for a class.
*   **Financial Balances**: It does not own the math or current state of the Ledger.
*   **Attendance Facts**: It does not own the tap logs or session status.
*   **Obligation Facts**: It does not own debt or assessment logic.
*   **Entitlement Balances**: It does not own the count of perks or items.
*   **Economic Policy Truth**: It does not own any economic policy table. Class configuration and `economic_engine` are owned by `DOM-CLASS-001`; each policy's history is its owning domain's own table (`DOM-CLASS-003` §V).
*   **Operational Boundary Legality**: It does not determine whether a rent cycle has closed, an insurance period has expired, or an accrual rollover is lawful. Those determinations belong to the owning operational domain (see §8).

### Application Availability Gate

Cloudflare Access is the sole infrastructure gate for restricting access to the
application hostname during prelaunch and operational work. It replaces the
application maintenance page, environment flag, query-token bypass, and persistent
session bypass. The application MUST NOT implement a parallel maintenance gate.

Access admission does not establish an application principal, class scope, or
capability. Normal Identity authentication and all INV/DOM/FEAT authorization
checks remain required after admission. Access policy is managed outside the
application; no application FEAT or sysadmin session may bypass it. Access login
email is handled by Cloudflare, not requested or stored by the application.

The origin must remain protected against paths around Cloudflare. Public health
probes must use an explicitly authorized service token; local deployment probes
remain independent. Gate messaging communicates an access restriction and MUST
NOT be treated as evidence of application health or canonical incident state.
Genuine service errors retain their normal HTTP error handling.

### Public Request Monitoring

The public automated status surface reports bounded HTTP request measurements,
not feature correctness certification. Its closed component registry is `service`,
`login`, `attendance`, `hall_pass`, `payroll`, `roster`, and `classroom_economy`. Route groups
identify the measured request family; they do not establish domain truth or prove
that a user journey completed. HTTP 404, 500 and 5xx rates and p80/p95 latency may
be displayed with request counts, observation window, source freshness and coverage.

The approved numerical contract is documented in `SPEC-OPS-006`. Overall public
availability follows the minute-by-minute application endpoint and database checks,
with five-minute expiry if checks stop. Quiet request traffic does not revoke fresh
connectivity evidence. Active operator notices, fresh observed server errors, and
failed-request 404s that reach the `SPEC-OPS-006` rule qualify the summary as
`Detected problems`: signals of possible issues were observed. That state does not
declare an outage, does not open an incident and never creates either automatically.
Reachability never certifies business correctness.

Feature cards report request outcomes without a minimum traffic count. Idle windows
show `No recent activity` with the last observed outcome and original window timestamp
as historical context, retained for at most seven days. Historical activity MUST NOT
be represented as current health or cleared solely because requests stop. Failed or
stale monitoring remains explicit. HTTP 4xx responses, including 404, remain numerical
observations and MUST NOT by themselves declare a feature outage. One fresh 5xx is
reported as an observed server error, not a diagnosis or canonical incident.

A component MAY designate request-resolution routes: routes the application's own
page calls only with an identifier it has just shown the user, to act on that item.
A 404 there means the item the user was shown could not be found, so it is a failed
request rather than an expected absence. `SPEC-OPS-006` closes the list of designated
routes; at 2.12 it is the hall-pass approve, reject and cancel routes and nothing
else. Such a 404 is not an outage, a diagnosis or a canonical incident, and it never
creates one. A single one may be a double click or a stale page, so it is a signal
only when a window holds enough of them: `SPEC-OPS-006` fixes that rate-plus-minimum
rule. When the rule holds, the component reports an observed error and the overall
summary reads `Detected problems`, exactly as for a fresh 5xx: signals of a possible
problem were observed. Every other 404 keeps the rule above and qualifies nothing.

Public current cards and historical percentages do not depend on internal integrity
evaluator registration. Internal readiness, correctness, lineage, reconciliation
and single-class verification requirements remain unchanged; their results MUST NOT
be inferred from HTTP response distributions. `SPEC-OPS-005` governs those internal
assessments independently. Raw logs, tenant identifiers, credentials, financial
values and arbitrary diagnostic payloads MUST NOT cross the public boundary.

The status service receives only closed numerical snapshots from a read-only
monitoring source. Firestore retains immutable snapshots and replaceable current
and historical derivatives. History describes measured windows and explicitly shows
coverage; gaps are not successful uptime. Public GET requests read persisted state
and MUST NOT initiate queries, samplers, verifiers or mutations.

### Interactions:
*   **Reads From**: All domains (Identity, Ledger, Obligations, Attendance, Store, Class Config) to evaluate invariants and health.
*   **Consumed By**: Support Tools (DOM-SUP), External Status Pages, Monitoring Systems, and Incident Response Teams.

---

## 2. State Classification

| State Entity | Classification | Justification |
| :--- | :--- | :--- |
| **Invariant Run Record** | Authoritative Event | A point-in-time detection of system (in)correctness. |
| **Health Check Result** | Authoritative Event | A point-in-time observation of component status. |
| **Structured Log Event** | Authoritative Event | Immutable record of system telemetry. |
| **Audit Event** | Authoritative Event | High-integrity, non-repudiable record of side effects. |
| **Incident Event** | Authoritative Event | Append-only record of an incident's lifecycle change. |
| **Alert Event** | Authoritative Event | Append-only record of a notification's lifecycle change. |
| **Job Execution Event** | Authoritative Event | Append-only record of background work progress/outcome. |
| **Trace / Correlation ID** | System Guard | The technical glue ensuring causality and traceability. |
| **Incident Summary** | Cache | Projection derived from incident events for fast current-state lookup. |
| **Status Page State** | Derived State | Separately presents automated request measurements, measured-window history and operator communication. |
| **External Status Notice** | Non-authoritative Communication Artifact | Bounded public communication based on independent external observation; never a canonical incident. |
| **Retention Policy State**| Authoritative Directive State | Defines the legal/technical lifespan of operational records. |

---

## 3. Invariants

### INV-OPS-001: Observability Without Business Mutation
*   **Statement**: The Operations domain may observe and report on any domain state but MUST NOT directly mutate business domain state.
*   **Constraints**:
    *   No direct SQL `UPDATE` or `DELETE` on tables owned by Identity, Ledger, Obligations, Attendance, Store, or Class Config.
*   **Prohibited Action**: An invariant runner automatically adjusting a student's balance or attendance status.

### INV-OPS-002: Append-Only Lifecycle State
*   **Statement**: All lifecycle state changes (Incidents, Alerts, Job Executions, Invariant Runs) MUST be recorded as append-only events.
*   **Constraints**:
    *   The event log is the source of truth.
    *   Any mutable "current state" table is a secondary projection or cache.
*   **Prohibited Action**: Updating a `job_execution` row from `RUNNING` to `SUCCESS` without emitting a corresponding event record.

### INV-OPS-003: Structured Logging Consistency
*   **Statement**: All operational logs must be JSON-structured and include mandatory, indexed trace fields outside the JSON payload.
*   **Constraints**:
    *   Mandatory Top-level Fields: `timestamp`, `correlation_id`, `domain`, `level`.
    *   JSON only for variable payload.
    *   **Critical trace fields MUST NOT exist only inside JSON blobs.**
*   **Prohibited Action**: Hiding a critical `seat_id` or `error_code` inside an opaque JSON string if it is required for primary indexing.

### INV-OPS-004: Correlation Integrity
*   **Statement**: Every request, background job, or internal workflow MUST carry a stable `correlation_id` across boundary hops.
*   **Constraints**:
    *   Identities must be generated at the entry point.
    *   **Incidents MUST anchor at least one originating correlation context.**
*   **Prohibited Action**: Creating an incident that cannot be linked back to a specific trace or invariant run.

### INV-OPS-005: Invariant Runner Authority
*   **Statement**: Runtime invariant runners may detect violations but must not silently "heal" business state.
*   **Prohibited Action**: An automated script "fixing" an out-of-sync ledger without an auditable business-logic transaction.

### INV-OPS-005A: Single-Scope Verification Execution
*   **Statement**: Operations may coordinate verification across the system only by dispatching independently authorized verification executions, each bound to exactly one canonical `class_id`.
*   **Constraints**:
    *   A verification worker MUST read and evaluate one `class_id` boundary per execution.
    *   A coordinator MUST NOT read tenant tables, issue a cross-class domain query, reconstruct a teacher-wide class set, or combine class identifiers in one domain execution.
    *   The coordinator MAY receive a pre-authorized opaque work item and MAY aggregate redacted outcomes such as check name, state, freshness, and failure count without tenant identity.
    *   A worker result MUST be reduced to the approved Operations result boundary before leaving its class-bound execution.
    *   Failed dispatch, missing work, stale results, and worker infrastructure errors remain distinct from a proven invariant violation.
*   **Prohibited Action**: Treating a loop over `class_id` values or a global aggregate query as compliant merely because each inner query is filtered.

### INV-OPS-006: Health Semantics
*   **Statement**: System health must distinguish between Liveness, Readiness, and Correctness.
*   **Prohibited Action**: Reporting "Healthy" when a critical domain invariant (e.g., zero-sum ledger) is failing.

### INV-OPS-007: Audit Completeness and Structure
*   **Statement**: Any action resulting in a financial, security, or identity-binding side effect MUST produce an `Audit Event` with a structured `changes` schema.
*   **Constraints**:
    *   Audit `changes` MUST follow a structured schema (before/after or field-delta format).
*   **Prohibited Action**: Storing arbitrary, unstructured blobs in the `audit_log.changes` field.

### INV-OPS-008: Append-Only Operational History
*   **Statement**: Incident history, invariant results, and audit events must be append-only within their retention window.
*   **Prohibited Action**: Deleting a record of a failed background job because it was eventually retried successfully.

### INV-OPS-009: Failure Visibility
*   **Statement**: Partial failures, retries, rollbacks, and skipped executions must be explicitly visible as distinct events.
*   **Prohibited Action**: Hiding internal retries from the operational trace.

### INV-OPS-010: Retention Enforcement Boundary
*   **Statement**: Retention enforcement MUST be explicit, logged, and never applied across different retention classes (Audit vs Debug).
*   **Constraints**:
    *   Audit and Incident records MUST NOT be purged by generic log cleanup scripts.
*   **Prohibited Action**: Accidental purge scripts nuking audit data due to shared storage keys.

### INV-OPS-011: No Hidden Remediation
*   **Statement**: Any automatic remediation MUST be explicit, logged, and separately classified from detection.
*   **Prohibited Action**: A background job "cleaning up" data without logging the specific records changed and the rationale.

### INV-OPS-012: Class/Seat/User Trace Boundaries
*   **Statement**: Classroom operational records MUST use `seat_id` (economic actor) under `class_id` (universe). Authentication principal IDs belong only to the Identity references allowed by INV-ARC-019.
*   **Prohibited Action**: Persisting or logging a `user_id` as a classroom actor, including under an actor or teacher alias.

---

## 4. State Transitions

### Operational Event Lifecycle
*   **Emit Structured Log**: (System) -> Effect: Appends to `operational_events`.
*   **Record Audit Event**: (Domain Service) -> Effect: Appends to `audit_log`.

### Invariant Runner Lifecycle
*   **Start Invariant Run**: (Scheduler/Trigger) -> Effect: Appends `START` to `invariant_run_events`.
*   **Complete Invariant Run**: (Runner) -> Effect: Appends `PASS` to `invariant_run_events`.
*   **Fail Invariant Run**: (Runner) -> Effect: Appends `FAIL` to `invariant_run_events`.
*   **Coordinate Scoped Runs**: (Operations Coordinator) -> Effect: Dispatches independently class-bound verification executions and receives only bounded redacted results.

### Incident Lifecycle
*   **Create Incident**: (System/Admin) -> Effect: Creates `incident_summary` AND appends `CREATED` to `incident_events`.
*   **Update Incident**: (Admin/System) -> Effect: Appends `UPDATED` to `incident_events`.
*   **Resolve Incident**: (Admin/System) -> Effect: Updates `incident_summary` AND appends `RESOLVED` to `incident_events`.

### External Publication Lifecycle
*   **Publish External Status Notice**: (Independent Status Infrastructure) -> Effect: Appends a bounded communication artifact and its publication event outside the canonical incident lifecycle.
*   **Reconcile External Status Notice**: (Status Infrastructure/System) -> Effect: Adds a linkage to canonical incident lineage when available; never rewrites the original notice or observation.

### Alert Lifecycle
*   **Emit Alert**: (System) -> Effect: Appends `TRIGGERED` to `alert_events`.
*   **Acknowledge Alert**: (Operator) -> Effect: Appends `ACKNOWLEDGED` to `alert_events`.
*   **Resolve Alert**: (System/Operator) -> Effect: Appends `RESOLVED` to `alert_events`.

### Background Job Lifecycle
*   **Start Job**: (Scheduler) -> Effect: Appends `STARTED` to `job_events`.
*   **Complete Job**: (Worker) -> Effect: Appends `SUCCESS` to `job_events`.
*   **Fail Job**: (Worker) -> Effect: Appends `FAILED` or `RETRY` to `job_events`.

### Health Lifecycle
*   **Record Health Check**: (System/Runner) -> Effect: Appends check result to `health_check_events`.

---

## 5. Derived Schema

### `operational_events`
*   `id`: UUID
*   `timestamp`: TIMESTAMPTZ (Indexed)
*   `correlation_id`: UUID (Indexed)
*   `domain`: VARCHAR (Indexed)
*   `level`: ENUM ('DEBUG', 'INFO', 'WARN', 'ERROR', 'CRITICAL')
*   `message`: TEXT
*   `payload`: JSONB

### `audit_log`
*   `id`: UUID
*   `timestamp`: TIMESTAMPTZ
*   `actor_id`: UUID
*   `correlation_id`: UUID
*   `action`: VARCHAR
*   `resource_id`: VARCHAR
*   `changes`: JSONB (Strict schema: `before`/`after`)

### `invariant_run_events`
*   `id`: UUID
*   `invariant_id`: VARCHAR (Reference to INV-*)
*   `event_type`: ENUM ('START', 'PASS', 'FAIL', 'ERROR')
*   `timestamp`: TIMESTAMPTZ
*   `correlation_id`: UUID
*   `payload`: JSONB (Specific violations detected)

### `incident_events`
*   `id`: UUID
*   `incident_id`: UUID
*   `timestamp`: TIMESTAMPTZ
*   `event_type`: ENUM ('CREATED', 'UPDATED', 'RESOLVED', 'COMMENT')
*   `payload`: JSONB

### `incident_summary` (Cache)
*   `id`: UUID
*   `correlation_id`: UUID (Originating context)
*   `title`: TEXT
*   `severity`: ENUM ('SEV1', 'SEV2', 'SEV3')
*   `status`: ENUM ('OPEN', 'RESOLVED')
*   `opened_at`: TIMESTAMPTZ

### `alert_events`
*   `id`: UUID
*   `alert_type`: VARCHAR
*   `event_type`: ENUM ('TRIGGERED', 'ACKNOWLEDGED', 'RESOLVED')
*   `timestamp`: TIMESTAMPTZ
*   `correlation_id`: UUID
*   `payload`: JSONB

### `job_events`
*   `id`: UUID
*   `job_name`: VARCHAR
*   `event_type`: ENUM ('STARTED', 'SUCCESS', 'FAILED', 'RETRY', 'SKIPPED')
*   `timestamp`: TIMESTAMPTZ
*   `correlation_id`: UUID
*   `payload`: JSONB

### `health_check_events`
*   `id`: UUID
*   `checked_at`: TIMESTAMPTZ (when the check completed; nullable only when no check ran)
*   `received_at`: TIMESTAMPTZ (when Operations received the bounded result)
*   `check_type`: ENUM ('LIVENESS', 'READINESS', 'CORRECTNESS')
*   `component`: VARCHAR
*   `evidence_source`: bounded source from the approved Operations registry
*   `freshness_class`: ENUM ('REALTIME', 'PERIODIC_CORRECTNESS', 'DEEP_INTEGRITY')
*   `staleness_state_at_receipt`: ENUM ('FRESH', 'STALE', 'UNKNOWN')
*   `outcome`: ENUM ('PASS', 'FAIL', 'UNKNOWN')
*   `epistemic_state`: ENUM ('KNOWN', 'UNAVAILABLE')
*   `correlation_id`: UUID
*   `probe_version`: VARCHAR (version of the check or collector protocol)
*   `evaluator_version`: VARCHAR (nullable only when no feature evaluator ran)
*   `payload`: JSONB (closed, bounded diagnostic fields only; no tenant identity or raw domain result)

The recorded staleness state describes the result at receipt; it is immutable
with the event. A current projection MUST recompute freshness from `checked_at`,
`freshness_class`, and its evaluation time rather than trusting a historical
`FRESH` value. Missing `checked_at` yields `UNKNOWN`, never a current pass.
For application feature results, `probe_version` identifies transport and
`evaluator_version` identifies the owning feature evaluator; they are not
interchangeable. A registered feature `PASS` or `FAIL` requires both.

The only lawful raw pairs are `PASS + KNOWN`, `FAIL + KNOWN`,
`FAIL + UNAVAILABLE`, and `UNKNOWN + UNAVAILABLE` as specified in
`SPEC-OPS-002`. A feature assessment derived from several checks may preserve
disagreement separately; it MUST NOT encode aggregate conflict as a raw
health event.

---

## 6. Edge Case Decisions

1.  **Log vs. Audit vs. Incident vs. Alert**:
    *   **Log**: Telemetry (Telemetry).
    *   **Audit**: Accountability (Integrity).
    *   **Alert**: Attention (Notification lifecycle).
    *   **Incident**: Duration (History of failure).
2.  **Correlation ID Ownership**: Operations owns the standard and propagation rules.
3.  **Health Definitions**:
    *   **Live**: Process is up.
    *   **Ready**: Dependencies are accessible.
    *   **Correct**: Business invariants are passing.
4.  **Auto-Fixing**: No. Invariant runners detect. Remediation must be an explicit, auditable FEAT.
5.  **Audit Requirements**: Mandatory for every Ledger mutation, Identity claim, Store purchase, and Class deletion.
6.  **Incident Correlation**: Incidents must anchor at least one originating correlation context.
7.  **Status Page State**: Independent public request measurements and their historical rollups remain separate from operator notices. Internal health/correctness results and canonical incidents retain their own authority; request telemetry does not replace them.
8.  **Retention Enforcement**: Must be explicit, logged, and isolated by retention class.
9.  **Repeated Failures**: Recorded as distinct events in `job_events`, `invariant_run_events`, or `health_check_events`.
10. **Avoiding Analytics**: Operations stores diagnostic/correctness data only.
11. **Verification Scope**: Cross-class correctness aggregation is permitted only over redacted results from independently class-bound executions; it is not a cross-class domain read.

---

## 7. Identity & Trace Model Alignment

*   `seat_id`, `class_id`, and `correlation_id` preserve classroom attribution. When no class/seat context is established, omit actor identity rather than substitute an authentication principal.

---

## 8. Scheduled Policy Activation (none)

*Amended 2.11 (operator ruling 2026-09-30).* There is no scheduled policy activation, and no OPS job exists to perform one. A change saved for a later boundary is a row of its owning domain's append-only table carrying the instant from which it governs (`DOM-CLASS-003` §V, §VII); the row in force is selected by time, so nothing activates it. The class-wide `policy_versions` / `policy_transitions` tables and the activation job that read them were retired and removed.

### 8.1 Prohibited OPS Policy Patterns

The following are constitutionally prohibited:

- an OPS job writing or rewriting a row of an economic policy table;
- an OPS job determining rent cycle legality or insurance renewal legality;
- an OPS job calling GET-style handlers to change policy as a side effect;
- an OPS job, table or flag that "activates" a recorded policy row: a row governs from its own date, and whether it has taken effect is answered by the owning domain's resolver, never by execution state.

### 8.2 Evidence

Operational jobs that consume policy (payroll, rent reconciliation, interest) record their own execution evidence in `job_events` (§4, §5). OPS evidence does not constitute policy truth. Policy truth remains in the owning domain's table (`DOM-CLASS-003` §V).
