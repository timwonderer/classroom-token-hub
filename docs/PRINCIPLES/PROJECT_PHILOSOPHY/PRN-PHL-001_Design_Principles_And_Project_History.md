---
title: Design Principles, Philosophy, and Project History
description: The design philosophy, guiding principles, and anti-goals of Classroom Token Hub, separated from the history of how it arrived at them
keywords: [philosophy, principles, history, milestones, evolution, anti-goals, design]
roles: [teacher, developer]
---

# PRN-PHL-001: Design Principles, Philosophy, and Memory

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| PRN-PHL-001 | 2.0 | 2026-09-20 | 1.2 | Informative |

## Document Purpose

This document preserves the design philosophy, guiding principles, and formative lessons of Classroom Token Hub.
*It is not a changelog. It is a record of decisions that survived real classrooms.*

Chronological releases and versioned changes live in the repository's `CHANGELOG.md`, which is
maintained for developers and is deliberately not published to this documentation site.

> [!NOTE]
> This document is Informative. It records why the system is shaped the way it is; it does not
> define runtime rules and cannot modify or supersede any `INV-*`, `DOM-*`, or `FEAT-*` contract.
> Where this document and a normative contract appear to disagree, the contract governs.

## How to Read This Document

The document is in two parts, and the distinction between them is load-bearing.

**Part I is what is true now.** It is written in the present tense and describes the system as it
currently works. Every architectural claim in it must be checkable against the code and against the
governing `INV-*` and `DOM-*` contracts. When the system changes, Part I is corrected.

**Part II is how it got here.** It is written in the past tense and describes decisions as they were
made, including decisions that have since been replaced. Nothing in Part II may be read as a
description of current architecture. A milestone that no longer holds is marked **Superseded** and
names what replaced it.

This separation exists because the two were previously interleaved, and a reader had no way to tell
a durable principle from a decision that had been reversed. Version 1.2 of this document stated that
the join code was "the absolute source of truth" and that the claim had "reshaped the entire data
model." Both sentences were accurate when written and are the inverse of current architecture: the
canonical context object now *raises* on any attempt to read a join code. A reader following that
document into the codebase would have been misled by a document that was never wrong, only old.

The rule that follows from it: **a principle belongs in Part I only for as long as it is true.**
When a decision is replaced, it moves to Part II and takes its reasoning with it. The reasoning is
usually still valuable — it is often the thing that survives when the mechanism does not.

---

# Part I — What Is True Now

## Project Vision

Classroom Token Hub exists to teach financial literacy and systems thinking through lived participation in a simulated classroom economy.

Students do not merely learn about money.
They earn it, lose it, insure against risk, misjudge trade-offs, recover from mistakes, and gradually understand consequences.

The system treats money not as a reward mechanism, but as a constraint system. It is a real-time experiment that exposes how incentives shape behavior over time.

## Educational Philosophy

This project is grounded in several beliefs that are treated as non-negotiable:

- Experience comes before explanation
Students understand systems after they feel them. Abstraction follows experience, not the other way around.
- Consequences teach faster than warnings
Missed time, poor planning, and unmanaged risk are more instructive than reminders or lectures.
- Fairness is responsiveness, not sameness
The system accounts for reality without pretending all students start from identical conditions.
- Agency without guardrails collapses systems
Freedom is meaningful only when bounded.
- Simulations must bind their designers
If teachers are exempt from the system, the simulation lies.

These beliefs were not theoretical. They were learned through failure.

## Design Tensions We Actively Manage

Classroom Token Hub does not resolve classroom tensions. It contains them.

- Authentic simulation vs. emotional safety
- Student agency vs. exploitability
- Teacher authority vs. system transparency
- Real consequences vs. recoverability

## Architectural Philosophy

The architecture reflects the pedagogy.

- **Every state change is a recorded event.** Balances are not stored numbers that someone edits;
  they are the sum of ledger postings a student can read back.
- **Mutation has exactly one legal path.** A request handler does not write to the database. It
  calls a FEAT, which calls domain services, which commit. A handler that responds to a `GET` writes
  nothing at all.
- **Class isolation is enforced per query, not per module.** Every read and write touching
  seat-owned data is scoped by `class_id`. This is a discipline applied at each call site, and it is
  tested as such.
- **Identity is resolved once, at the boundary.** Routes do not assemble identity from request
  parameters; they ask for the canonical context and receive a frozen object.
- **Minimal hidden state builds student trust.** Reversibility and logging reinforce accountability.

The system avoids "magic." If something happens, it can be traced, explained, and — when appropriate — undone.

```
app/
├── __init__.py       # Application factory
├── models.py         # Explicit economic state
├── auth.py           # Access boundaries and decorators
├── feats/            # The only legal path to a state change
├── services/         # Domain logic, queries, and identity resolution
├── routes/           # Request handling, feature-scoped; no direct writes
└── utils/            # Shared constraints
```

