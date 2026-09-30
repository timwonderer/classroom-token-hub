# SPEC-ECON-001: Savings Interest Accrual and Disbursement Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-ECON-001    | 1.2     | 2026-09-30     | 1.1        | Normative       |

---

## 1. Purpose

This specification defines the authoritative behavior for savings interest accrual, compounding, scheduling, and payout within Classroom Token Hub (CTH).

The banking domain SHALL model interest as a deterministic, replayable financial process governed by canonical time boundaries and lawful ledger execution.

This specification distinguishes between:

1. Interest accrual
2. Compound participation
3. Interest payout/crediting
4. Savings eligibility
5. Settlement scheduling

These concepts are independent and MUST NOT be conflated into a single implicit operation.

---

## 2. Design Principles

### 2.1 Ledger Authority

The ledger is the sole authoritative financial source of truth.

Interest payouts MUST materialize as lawful ledger transactions through the Ledger Domain.

No derived balances, cached balances, projections, or UI-computed values SHALL possess financial authority.

---

### 2.2 Emergent Compounding

Compounding SHALL emerge from lawful balance participation rules rather than mutable “principal” state.

The system SHALL NOT maintain a mutable “principal” field for savings accounts.

Instead, future accrual eligibility SHALL derive from authoritative eligible balance computation.

---

### 2.3 Temporal Determinism

Interest accrual and payout SHALL operate against canonical class-time boundaries as defined by INV-ARC-015.

All scheduling decisions MUST resolve using:

- class_id
- authoritative class timezone
- canonical settlement windows

UTC calendar shortcuts are prohibited.

---

### 2.4 Separation of Concepts

The following concepts are independent:

| Concept | Purpose |
| --- | --- |
| Accrual Frequency | How often interest is earned |
| Compound Frequency | How often accrued interest joins future earning base |
| Payout Frequency | How often interest becomes posted ledger balance |
| Eligibility Rules | Which balances qualify |
| Settlement Schedule | When execution occurs |

Implementations MUST preserve these separations.

---

## 3. Definitions

### 3.1 Eligible Savings Balance

The balance eligible to earn interest during an accrual period.

Eligible balance SHALL derive from authoritative posted ledger state.

Eligible balance MUST account for:

- deposits
- withdrawals
- transfers
- reversals
- voids
- settlement timing

Historical deposit totals SHALL NOT independently confer future earning authority.

---

### 3.2 Accrued Interest

Interest earned but not yet paid out to the ledger.

Accrued interest MAY exist as:

- internal accounting state
- append-only accrual records
- derived deterministic calculations

Accrued interest SHALL NOT be treated as spendable balance until payout occurs.

---

### 3.3 Compound Participation

The rule governing whether accrued-but-unpaid interest contributes to future accrual calculations.

If accrued interest participates prior to payout:

- compounding frequency equals accrual frequency.

If accrued interest participates only after payout:

- compounding frequency equals payout capitalization frequency.

---

### 3.4 Interest Payout

A lawful ledger posting that credits accrued interest into the student’s savings balance.

Payout SHALL:

- occur through FEAT orchestration
- generate lawful audit lineage
- create authoritative ledger entries
- obey idempotency guarantees

---

## 4. Supported Interest Models

---

### 4.1 Simple Interest

Simple interest SHALL compute accrual solely from eligible principal balance.

Previously accrued or previously paid interest SHALL NOT participate in future accrual calculations.

Formula:

Where:

- P = eligible principal balance
- r = rate
- t = accrual duration

---

### 4.2 Compound Interest

Compound interest SHALL permit previously accrued or credited interest to participate in future accrual calculations according to compound frequency rules.

Formula:

Where:

- n = compound frequency periods per year

---

## 5. Accrual Rules

### 5.1 Accrual Frequency

The system SHALL support:

- daily
- weekly
- monthly

accrual frequencies.

Savings interest accrues daily by the daily balance method (§9.2, operator ruling
2026-09-30). Until an amendment defines what a weekly or monthly accrual frequency
would change under that method, a persisted `interest_accrual_frequency` SHALL NOT
alter accrual.

---

### 5.2 Daily Accrual Formula

Daily accrual SHALL compute as:

Equivalent formulas MAY exist for weekly/monthly accrual periods.

---

### 5.3 Precision

Internal accrual precision SHALL exceed displayed currency precision.

Implementations SHALL NOT discard sub-cent precision during accrual computation.

Rounding SHALL occur only at lawful payout boundaries unless explicitly configured otherwise.

