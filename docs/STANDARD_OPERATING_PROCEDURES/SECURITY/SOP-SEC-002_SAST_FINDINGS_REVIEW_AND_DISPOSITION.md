# SOP-SEC-002: SAST Findings Review and Disposition

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-SEC-002 | 1.0 | 2026-10-11 | — | Normative procedure (Tier 2) |

## I. Purpose

This procedure governs how static-analysis (SAST) findings on this repository are
configured to gate merges, how an individual finding is disposed of (fixed, deferred,
or recorded false-positive/mitigated), and how the full backlog — not just a given
PR's diff — gets a scheduled, recurring look. It exists because a SAST tool whose
merge-time check only diffs changed lines against its own findings can report green
indefinitely while a real, reachable finding sits untouched in its dashboard; this is
exactly how both sinks in `docs/ops/audits/INCIDENT_2026-10-11_SEC-SAST-GAP-001.md`
survived in production for up to ~11 months. That record's §5 follow-ups are the
direct origin of this SOP; see it for the incident this procedure answers.

## II. Scope

This SOP applies to anyone who configures repository code-scanning settings, reviews
or disposes of a SAST finding, authors or reviews a pull request flagged by a SAST
tool, or performs the recurring backlog review in §V.4. It does not define
application security behavior (`SPEC-SEC-001` and the owning domain `DOM-*`/`FEAT-*`
contracts do that) and does not replace manual security review, threat modeling, or
the incident-response procedure in `SOP-SEC-001` §V.4.

## III. Authority Level

