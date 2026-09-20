# SPEC-OPS-005: Feature Health Evidence

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-OPS-005 | 1.1 | 2026-09-19 | 1.0 | Normative |

## I. Purpose

Define how Operations evaluates public feature health from naturally occurring
application activity without synthetic users, business mutations, or a second
source of domain truth. A feature card describes **observed runtime integrity**
within a declared evidence window; it does not certify every user journey.

## II. Scope

This contract governs the five public feature keys `login`, `attendance`,
`payroll`, `roster`, and `classroom_economy`, their bounded internal
evidence, and their reduction to the application health endpoint. It does not
define the underlying domain invariants, alter owning FEATs, create canonical
incidents, or authorize external status infrastructure to read tenant state.

## III. Authority Level

Normative SPEC tier, subordinate to `DOM-OPS-001` and the owning domain and
FEAT contracts. An evaluator consumes existing authoritative execution and
verification results; it does not reinterpret business rules or repair state.

## IV. Dependencies

- `docs/DOMAIN/DOM-OPS-001_OPERATIONS_DOMAIN.md`
- `docs/DOMAIN/DOM-OPS-002_AUDIT_LINEAGE_INTEGRITY.md`
- `docs/SPEC/SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md`
- `docs/SPEC/SPEC-OPS-003_APPLICATION_OBSERVABILITY_CONTRACT.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-001_RECORD_ATTENDANCE_SESSION.md`
- `docs/FEATURE-EXECUTION/FEAT-PROD-004_COMPLETE_PAYROLL_CYCLE.md`
- `docs/STANDARD_OPERATING_PROCEDURES/OPERATIONS/SOP-OPS-001_SERVICE_STATUS_AND_INCIDENT_COMMUNICATION.md`

## V. Closed evaluator registry

Each registered evaluator MUST declare its owning execution boundary, what
counts as relevant real activity, the qualifying `SYSTEM_FAILURE` outcomes,
the owning verifier for state and transition validity, the required lineage
and reconciliation proof, its window and freshness class, and its public
wording. An undeclared or unevaluated dimension is missing evidence, not a
passing check. The initial five keys and required evidence families are:

| Key | Relevant activity | Required affirmative evidence |
|---|---|---|
| `login` | completed real sign-in attempt | Identity-owned execution result and bounded identity/claim-state validity |
| `attendance` | real attendance session command | Productivity-owned execution result, lawful state transitions, actor/target/class attribution, temporal validity, and attendance projection reconciliation |
| `payroll` | completed real payroll cycle | Productivity-owned execution result, lawful cycle state/transitions, Ledger-owned posting lineage and duplicate/orphan checks, and balance/projection reconciliation |
| `roster` | real roster provisioning or edit command | Identity/Class-owned execution result, lawful seat/claim state and class isolation, and roster projection reconciliation |
| `classroom_economy` | a registered real economic command | owning FEAT result, applicable Ledger/Obligations/Store/Class verifier results, and required cross-domain lineage/reconciliation |

The `classroom_economy` key is a composite. It MUST remain `UNKNOWN` until
the implementation registry names the included command families and every
required owning verifier; a successful sample from only one family cannot
make the whole composite `PASS`. Likewise, a payroll check that sees no
recent completed cycle cannot infer health from a clean error log.

The verifier for each row MUST be the owning domain's lawful proof surface,
not a new Operations SQL reconstruction of its business rules. Expected
business denial is not a system failure (`SPEC-OPS-003` §VI), but it also
does not establish successful feature activity.

## VI. Evaluation

Each evidence item carries an observation/check time, source, class-bound
execution provenance internally, probe/evaluator version, and a closed
result code. The internal evaluator may consume only authorized one-class
verification results. An Operations coordinator receives redacted outcomes
through opaque work items and MUST NOT issue a cross-class domain query.

For each feature and evaluation window:

1. A fresh proven execution failure, invalid state/transition, broken
   lineage, or failed reconciliation yields `FAIL + KNOWN`, even if another
   required dimension is unavailable. Preserve the distinct underlying
   evidence; this reduction is only a current assessment.
2. Otherwise, `PASS + KNOWN` requires relevant real activity and fresh
   affirmative results for **every** declared dimension. A zero-error count
   alone is never affirmative evidence of correctness.
3. Otherwise, return `UNKNOWN + UNAVAILABLE`. This includes no recent
   activity, incomplete coverage, stale results, unavailable sources,
   skipped checks, and failed dispatch. Do not turn an idle period into a
   failure or a pass.

Feature-health readiness uses the approved `REALTIME` freshness class
(one-minute collection cadence, five-minute maximum evidence age). A
periodic correctness proof may retain its separately approved freshness
class, but a stale or missing required proof still blocks feature `PASS`.
An evaluator MUST NOT backdate a current result or substitute an old
successful run for recent activity.

## VII. Persistence and boundary

Application/Operations health evidence is append-only within its retention
class. A replaceable current assessment MAY be derived from it. The public
health endpoint is a pure GET: it reads a bounded assessment and MUST NOT
execute a FEAT, repair a record, or start a verifier. The external collector
receives only capability key, observation class, lawful outcome/epistemic
pair, checked-at time, a closed diagnostic code, and the bounded evaluator
version when a registered feature evaluator ran. The collector derives the
bounded evidence source from the validated signal origin and stamps its own
transport `probe_version`; neither value substitutes for the owning evaluator
version. An unregistered `UNKNOWN` has no evaluator version. No class/user/seat
identifier, contact detail, credential, financial value, row ID, free-form
exception, or raw verifier result crosses that boundary.

The external status service stores observations and projects communication;
it does not become the authority for Identity, Productivity, Ledger, or
canonical Operations incidents.

Transport is not provenance: the external collector's fetch of an
application-reported feature result does not make that result an independent
`EXTERNAL_PROBE`. Feature results MUST retain the distinct bounded evidence
source `APPLICATION_RUNTIME_EVIDENCE` in external observation records.
The collector's own HTTP reachability result remains `EXTERNAL_PROBE`.
Neither source may overwrite the other's evidence or freshness timestamp.
The collector derives `APPLICATION_RUNTIME_EVIDENCE` only from a validated,
closed application signal; it derives `EXTERNAL_PROBE` only from its own
reachability check. The observation `probe_version` identifies the collector
transport protocol, not the feature evaluator. A feature evaluator MUST
provide a separately bounded and validated evaluator version in the
application-to-collector signal before its result can be registered as `PASS`
or `FAIL`. The external observation stores that version separately from
`probe_version`. Until that producer and transport field are implemented,
its public result remains `CHECK_NOT_REGISTERED` / `UNKNOWN`.

## VIII. Public wording

The card headline MUST name the feature, not promise that every operation
works. A `PASS` detail may say, “Recent activity completed without detected
integrity failures.” A `FAIL` detail says that a problem was detected,
without exposing internal evidence. An `UNKNOWN` detail says, “Not enough
recent evidence to verify.” The card MUST NOT say “Payroll works” from
silence or imply universal availability from one observed class.

## IX. Validation

Targeted tests MUST cover each registered evaluator's real-activity
threshold, qualifying system failure, expected denial, every required
validity/lineage/reconciliation dimension, missing/stale evidence, conflict,
one-class authorization, redaction at the external boundary, and public
wording. An evaluator is not registered merely because a key appears in the
status-page UI. Until its evidence producer and tests exist, its signal
remains `UNKNOWN/UNAVAILABLE` with `CHECK_NOT_REGISTERED`.

## X. Amendment

Changing the closed keys, required evidence families, public meaning, or
cross-boundary payload requires a version increment and review against
`DOM-OPS-001`, the owning domain/FEAT, `SPEC-OPS-002`, and
`SOP-OPS-001`. Update the documentation index.