Daily accruals within a payout window SHALL be summed at full precision and rounded to the
currency unit exactly once, when the window is credited (§9.2). Individual days SHALL NOT be
rounded.

---

## 6. Compound Frequency Rules

### 6.1 Supported Compound Frequencies

The system SHALL support:

- never (simple interest)
- daily
- weekly
- monthly

---

### 6.2 Compound Participation Boundary

Compound frequency determines when accrued interest joins future earning eligibility.

Example:

| Frequency | Behavior |
| --- | --- |
| Daily | Accrued interest participates next day |
| Weekly | Participation updates weekly |
| Monthly | Participation updates after monthly capitalization |
| Never | Accrued interest never participates |

Under the daily balance method (§9.2), compound frequency governs when interest accrued but
not yet credited in the current payout window joins the earning base:

- **Daily:** each day's earning base is that day's end-of-day posted savings balance plus all
  interest accrued so far in the window.
- **Weekly / Monthly:** interest accrued so far in the window joins the earning base at each
  class-local week start (Monday) or month start that falls inside the window, and stays in
  the base for the rest of the window.
- **Never (simple):** accrued interest never joins the earning base.

In every case, interest already credited to the ledger is part of the posted balance and
therefore of every later day's end-of-day balance.

---

## 7. Payout Rules

### 7.1 Payout Frequency

Payout frequency SHALL determine when accrued interest becomes:

- posted ledger balance
- visible student balance
- spendable funds

---

### 7.2 Supported Frequencies

The system SHALL support:

- daily
- weekly
- monthly

---

### 7.3 Payout Execution

Interest payout SHALL:

- execute through FEAT orchestration
- create lawful ledger transactions
- obey idempotency
- emit audit lineage
- respect class boundaries

Direct database writes are prohibited.

---

## 8. Scheduling

### 8.1 Canonical Settlement Execution

Settlement jobs SHALL execute through scheduled orchestration services.

Execution SHALL:

- iterate lawful class scope
- resolve canonical class time
- determine eligible payout windows
- execute deterministically

---

### 8.2 Idempotency

Each accrual and payout period SHALL possess deterministic idempotency boundaries.

Duplicate payout within the same settlement window is prohibited.

A payout window is one calendar period of the configured payout frequency in the class
timezone, as `SPEC-TIME-001` §11 defines it: a Monday-start week for weekly payout, a
calendar month for monthly payout. Each window SHALL be credited at most once per seat,
under an idempotency key that names the window (its class-local start date for a week, its
year and month for a month). A window already credited under any earlier key SHALL NOT be
credited again.

No day SHALL accrue for a seat twice. When the payout frequency changes, the first window under
the new frequency may overlap days already credited under the old one; that window keeps its own
key and accrues only on its days that end after the last credited window closed. Its earlier days
keep their place for compounding but accrue nothing. Days before the seat was claimed accrue
nothing in the same way.

---

## 9. Eligibility Rules

### 9.1 Withdrawal Participation

Withdrawals MUST reduce future eligible balance.

The system SHALL NOT continue paying interest on historical deposits no longer represented in authoritative balance state.

---

### 9.2 Pending Funds

Implementations MUST explicitly define whether pending balances participate in accrual.

The default authoritative rule SHALL be:

- posted balances only.

**Daily balance method** (operator ruling 2026-09-30; as in US Regulation DD, 12 CFR
1030.7): interest accrues daily on each day's end-of-day posted savings balance; accrued
interest is credited at the close of each payout window.

- A day is a class-local calendar day, `[00:00, 24:00)` in the class timezone
  (`SPEC-TIME-001`; `INV-ARC-015`). Its end-of-day posted balance is the sum of the seat's
  non-void savings effects whose posting time precedes the end of that day. An effect posted
  after a day ends first participates on the day it posts.
- A savings-interest credit participates from the close of the window it pays, whether or not it
  has settled, and not from its posting time. The balances of later windows, and so the amounts
  credited for them, do not depend on when the payout job ran or when settlement posted an
  earlier credit.
- Each day accrues `earning base × annual rate / 365` (`SPEC-ECON-003` §5.5), where the earning
  base is determined by compound frequency (§6.2). A non-positive earning base accrues nothing.
- The annual rate for a day is the rate in force at the end of that day: the `economic_engine` version with the greatest `effective_at` at or before that instant (`DOM-CLASS-003` §VII; 1.2). A version saved mid-window and dated for later earns nothing before its `effective_at`.
- The credited amount is the window's accrued interest, rounded once (§5.3).

Because end-of-day balances derive from posted ledger effects and their posting times,
every credited amount is reconstructible from the ledger (§12).