Normative human procedure (Tier 2), subordinate to `INV-CORE-*` and `INV-ARC-*`. Under
`SOP-CORE-000`, this SOP binds people and the CI/branch-protection configuration
around them; it cannot establish runtime authority and does not override an `INV-*`,
`DOM-*`, or `FEAT-*` contract. A SAST tool's silence on a pattern is never evidence
that the pattern is safe — only a reviewed disposition under §V.2 is.

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/CORE/INV-CORE-001_CAPABILITY_BASED_ARCHITECTURE_AND_AUTHORITY_MODEL.md`
- `docs/SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SOP-CORE-000_Sop_Foundation.md`
- `docs/ops/audits/INCIDENT_2026-10-11_SEC-SAST-GAP-001.md`
- `docs/STANDARD_OPERATING_PROCEDURES/TESTING/SOP-TEST-003_Test_Creation.md` §IX.A (mutation-proof requirement for structural guards)

## V. Operating Controls

### V.1 Merge-gate configuration and its rationale

- CodeQL runs on the `security-extended` query suite (not the narrower default
  setup), configured in Settings → Code security, not as a committed workflow file.
- `main`'s branch ruleset (id `10357616`) carries a `code_scanning` rule with
  `security_alerts_threshold: high_or_higher`. GitHub's `code_scanning` rule has two
  independent threshold fields: `security_alerts_threshold`
  (`none`/`critical`/`high_or_higher`/`medium_or_higher`/`all`, by severity) and
  `alerts_threshold` (`none`/`errors`/`errors_and_warnings`/`all`, by code-scanning
  alert severity: Error, Warning, or Note). This SOP's threshold rationale concerns
  `security_alerts_threshold` only. **Rationale:** `high_or_higher` blocks merge on a
  new Critical or High finding the PR's diff introduces, while leaving Medium/Low/Note
  findings to flow through the per-alert triage in §V.2 rather than blocking every PR
  on a tool with a known false-positive rate. This was chosen deliberately over
  `critical` alone (which would let a new High-severity finding merge unblocked) and
  over `none`/no rule (which reproduces the original gap). Missing or in-progress
  CodeQL analysis on the PR head blocks merge separately from either threshold field,
  and this was experimentally verified fail-closed (confirmed 2026-10-11 against a
  draft PR). A rule that only scopes to alerts the PR's diff introduces is a
  deliberate, narrower scope than the whole-repository backlog; §V.4 exists because of
  that gap.
- **What the ruleset does not do:** it has no required status check for this
  repository's own test suite. A structural guard test (such as
  `tests/guards/unsafe_jinja_filter_markup.py`'s `test_no_unsafe_jinja_markup.py`)
  can fail red in CI without blocking a merge on its own. Closing that gap is a
  separate, larger change (adding a required status check to the ruleset) and is not
  in scope for this SOP; until it lands, a reviewer who sees red CI on a security
  guard test MUST treat it as a merge blocker by judgment, not rely on the ruleset to
  enforce it.
- A removed or disabled scanner (Aikido was removed 2026-10-11; see the incident
  record §4) MUST NOT be replaced by a tool whose merge-time check is diff-scoped
  only, unless paired with a recurring full-backlog review under §V.4. A green
  diff-scoped check is a weaker signal than no check, because it reads as "nothing
  found" when it means "nothing new in this diff."

### V.2 Per-alert disposition (evidence-based, never blanket)

Every open SAST finding gets exactly one of three dispositions, each requiring
written evidence, not a bulk action:

1. **Fixed.** A code change closes the finding. Record the fix's commit/PR.
2. **False positive / mitigated, documented.** The finding is not exploitable as
   reported, or an existing control already mitigates it. Required evidence,
   recorded in a dated triage document under `docs/ops/audits/`:
   - The query ID and, when the rule models a taint flow, the specific source/sink pair;
     for a rule that does not model a taint flow, the alert location and evidence
     addressing that rule's actual condition instead.
   - A traced path (or explicit absence of one) from a real caller or input to the
     flagged code — not just "looks fine on read."
   - Trust boundary classification: public unauthenticated request, authenticated
     request, CI-triggered (and whether `pull_request_target` is involved — a
     privilege-escalation-relevant distinction), scheduled/operational, or
     local-maintainer-only.
   - Existing defenses that make the path non-exploitable (auth gate, allowlist,
     fixed host, sanitizer call, etc.), named specifically, not asserted generally.
   - **MUST NOT** be dismissed on GitHub's side (via the code-scanning alerts API)
     without this evidence already written down. Writing the evidence down and
     flagging it as reviewed is a valid interim state when API dismissal access is
     unavailable; the dismissal itself should follow once access exists, referencing
     the same evidence.
3. **Real, deferred.** The finding is genuine and reachable but not fixed in the
   current change for a stated reason (credential/production risk in the affected
   workflow, scope boundary of the current PR, etc.). Record the reason and track it
   as a follow-up (an issue, or a named future PR) — "deferred" without a tracked
   follow-up is not a valid disposition.

**Never blanket-dismiss.** A classification pass across many findings (e.g. a suite
switch that surfaces dozens of alerts at once) MUST classify each one individually
per the three dispositions above, grouped by query ID and trust boundary for
efficiency, but never dismissed as a group without each member meeting its own
evidence bar. This was an explicit correction during the 2026-10-11 triage: "fix the
actionable findings without indiscriminately dismissing everything else."

Static guard tests added to close a gap a SAST tool's query set does not cover (the
pattern in `tests/guards/unsafe_jinja_filter_markup.py`) follow the same
only-shrinks-baseline discipline as `migrations/lint_baseline.txt`: a reviewed,
pre-existing occurrence may be recorded in the guard's baseline file to avoid
re-litigating it, but the baseline file MUST NOT be used to silence a newly
introduced occurrence, and every guard MUST carry a mutation proof per
`SOP-TEST-003` §IX.A before it is trusted.

### V.3 Query-coverage gaps

When a vulnerability class ships and reaches production without either SAST tool
flagging it, confirm whether the gap is a **routing failure** (the tool found it but
the finding never reached a merge-blocking gate — the Aikido diff-scope failure) or a
**coverage gap** (no rule models the taint flow at all — CodeQL's missing
`Markup()`/`|safe` query). The two have different fixes:

- A routing failure is fixed by gating configuration (§V.1), not by code change.
- A coverage gap requires either a custom query for that specific taint shape, or,
  where a custom query is impractical, a deterministic repository guard test proven
  against a synthetic near-miss per `SOP-TEST-003` §IX.A. A changelog note or a
  comment asserting the pattern "is now covered" without a guard or query that
  reports a synthetic violation is not sufficient — `SOP-TEST-003` §IX.A documents a
  guard in this repository that passed while failing to guard, for exactly this
  reason.
- Confirm a rule that *should* already cover a related pattern (e.g. `js/xss-through-dom`
  for client-side `innerHTML` sinks) remains enabled rather than assuming it does,
  since the same incident found that rule class present but missing one specific
  instance for reasons distinct from the Jinja-side gap.

### V.4 Recurring backlog review (not purely PR-triggered)

A SAST tool's full open-alert dashboard gets a scheduled review independent of any
PR, so a pre-existing finding in code a PR doesn't touch has a point where someone
looks at it rather than sitting indefinitely:

- **Owner:** the repository owner (or, where delegated, the named security
  maintainer on record) is accountable for this review running on schedule. If that
  person is unavailable when a review falls due, they MUST name a delegate before the
  due date; an unassigned or missed review is itself a finding, recorded the same way
  as a missed disposition.
- **Cadence:** at minimum, following every SAST tool's query-suite or rule-pack
  change — CodeQL's `security-extended` switch is the example this SOP was written
  against, but the trigger applies to any configured scanner, present or future, not
  CodeQL specifically — and at least once per quarter otherwise.
- **Procedure:** pull the full open-alert list (not just `is:open` counts — verify the
  count against the actual list, as a prior triage pass under-summed a group and
  reported a materially wrong total before being caught against the Security tab UI),
  group by query ID and trust boundary, and apply §V.2's per-alert disposition to any
  alert without one yet. Also pull the complete dismissed-alert list — every
  supported dismissal reason (`false positive`, `won't fix`, `used in tests`,
  `mitigated`), not only the first two — and re-walk each prior
  false-positive/mitigated disposition against the current code: a dismissed alert is
  absent from the open-alert list by definition, so a mitigation invalidated by a
  later code change (the guarding check removed, the trust boundary widened) would
  otherwise stay invisible indefinitely.
