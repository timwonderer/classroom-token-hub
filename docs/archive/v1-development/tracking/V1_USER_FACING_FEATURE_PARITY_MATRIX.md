# V1 User-Facing Feature Parity Matrix

**Status:** Active tracking  
**Last Updated:** 2026-04-19  
**Purpose:** Track whether V2 preserves the user-visible feature surface that V1 users already know exists, independent of internal code reorganization.

This is a feature-surface audit, not a code-port audit.

## Status Key

- `same` — user-facing feature exists in V2 in substantially the same place and shape
- `moved` — feature exists in V2 but location or navigation changed
- `changed` — feature exists but workflow or expectations differ materially
- `missing` — feature expected from V1 is not currently present/discoverable in V2
- `deferred` — intentionally postponed and not required for the current lane
- `unknown` — not yet audited

## Teacher Surface

| Actor | V1 Feature | V1 Expected Location | V2 Location / Surface | Status | Notes |
|---|---|---|---|---|---|
| Teacher | Dashboard | Teacher nav / home | Teacher dashboard | same | Core teacher landing surface still exists |
| Teacher | Classroom / roster management | Teacher nav | Teacher classroom flows | unknown | Audit exact entry points and naming |
| Teacher | Economy management | Teacher nav | Teacher economy flows | same | Broad category exists, per-page parity still needs verification |
| Teacher | Bills / rent / insurance / banking | Teacher nav | Teacher billing/economy/settings flows | changed | Needs exact mapping by page and selected class context |
| Teacher | Store management | Teacher nav economy area | Teacher store routes | same | Discoverability under redesigned nav still needs confirmation |
| Teacher | Payroll / work & pay controls | Teacher nav economy area | Teacher payroll routes | same | Needs page-by-page parity check |
| Teacher | Feature toggles / settings | Teacher nav settings | Settings + feature toggle page | changed | V2 rule is class-scoped, backend authoritative |
| Teacher | Support / tickets | Teacher nav | Support / help routes | same | Should remain class-scoped in V2 |
| Teacher | Insurance claim processing | Teacher nav / insurance area | Admin insurance claim routes | same | Already routed through FEAT + access boundary |
| Teacher | Class switching | Teacher shell/nav | Global class switcher | moved | Must be backend-owned session context |

## Student Surface

| Actor | V1 Feature | V1 Expected Location | V2 Location / Surface | Status | Notes |
|---|---|---|---|---|---|
| Student | Dashboard | Student nav / home | Student dashboard | same | Already under access boundary |
| Student | Accounts / banking | Student nav | Student accounts/banking routes | same | Future ledger rewrite is separate from surface parity |
| Student | Store | Student nav | Student store | same | Feature gating must be backend-owned |
| Student | Work & Pay | Student nav | Student payroll / attendance area | same | Needs nav parity audit under feature flags |
| Student | Bills | Student nav | Rent / insurance / bills area | changed | Needs exact V2 information architecture mapping |
| Student | Help & Support | Student nav | Help & Support | same | Route still present |
| Student | Insurance marketplace | Student nav / bills area | Student insurance routes | same | Claim filing now behind FEAT |
| Student | Transfers | Student banking area | Student transfer route | same | Needs discoverability confirmation in redesigned nav |
| Student | Class switching | Student nav footer / class control | Global class switcher | moved | Backend-owned context switch, student-visible control remains |
| Student | Add class / claim seat | Student surface | Claim/setup and join-code flows | changed | Audit exact discoverability after nav redesign |

## Cross-Cutting Navigation / Discoverability

| Topic | Expectation | Status | Notes |
|---|---|---|---|
| Teacher nav stability | Nav links remain stable even when a feature is disabled for selected class | agreed | Backend should return stable teacher nav shape |
| Student nav gating | Disabled features are hidden from student nav | agreed | Backend must prune nav model; frontend only renders |
| Teacher disabled feature access | Teacher sees disabled-state page, not silent redirect | agreed | Must direct teacher to class switcher or feature toggle page only |
| Student disabled feature access | Student receives `404` for disabled feature direct access | agreed | Must not reveal feature existence |
| Class switch authority | Class switcher is the only class-context control | agreed | Pages must not silently switch class |
| Feature toggle authority | Feature toggle page is the only feature enable/disable control | agreed | Feature pages must enforce, never mutate |

## Next Audit Pass

1. Enumerate actual teacher nav destinations in the redesigned V2 shell.
2. Enumerate actual student nav destinations in the redesigned V2 shell.
3. Map each destination to the corresponding V1 user expectation.
4. Reclassify all `unknown` rows to `same`, `moved`, `changed`, `missing`, or `deferred`.
5. Record intentional removals explicitly so they are not mistaken for omissions.