Blueprints are scoped by **role** — teacher, student, operator, API — not by class. They separate
who is asking from what is being asked, and they are not the mechanism that keeps one class period's
data away from another. That mechanism is `class_id` scoping, and the distinction matters: a
blueprint boundary is structural and cannot leak, whereas a missing `class_id` filter is a one-line
omission inside a correct-looking query. The isolation that has to be defended is the one that has
already failed once.

Complexity is allowed. Ambiguity is not.

## Design Anti-Goals

(Features We Intentionally Do Not Build or Display)

The system is defined as much by what it refuses to show as by what it includes.
The following absences are deliberate.

### 1. No XP Bars, Streaks, or Level-Ups

We do not include:

- Experience points
- Participation streaks
- Leveling systems

Instead: earned wages, time-based pay, and explicit costs tied to decisions.

### 2. No Perfect Attendance Bonuses

We do not display:

- Attendance streak rewards
- Automatic bonuses for uninterrupted presence

Instead: insurance systems, partial pay, and recovery paths.

### 3. No Invisible Teacher Overrides

We do not allow:

- Silent balance edits
- Hidden forgiveness
- Unlogged interventions

Instead: explicit transactions, reversals, and audit trails. Teacher actions are visible to students because trust is the first step in making a system work.

### 4. No Behavior Scores or Compliance Metrics

We do not calculate:

- Engagement scores
- Effort ratings
- Participation grades

Instead: actions, outcomes, and room for human interpretation.

### 5. No AI Judgments of Student Intent

We do not show:

- Motivation predictions
- Effort classifications
- Character inferences

Instead: neutral logs that support teacher-led conversations.

### 6. No Unlimited Configuration Knobs

We do not expose:

- Arbitrary wage overrides
- Per-student economic exceptions
- Infinite economy sliders

Instead: guardrailed configuration that preserves coherence.

### 7. No Frictionless Shortcuts

We do not provide:

- Auto-approval flows
- One-click late forgiveness
- Bulk overrides without review

Instead: deliberate processes that require acknowledgment and choice.

### 8. No Leaderboards or Public Rankings

We do not display:

- Top earners
- Lowest balances
- Competitive rankings

Instead: private balances and individual decision paths.

### 9. No Neutral-System Claim

We do not claim:

- Value neutrality
- Bias-free incentives
- Objective fairness

Instead: visible assumptions that can be discussed and critiqued.

### 10. No Direct Student-to-System Support Tickets

We do not allow:

- Students to submit tickets directly
- Automated escalation from student complaints
- Appeals that bypass the teacher

The teacher is the first stop.

Instead:

- Students raise issues to teachers
- Teachers triage and submit tickets when appropriate
- Tickets represent vetted system issues, not raw frustration

This preserves teacher authority and protects student privacy.

## Security & Ethics

Security is a prerequisite, not an enhancement.

- Encrypted PII at rest
- Strong authentication for privileged accounts
- CSRF protection and input validation
- Bot mitigation
- Strict data minimization

The system assumes curiosity and welcomes students pushing system assumptions.

## Educational Use Only

Classroom Token Hub is licensed under the PolyForm Noncommercial License 1.0.0.

This project exists to serve classrooms, not markets.

---

# Part II — How It Got Here

Everything below is history. It describes decisions in the state they were made, and several of them
no longer describe the system. Each milestone carries a status:

| Status | Meaning |
|---|---|
| **Current** | The decision still holds and is reflected in Part I. |
| **Superseded** | The mechanism was replaced. The entry names the replacement. |
| **Evolved** | The decision holds in principle but its implementation has moved on. |

## From "Classroom Economy" to "Classroom Token Hub"

**Status: Current.**

The original project behaved like an activity layered on top of class routines.
The rename marked a shift toward a persistent, interconnected system — a hub rather than a gimmick.

## Class Identity: From Join Code to `class_id`

**Status: Superseded.** The join code is now an ingress alias only. `class_id` is canonical.

Early designs tied students too closely to teacher accounts or static rosters. This failed under real
classroom conditions, and the join code was promoted to be the system's source of truth for class
membership. At the time it delivered exactly what it was adopted for:

- Deterministic class membership
- Safe multi-class participation
- Strict data isolation
- Predictable recovery from errors

**What replaced it.** `class_id`, an opaque UUID and the primary key of the classes table, is the
canonical isolation key. The join code survives as a public alias with three legitimate uses — the
join and claim flow, the boundary lookup that resolves it into a `class_id`, and user-facing display.
Anywhere else it is a scoping bug. The canonical context object raises an `AttributeError` on any
attempt to read `join_code`, `teacher_id`, `block`, `section`, or `student_id` from it; this is
deliberate, and it is the mechanism that keeps the old model from creeping back in one query at a time.

