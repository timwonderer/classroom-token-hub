# INV-ARC-015: Temporal Model and Boundary Enforcement

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| INV-ARC-015      | 2.1     | 2026-09-22    | 1.0, 2.0    | Foundational    |

---

## I. Purpose

Define the canonical temporal model for Classroom Token Hub.

This specification governs how time is interpreted, stored, and enforced across all execution paths.

---

## II. Scope

This specification applies to:

- Timestamp storage and interpretation
- Time-based capability evaluation
- Domain command execution involving time
- Temporal boundaries (e.g., day limits)
- Logging and observability

It is binding on all DOM and FEAT specifications.

---

## III. Authority Level

Foundational within the INV-ARC namespace. Derived from `INV-CORE-000` Section III.1, `` `class_id` Centric Isolation``, and Section III.3, `Deterministic and Traceable Financial Logic`, and governed within the hierarchy described by `INV-CORE-001`.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-000_EXECUTION_MODEL.md`

---

## V. Time-Based Evaluations

Time-based evaluations in Classroom Token Hub SHALL be differentiated between the following two types:

### System-Level Evaluations (SLEs)
System-Level Evaluations are evaluations whose authority derives from the authenticated principal (i.e. `User`) or the operation of the platform itself. Examples include, but are not limited to:

- Session tracking
- System Logging
- Account Inactivity
- Observability

### Class-Level Evaluations (CLEs)
Class-Level Evaluations are evaluations whose authority derives from a specific `ClassEconomy` and therefore inherit that class's Canonical Class Timezone. Examples include, but are not limited to:

- Obligation due dates
- Payroll
- Attendance Record
- Hall Pass 
- Store item expiry dates

## VI. Core Temporal Model
1. All timestamp entry on the database SHALL be stored in UTC. This is the canonical source of truth for all temporal logic.
2. The application of temporal logic MUST differentiate between SLEs and CLEs. 
3. All SLEs SHALL be evaluated using UTC
4. All CLEs SHALL be evaluated using Canonical Class Timezone as established by the teacher of the class
5. All CLEs SHALL NOT be performed without an explicit establishment of Canonical Class Timezone. Clear and visible warning must be displayed to the teacher user.
6. Canonical Class Timezone SHALL be immutable for the lifetime of the class (as determined by the existence of the `ClassEconomy` row)
7. Changes to temporal configuration SHALL apply only to future evaluations. They SHALL NOT reinterpret or mutate previously recorded events.


---

## VII. Canonical Temporal Evaluation

All temporal evaluations SHALL be performed through a single Canonical Temporal Evaluation helper.

The helper SHALL expose only the finite set of temporal evaluation primitives permitted by this specification. It SHALL NOT expose raw temporal interpretation to downstream callers.

The Canonical Temporal Evaluation helper SHALL:

1. Accept the evaluation type (System-Level Evaluation or Class-Level Evaluation).
2. Accept the canonical execution context when evaluating Class-Level Evaluations.
3. Resolve the canonical temporal authority (UTC for SLEs, Canonical Class Timezone for CLEs).
4. Produce a canonical temporal evaluation object containing all required temporal information for downstream execution.
5. Expose only canonical temporal primitives, including:
   - earlier-than evaluation
   - later-than evaluation
   - between-boundaries evaluation
   - time-since evaluation
   - time-until evaluation
   - current evaluation day derivation
   - boundary derivation for the current evaluation day
6. Prevent callers from independently deriving or interpreting temporal state.
7. Fail closed when Canonical Class Timezone cannot be established for a CLE.

All DOM specifications, FEAT specifications, runtime services, and tests SHALL use the Canonical Temporal Evaluation helper for all temporal logic.

Business logic, route handlers, domain services, FEAT implementations, scheduled jobs, and tests SHALL NOT perform direct datetime comparisons, direct timezone conversions, direct current-time reads, or independent day-boundary derivation. Such logic SHALL be expressed through the Canonical Temporal Evaluation helper primitives.

---

## VIII. Temporal Boundaries

### VIII.1 Day Definition

A day is defined as:

> [00:00, 24:00) in class timezone

### VIII.2 Boundary Enforcement

- Temporal processes MUST NOT span multiple class days.
- Boundary crossing MUST terminate active processes.
- No carryover across day boundaries is permitted.

---

## IX. Execution Constraints

### IX.1 Capability Evaluation

- Time-based capability checks MUST use canonical class time.
- No alternate time derivation is permitted.

### IX.2 Command Execution

- Domain commands MUST enforce temporal boundaries.
- Commands MUST NOT reinterpret prior timestamps under new context.

---

## X. Observability Requirements

All time-related logs MUST include:

- UTC timestamp
- Class timezone
- Derived class time

### X.1 Correlation Packs

Correlation Packs MAY contain both System-Level Evaluation (SLE) and Class-Level Evaluation (CLE) artifacts.

Each artifact SHALL retain its original temporal authority and SHALL NOT be normalized, reinterpreted, or converted into a different temporal model solely for inclusion within a Correlation Pack.

A Correlation Pack is an evidence container and SHALL NOT alter the temporal semantics of the artifacts it contains.

### X.2 Display Convention: Classroom vs. Operations Surfaces

Section V establishes SLE/CLE as an evaluation-authority distinction. This
section states its corollary for display: which timestamp authority a
*rendered page* defaults to, independent of what governs the record
underneath it.

1. Classroom surfaces (teacher- and student-facing pages) SHALL display time
   in the rendering class's Canonical Class Timezone by default.
2. Operations surfaces (sysadmin- and system-facing pages, including the
   sysadmin navigation clock) SHALL display time in UTC by default, with no
   exception and no inference from browser locale, operator IP geolocation,
   or any other environment-derived signal. This holds even when the page
   concerns one specific class, because the operator, not the class, is the
   audience.
3. An Operations surface MAY offer a deliberate, explicit, presentation-only
   toggle that re-renders class-scoped timestamps on that one page in the
   relevant class's Canonical Class Timezone, to support an operator
   correlating a class-scoped report (e.g. "I clicked at 8:03") against
   UTC-anchored evidence (logs, traces, Correlation Pack artifacts). Such a
   toggle:
   - MUST be resolved entirely server-side, as an ordinary Page View Model
     field (INV-ARC-022 SS V.6) — never via client-side timezone inference.
   - MUST NOT establish, imply, or require Canonical Class Context for the
     request (INV-ARC-022 SS V.3; sysadmin holds no class context).
   - MUST NOT alter, normalize, or reinterpret any stored value, Correlation
     Pack artifact, or audit record (SS X.1 continues to govern the
     underlying data). It changes only what the template renders.
   - MUST default to UTC on every page load; the class-time lens is chosen
     per view, never persisted as an ambient session preference that would
     make a later, unrelated page silently render in a stale class's time.
   - MUST show the resolved IANA timezone name (e.g. "America/Los_Angeles")
     alongside any timestamp rendered in class time, so the operator can see
     which transformation, if any, is in effect.
4. Third-party operational tooling (e.g. Grafana) is out of scope for this
   section and retains its own display conventions; CTH does not build a
   parallel convention for it. CTH's own operational baseline remains UTC.

**Rationale:** An operator correlating a sysadmin page against Grafana,
application logs, and audit records benefits from every operational surface
sharing one timestamp baseline — no `+7`/`-7` arithmetic mid-incident. A
class-time lens is valuable for a narrower, deliberate purpose: checking
whether a specific class-scoped report and its underlying UTC record actually
describe the same moment. Offering that as an explicit, reversible,
display-only toggle serves both needs without contradicting either.

---

## XI. Downstream Consequence

DOM specifications MUST:

- Treat time as class-scoped and immutable.
- Enforce boundary rules strictly.

FEAT specifications MUST:

- Not introduce alternate temporal models.
- Not bypass boundary enforcement.

---

## XII. Enforcement

The following MUST be enforced through CI and runtime guards:

- No use of non-UTC storage for timestamps
- No use of non-class time in execution paths
- No cross-boundary temporal continuation
- No mutation of class timezone
- No direct datetime comparison in DOM or FEAT execution paths
- No direct current-time reads outside the Canonical Temporal Evaluation helper
- No direct timezone conversion outside the Canonical Temporal Evaluation helper
- No independent day-boundary derivation outside the Canonical Temporal Evaluation helper

---

## XIII. Final Statement

> Time is not user-relative.
> Time is not environment-relative.
> Time is class-scoped, immutable, and authoritative.

The display corollary (SS X.2):

> Classroom surfaces speak class time.
> Operations surfaces speak UTC.
> Support can translate between them — deliberately, visibly, and without
> touching the record.

---

## XIV. Amendment

Revisions to this document must:

1. Increment the version number.
2. Update the Effective Date.
3. Maintain alignment with all INV-CORE specifications.
4. Preserve the canonical temporal model.
