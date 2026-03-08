# DOM-ECON-002: Economy Specification

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| DOM-ECON-002     | 1.1     | 2026-03-08     | DOM-ECON-002 v1.0 | Constitutional |

## I. Purpose

This document defines the constitutional economy model for CWI-derived pricing, policy-mode ratio bands, insurance proportionality, and solvency validation used by Classroom Token Hub.

## II. Scope

This specification applies to all economy-related calculations, recommendations, validation workflows, teacher-facing balance tooling, and automated configuration helpers that evaluate or propose rent, utilities, store prices, insurance settings, or fines.

## III. Authority Level

Constitutional (DOM Tier). This document is subordinate to `INV-CORE-000_Core_Invariants.md` and `DOM-CORE-000_Domain_Foundation.md`. No FEAT, SOP, UI workflow, or informative guide may override the ratio bands or solvency rules defined here.

## IV. Dependencies

- `INV-CORE-000_Core_Invariants.md`
- `DOM-CORE-000_Domain_Foundation.md`

## V. Core Reference Variable

All monetary outputs shall derive from the Classroom Wage Index (`CWI`).

### 1. CWI Definition

```
CWI = expected weekly pay for a student with perfect attendance
```

All economy validators, recommendations, and previews shall compute or retrieve CWI before evaluating any cost structure.

### 2. Normalization Rule

CWI is weekly. Any monthly, biweekly, daily, semester, yearly, or custom configuration shall be normalized to a weekly equivalent before ratio comparison.

## VI. Policy Mode Framework

The economy engine shall support exactly three internal policy modes:

1. `tight`
2. `default`
3. `comfortable`

Policy mode shall modify recommendation bands and validation targets. Policy mode shall not rewrite historical transactions, frozen insurance snapshots, or prior ledger entries.

### 1. Default Policy Ratios

The default policy shall use the following weekly-CWI bands:

- Rent: `60%` to `75%` of weekly CWI
- Utilities / fixed recurring fees: `5%` to `10%` of weekly CWI
- Store standard tier: `2%` to `5%` of weekly CWI
- Insurance premium: `5%` to `12%` of weekly CWI
- Fines: `5%` to `15%` of weekly CWI
- Minimum weekly savings target: `10%` of weekly CWI

### 2. Tight Policy Ratios

The tight policy shall use the following weekly-CWI bands:

- Rent: `70%` to `80%` of weekly CWI
- Utilities / fixed recurring fees: `7%` to `12%` of weekly CWI
- Store standard tier: `2%` to `4%` of weekly CWI
- Insurance premium: `6%` to `14%` of weekly CWI
- Fines: `7%` to `18%` of weekly CWI
- Minimum weekly savings target: `5%` of weekly CWI

### 3. Comfortable Policy Ratios

The comfortable policy shall use the following weekly-CWI bands:

- Rent: `50%` to `65%` of weekly CWI
- Utilities / fixed recurring fees: `4%` to `8%` of weekly CWI
- Store standard tier: `3%` to `6%` of weekly CWI
- Insurance premium: `4%` to `10%` of weekly CWI
- Fines: `4%` to `12%` of weekly CWI
- Minimum weekly savings target: `15%` of weekly CWI

## VII. Category Ratio Bands

### 1. Rent

Rent shall be validated against the active policy mode's rent band using weekly normalization. Monthly-equivalent recommendations shall be derived by multiplying the weekly burden target by average weeks per month.

### 2. Utilities and Fixed Recurring Fees

Utilities guidance shall use the active policy mode's utilities band. If a surface presents utilities, property taxes, or equivalent fixed recurring costs, it shall validate them against the same weekly band.

### 3. Store Pricing Tiers

All store tier recommendations shall remain CWI-relative and policy-aware.

#### a. Default Store Tiers

- Basic: `1%` to `3%` of CWI
- Standard: `2%` to `5%` of CWI
- Premium: `5%` to `15%` of CWI
- Luxury: `15%` to `30%` of CWI

#### b. Tight Store Tiers

- Basic: `1%` to `3%` of CWI
- Standard: `2%` to `4%` of CWI
- Premium: `4%` to `12%` of CWI
- Luxury: `12%` to `24%` of CWI

#### c. Comfortable Store Tiers

- Basic: `2%` to `4%` of CWI
- Standard: `3%` to `6%` of CWI
- Premium: `6%` to `18%` of CWI
- Luxury: `18%` to `35%` of CWI

### 4. Fines

Fine recommendations shall use the active policy mode's fine band. Fine validation shall remain proportional and shall warn when a fine is so low it loses instructional meaning or so high it materially threatens solvency.

## VIII. Insurance Structure

Insurance guidance shall remain bounded, policy-aware, and premium-proportional.

### 1. Premium Bands

Insurance premium validation shall use the active policy mode's premium band defined in Section VI.

### 2. Coverage Multipliers

Maximum claim amount shall be evaluated against the configured premium using the following policy-specific multiplier bands.

#### a. Default

- Minimum: `3.0x` premium
- Maximum: `5.0x` premium
- Recommended center: `4.0x` premium

#### b. Tight

- Minimum: `2.5x` premium
- Maximum: `4.0x` premium
- Recommended center: `3.25x` premium

#### c. Comfortable

- Minimum: `4.0x` premium
- Maximum: `6.0x` premium
- Recommended center: `5.0x` premium

### 3. Period Cap Multipliers

Maximum payout per period shall be evaluated against the configured premium using the following policy-specific multiplier bands.

#### a. Default

- Minimum: `6.0x` premium
- Maximum: `10.0x` premium
- Recommended center: `8.0x` premium

#### b. Tight

- Minimum: `5.0x` premium
- Maximum: `8.0x` premium
- Recommended center: `6.5x` premium

#### c. Comfortable

- Minimum: `8.0x` premium
- Maximum: `12.0x` premium
- Recommended center: `10.0x` premium

### 4. Waiting Period Bands

Waiting period guidance shall be policy-aware.

- Default: `7` days
- Tight: `10` to `14` days
- Comfortable: `3` to `7` days

### 5. Frozen Enrollment Invariant

Policy-mode changes shall not mutate frozen policy terms already attached to an existing student enrollment. Policy mode shall affect recommendations, future policy edits, and future enrollments only.

## IX. Solvency Constraints

### 1. Budget Survival Test

A student with perfect attendance shall remain able to save at least the active policy mode's minimum weekly savings target after normalized fixed costs and conservative store spending.

```
weekly_savings = CWI - weekly_rent - weekly_insurance - average_store_cost
weekly_savings >= policy_mode_minimum_savings_ratio * CWI
```

### 2. Catastrophe Rule

A student experiencing two fines, an uninsured loss event, and a discretionary store purchase shall not be driven below zero for more than one cycle under system-recommended settings.

## X. Output Requirements

All automated recommendations and validation outputs shall:

1. identify the active policy mode
2. identify the CWI used
3. identify the normalized ratio band applied
4. identify the resulting recommendation range
5. surface warnings when configuration falls outside the active band

## XI. Non-Negotiable Rules

1. All monetary values shall remain CWI-relative.
2. Policy mode shall modify recommendation targets, not history.
3. Insurance proportionality shall remain premium-relative.
4. Rebalancing workflows shall surface impacts before application.
5. Economy tooling shall preserve student solvency under the active policy profile.

## XII. Amendment

Revisions to this document shall:

1. increment the version number
2. update the Effective Date
3. maintain consistency with `DOM-CORE-000_Domain_Foundation.md`
4. preserve compatibility with higher-authority invariant documents