---

### 9.3 Voided Transactions

Voided transactions SHALL NOT contribute to:

- accrual
- compounding
- payout eligibility

---

## 10. Projection and Forecasting

Projection displays SHALL use the same mathematical rules as authoritative execution.

UI forecasts SHALL NOT diverge from runtime execution semantics.

Hardcoded APY defaults in projections are prohibited.

---

## 11. Architectural Prohibitions

The following are prohibited:

- GET-triggered financial mutation
- mutable principal authority fields
- direct DB transaction insertion outside FEAT orchestration
- UTC calendar shortcuts for payout boundaries
- historical-deposit-only eligibility logic
- projection formulas inconsistent with runtime execution
- hidden default APY behavior

---

## 12. Auditability

Interest execution SHALL be replayable and explainable.

The system MUST support reconstruction of:

- accrual basis
- compounding state
- payout eligibility
- payout timing
- resulting ledger transactions

from authoritative records.

---

## 13. Recommended Default Model

The recommended canonical banking model for CTH is:

| Property | Recommended Setting |
| --- | --- |
| Accrual Frequency | Daily |
| Compound Frequency | Monthly |
| Payout Frequency | Monthly |
| Eligibility Basis | Posted balance |
| Precision | High internal precision |
| Settlement Boundary | Canonical class midnight |

This mirrors common real-world savings account behavior while preserving deterministic replayability.

---

## 14. Operational Boundary Authority

Class Configuration is the sole authority over the class-local policy inputs that feed accrual rollover legality within CTH.

This authority derives from `DOM-CLASS-001` through `DOM-CLASS-002` and `DOM-CLASS-003`. `FEAT-ECON-001` executes the behavior but does not own the authority.

### 14.1 Boundary Determination

When the scheduled accrual settlement job fires, the accrual service SHALL:

1. Resolve the canonical class-time boundary using `class_id` and class timezone (per INV-ARC-015).
2. Determine whether the accrual window has closed since the last settled period.
3. Execute interest payout through `FEAT-CORE-000`-compliant FEAT orchestration.
4. Read the banking terms from the `economic_engine` version in force (`DOM-CLASS-003` §VII). A banking change is a version with its own `effective_at`; the accrual service never applies or activates one.

Only payout windows that have closed SHALL be credited. Each window closed since the last
credited window SHALL be credited in order, from its end-of-day balances reconstructed from
the ledger (§9.2, §12), so the amount does not depend on when the job runs or on balances
after the window closed.

### 14.2 Banking Policy Changes

*(1.2, operator ruling 2026-09-30: the transition-activation protocol that stood here is withdrawn with the retired `policy_versions` / `policy_transitions` tables.)*

The accrual service MUST NOT:

- Write or rewrite an `economic_engine` version
- Treat a version whose `effective_at` is still ahead as in force
- Determine supersession legality
- Change policy inside a GET handler or read path

Policy lineage is the `economic_engine` table itself (`DOM-CLASS-003` §V). Class-level policy inputs remain owned by `DOM-CLASS-001` through `DOM-CLASS-002`.

---

## 15. Amendment

Revisions to this document SHALL:

1. Increment the version number.
2. Update the Effective Date.
3. Maintain consistency with `INV-CORE-000` and `INV-ARC-015`.
4. Maintain consistency with `DOM-CLASS-001` and `DOM-CLASS-002` for class-level policy inputs, `DOM-CLASS-003` for policy lineage, and the owning operational domain together with `FEAT-ECON-001` for operational boundary activation.
5. Preserve deterministic, replayable accrual semantics.

### Revision history

- **1.2 (2026-09-30)** — Operator ruling 2026-09-30 retires `policy_versions` / `policy_transitions`. §14.1 item 4 reads banking terms from the `economic_engine` version in force; §14.2's transition-activation protocol is withdrawn; §9.2's rate for a day is the version in force by `effective_at`, so a rate dated for later never accrues early.
- **1.1 (2026-09-30)** — Operator ruling 2026-09-30 adopts the daily balance method (12 CFR
  1030.7). §9.2 states it: interest accrues daily on each class-local day's end-of-day posted
  savings balance and is credited at the close of each payout window. §5.1 fixes accrual as daily.
  §5.3 rounds once, at crediting. §6.2 defines how compound frequency applies within a window.
  §8.2 defines the payout window and its key, and says that no day accrues twice when the
  payout frequency changes. §9.2 says a credit participates from its window's close.
  §14.1 credits only closed windows, replayed from the ledger.
- **1.0 (2026-07-25)** — Initial specification.