**Why it changed.** A join code is a human-readable handle. It is typed by students, shared aloud,
printed on handouts, and occasionally changed. Binding the data model to it meant binding isolation
to a value that is both public and mutable. The decisive event was a same-teacher, multi-period data
leak: scoping that looked correct because it named the right teacher returned rows from every class
period that teacher ran. The failure was not that the join code was the wrong key so much as that
*a class needs an identity that nothing outside the system can influence.*

**What survived.** The principle did. "Class membership must be deterministic, isolated, and
recoverable" is still true and still shapes the data model — it simply hangs off a different key.
This is the clearest example in the project of a correct principle outliving the mechanism that first
expressed it, and it is why this document now separates the two.

## The v1 → v2 Identity Migration

**Status: Current.**

The identity model was rebuilt around four objects: a `User` is the global authentication principal;
a `Seat` is the class-local actor that every piece of activity keys off; an `IdentityProfile` holds
display-only identity; and a `ClassEconomy` is the isolation boundary. Credentials live on the user;
activity lives on the seat.

The v1 identity tables — among them `Student`, `Admin`, and the various block and membership join
tables — were removed outright rather than deprecated. A compatibility shim would have let both
models exist at once, and two identity models in one codebase is how the leak described above became
possible in the first place.

The practical consequence for anyone reading the code: a variable named `student` is a `Seat`, and
`Seat.user_id` is a `User` id and not a student id of any kind.

## Classroom Wage Index (CWI)

**Status: Current.**

Unregulated classroom economies inflate, collapse, or become meaningless.

CWI was introduced as a macro-level stabilizer to prevent runaway wages, distorted prices, and silent inequity.
The system learned to regulate itself.

## Insurance Systems

**Status: Evolved.**

Attendance is not purely a moral choice.
Life interferes.

Insurance was added when it became clear that punishment disguised as realism was neither accurate
nor educational. It has since grown from a single feature into a domain of its own, with policy
versioning, billing cycles, and claims — the governing contracts are the authority on its current
shape, not this entry.

## Visual Identity

**Status: Recorded elsewhere.**

The history of the visual system — role palettes and their predecessors, the move from image logos to
a live text wordmark, typography, and the public site's parallel identity — is a separate and
commit-cited account in `REF-DES-001`. The current visual contract is `SPEC-DES-001`. Neither is
summarized here, because a summary of a history is how a history goes stale.

---

## In Reflection

The system you are looking at today is conceptualized, designed, built, tested, maintained, and updated by a full-time high school teacher who lives by the motto *"I will just make it myself."*

Becoming an app developer was never part of the plan, but rather a side project that has "gone out of hand." Every feature and design you see today was a product of countless 500 errors, tears, students' incessant "Mr., it's not working!", and, of course, the satisfaction of seeing the puzzle pieces click into place.

This project would not have been possible without the best beta testers in the world: real students. Every impatient double click, negative deposit, "what if I do this instead?", and middle-of-the-night transaction exposed bugs and vulnerabilities that would have remained silent for now, but would fail loudly in production.

Classroom Token Hub was created to fill the void of a platform that simulates an economy more realistically than what is available on the market. It also functions as a classroom management tool that teaches students personal responsibility. Most of all, it respects data privacy and security like no other. The friction you experience when creating, claiming, and resetting accounts was intentional. Classroom Token Hub does not ask, "How can we defend ourselves?" It was designed to anticipate, "What if the bad actor gets in?"

Welcome to the Classroom Economy System, reimagined.

## Amendment

Increment the version and effective date when revising this document.

A revision MUST:

1. Keep Part I checkable. An architectural claim in Part I that no longer matches the code or the
   governing contract is a defect in this document, not a difference of opinion.
2. Move a superseded decision into Part II rather than deleting it, and name what replaced it.
   Deleting a reversal makes the project's progression look inevitable, which it was not.
3. Preserve the anti-goals as a list of refusals. An anti-goal that has been abandoned is removed
   with a note in Part II, never quietly softened.
4. Leave the normative hierarchy alone. This document explains; `INV-*`, `DOM-*`, `FEAT-*` and
   `SPEC-*` govern.

## Change Notes

**Version 2.0 (2026-09-20):**
- Split the document into Part I (present-tense truth) and Part II (history), and added the reading
  rule that governs the split.
- Corrected the architecture section. The previous file-tree omitted `feats/` and `services/` — the
  mutation and domain layers — and described blueprint isolation as mirroring classroom section
  isolation, which conflated role-scoped blueprints with `class_id` scoping.
- Rewrote "Join Code as Source of Truth" as a superseded milestone. It described the join code as the
  absolute source of truth; `class_id` has been canonical since the v2 identity work, and the
  canonical context raises on `join_code`.
- Added the v1 → v2 identity migration, which was the largest architectural event in the project and
  was absent from the document.
- Added an Amendment section and these change notes. Marked insurance as evolved, and pointed visual
  identity history at `REF-DES-001` rather than restating it.