- **Record:** each review's output is a dated document under `docs/ops/audits/`
  (following the `SECURITY_TRIAGE_<date>_<topic>.md` naming already in use), stating
  the total open-alert count at review time, the count newly dispositioned, the count
  still pending with its tracked follow-up, and the count of previously-dismissed
  alerts re-examined and confirmed still valid (or reopened, if not).
- A reviewer MUST NOT treat "no new alerts since last review" as equivalent to "no
  review needed" — the review's purpose includes re-examining whether a prior
  false-positive/mitigated disposition, open or already dismissed, still holds as the
  surrounding code changes.

## VI. Required Evidence and Handoff

A SAST-related change handoff (a gating-configuration change, a disposition pass, or
a new coverage guard) MUST include: the specific rule/threshold or query ID changed,
the evidence required by §V.2 for every disposition made, the guard's mutation-proof
test where one was added, and, for a recurring review, the dated record required by
§V.4. A change that only reports "alert count went down" without per-alert evidence
does not meet this bar.

## VII. Prohibited Operations

Reviewers and operators MUST NOT: dismiss a SAST finding without the evidence
required by §V.2; dismiss a batch of findings as a single action without each
member's own evidence; treat a diff-scoped merge check as equivalent to a
full-backlog review; rely on a changelog note or comment as proof that a coverage gap
is closed without an accompanying query or proven guard test; skip, disable, or
quarantine a guard test to make it stop reporting a real finding; or let a known
coverage gap (§V.3) go unreviewed past the cadence in §V.4.

## VIII. Amendment

Revisions require a version increment, updated effective date, review against the
Section IV dependencies, and evidence that the revised procedure still closes the gap
described in `docs/ops/audits/INCIDENT_2026-10-11_SEC-SAST-GAP-001.md`.
