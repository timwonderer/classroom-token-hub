# FEAT-CLASS-003: Insurance Policy Management

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| FEAT-CLASS-003 | 0.4 | 2026-10-28 | 0.3 | Normative |

## I. Purpose

Define the canonical class-configuration workflow for class-level insurance enablement and economic settings.

This FEAT governs:

- toggling the insurance capability at the class level;
- maintaining class-level economic settings that insurance workflows depend on;
- producing student-visible availability notices when insurance is enabled or disabled;
- delegating insurance policy definition changes to `FEAT-POL-001`.

This FEAT owns orchestration only.

It SHALL NOT mutate insurance policy definitions, entitlement records, obligation records, or ledger records directly.

## II. Authority

This FEAT is authorized by:

- `DOM-CLASS-001_CLASS_CONFIGURATION_DOMAIN.md`
- `INV-CORE-000_CORE_INVARIANTS.md`
- `INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `INV-ARC-015_TEMPORAL_MODEL_AND_BOUNDARY_ENFORCEMENT.md`
- `INV-ARC-016_LAWFUL_EXISTENCE_AND_AUDIT_LINEAGE.md`
- `INV-ARC-021_CROSS_DOMAIN_REFERENCE_AND_COORDINATION.md`

This FEAT is the sole lawful orchestrator for class-side insurance capability and economics changes.

## III. Required Context

Required canonical context:

- `user_id`
- `class_id`
- `seat_id`
- `actor_role = teacher`

The teacher seat SHALL be lawful for the class boundary.

This FEAT SHALL NOT reconstruct authority from labels, block names, join codes, or route-local state.

## IV. Scope and Model

Class-level insurance configuration is class-scoped enablement and economics.

The canonical class configuration SHALL capture, at minimum:

- class-level insurance enablement;
- class-level economics that insurance workflows depend on;
- teacher-facing notice state for insurance availability;
- any class-scoped settings that influence policy orchestration but are not policy definitions themselves.

This FEAT SHALL NOT add foreign keys from class configuration into entitlement, obligation, or ledger tables.

## V. Insurance Enablement

Insurance enablement SHALL:

1. toggle the insurance capability at the class level;
2. preserve existing downstream facts;
3. control whether insurance-related Policy definitions are reachable from the class UI;
4. emit teacher-visible notices about availability changes.

## VI. Economic Settings

Class-level economic settings SHALL remain under Class Configuration.

These settings MAY be consulted by insurance or rent policy workflows, but they SHALL NOT rewrite Policy definitions.

## VII. Delegation

This FEAT performs the immutable definition write, availability projection, and
retirement by invoking the **POL definition commands**
(`insurance_definition_service.create_insurance_definition` / `set_availability`)
inside its own single FEAT context. It does NOT execute a separate FEAT — a FEAT
never executes another FEAT; it composes domain commands (FEAT-CORE-000 §V.1,
INV-ARC-000 §VIII.2, INV-ARC-021 §V.2).

## VIII. Tier Groups

A **tier group** is a teacher-named set of mutually-exclusive insurance policies a
student chooses one of (e.g. a "Paycheck Protection" line offered as Basic / Mid /
Premium). A group is a class-scoped `insurance_tier_groups` identity: membership is the canonical `tier_group_id` carried
on each `insurance_policies` row, class-scoped.

### 1. Ranks

Grouped tiers occupy the three ordinal ranks `tier_level ∈ {1, 2, 3}` = basic / mid /
premium. An ungrouped ("single") offering carries no `tier_group_id` (and no group
semantics attach to a bare `tier_level`). A grouped policy MUST carry a rank in
{1,2,3}; a missing or out-of-range rank fails closed.

### 2. Rank uniqueness and the three-tier cap

Within one group, at most one **available (`IN_USE`)** policy may occupy each rank,
so a group holds **at most three** active tiers. Because definitions are immutable
(an edit mints a new `policy_uuid`, records the old one as its `supersedes_policy_uuid`,
and retires the old — DOM-POL-001, DOM-POL-001A §D), the constraint
is over `IN_USE` rows only: retired/hidden versions never occupy a slot, and
re-adding a rank after retiring its prior tier is lawful.

Primary enforcement is this FEAT's create-time guard (reject a duplicate `IN_USE`
rank in the group, or a fourth active tier). A partial unique index
`(class_id, tier_group_id, tier_level) WHERE availability_state = 'IN_USE' AND
tier_group_id IS NOT NULL` is the concurrent-create backstop.

### 3. Mutual exclusion at purchase

A seat holds at most one active insurance coverage per `tier_group_id`. This extends
FEAT-OBL-004's single-active-coverage invariant from per-`policy_uuid` to
per-group: purchasing a policy whose group the seat already holds active coverage
in fails closed. Enforcement lives in FEAT-OBL-004 (the purchase authority), not here.

### 4. Rank → economic envelope (advisory)

The Economic Engine (SPEC-ECON-003 §4.5.8) provides per-tier preset envelopes
(reimbursement %, payout multiple, claims/week, window, premium band position). These
are ADVISORY presets a teacher may accept or override; they are not enforced by this
FEAT beyond the hard bounds and per-type structural CHECKs. Bundle/multi-tier discount
is out of scope for this revision.

## IX. Guarantees

This FEAT guarantees:

- class-level insurance enablement is explicit;
- class-level economic settings remain under Class Configuration;
- Policy definitions are not mutated here (a new immutable row per lawful change);
- a tier group holds at most three active tiers, one per rank;
- downstream entitlement, obligation, and ledger facts are not rewritten by this FEAT.
- an edit, and putting a hidden policy back on sale, record the replaced version as
  `supersedes_policy_uuid` on the new row; existing holders move to it only through a new
  entitlement at their coverage boundary (`DOM-STORE-001` §VIII.E.1), never by a change to
  their existing entitlement.

**0.2 (2026-10-14)** records the successor link on edit and reactivation (owner ruling
2026-10-14).
## Configuration portability and canonical insurance groups

Owner ruling 2026-10-25 incorporates SPEC-CLASS-001. Policies exposes pure portable
projections and shared definition commands to FEAT-CLASS-009/010 without coordinating
other domains. FEAT-POL-001 describes the definition contract; it is not an executor
that other FEATs call. Existing exclusive-writer wording does not forbid these declared
FEATs from composing the same domain commands.

Hall-pass import replaces the complete definition with a new row and retires the old
one; selected destinations are not merged. Store/insurance imports create independent
products and groups with fresh identifiers, never predecessor links to destination
products. Rent-linked products export as ordinary products; their source rent-product
links are excluded (owner ruling 2026-10-28), so an imported product is not rent-linked
until the teacher links it in the destination Store. One not directly purchasable is
imported HIDDEN with its terms unchanged (SPEC-STORE-001). Destination
rent-product links survive replacement of the other rent settings.

`insurance_policies.tier_group_id` is a nullable canonical UUID scoped by class_id.
`tier_group` and `tier_name` are presentation only. Membership and unique active ranks
use `(class_id, tier_group_id, tier_level)`, never labels. New groups always receive a
fresh identifier, including same-name groups. Editing a member preserves group identity.

The one-time successor migration groups the existing available definitions by their
exact stored class/label membership (the pre-cutover contract), creates new UUID groups,
publishes identical-term successors and retires predecessors from new selection. Old
definition payloads and operational facts are not rewritten. Existing coverage migrates
through normal succession at its boundary. Purchase exclusion resolves predecessor
coverage through explicit successor links to canonical group identity; it never falls
back to labels. The migration must refuse ambiguous live coverage without a successor
path rather than invent membership. This is a forward-only cutover, not a dual writer.
