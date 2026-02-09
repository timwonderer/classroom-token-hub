# Classroom Token Hub — Design Principles, Philosophy, and Memory

## Document Purpose

This document preserves the design philosophy, guiding principles, and formative lessons of Classroom Token Hub.  
*It is not a changelog. It is a record of decisions that survived real classrooms.*

For chronological releases and versioned changes, see CHANGELOG.md￼.

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

Every major feature exists because one of these tensions was mishandled once—and deliberately redesigned.

## Design Evolution & Key Milestones

The system hardened over time through specific turning points.

### From “Classroom Economy” to “Classroom Token Hub”

The original project behaved like an activity layered on top of class routines.  
The rename marked a shift toward a persistent, interconnected system—a hub rather than a gimmick.

### Join Code as Source of Truth

Early designs tied students too closely to teacher accounts or static rosters.  
This failed under real classroom conditions.

The join code became the absolute source of truth, enabling:

- Deterministic class membership
- Safe multi-class participation
- Strict data isolation
- Predictable recovery from errors

This decision reshaped the entire data model.

### Classroom Wage Index (CWI)

Unregulated classroom economies inflate, collapse, or become meaningless.

CWI was introduced as a macro-level stabilizer to prevent runaway wages, distorted prices, and silent inequity.  
The system learned to regulate itself.

### Insurance Systems

Attendance is not purely a moral choice.  
Life interferes.

Insurance was added when it became clear that punishment disguised as realism was neither accurate nor educational.


## Architectural Philosophy

The architecture reflects the pedagogy.

- Blueprint isolation mirrors classroom section isolation
- Explicit models enable auditable economic rules
- Minimal hidden state builds student trust
- Reversibility and logging reinforce accountability

The system avoids “magic.” If something happens, it can be traced, explained, and—when appropriate—undone.

```
app/
├── __init__.py          # Application factory
├── models.py            # Explicit economic state
├── auth.py              # Access boundaries
├── routes/              # Feature-scoped systems
└── utils/               # Shared constraints
```

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

Instead: explicit transactions, reversals, and audit trails. Teacher actions is visible to students because trust is the first step in making a system work.

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

The system assumes curiosity and welcomes student pushing system assumptions.

## Educational Use Only

Classroom Token Hub is licensed under the PolyForm Noncommercial License 1.0.0.

This project exists to serve classrooms, not markets.

## In Reflection

The system you are looking at today is conceptualized, designed, built, tested, maintained, and updated by a full-time high school teacher who lives by the motto *“I will just make it myself.”*

Becoming an app developer was never part of the plan, but rather a side project that has “gone out of hand.” Every feature and design you see today was a product of countless 500 errors, tears, students’ incessant “Mr., it’s not working!”, and, of course, the satisfaction of seeing the puzzle pieces click into place.

This project would not have been possible without the best beta testers in the world: real students. Every impatient double click, negative deposit, “what if I do this instead?”, and middle-of-the-night transaction exposed bugs and vulnerabilities that would have remained silent for now, but would fail loudly in production.

Classroom Token Hub was created to fill the void of a platform that simulates an economy more realistically than what is available on the market. It also functions as a classroom management tool that teaches students personal responsibility. Most of all, it respects data privacy and security like no other. The friction you experience when creating, claiming, and resetting accounts was intentional. Classroom Token Hub does not ask, “How can we defend ourselves?” It was designed to anticipate, “What if the bad actor gets in?”

Welcome to the Classroom Economy System, reimagined.
