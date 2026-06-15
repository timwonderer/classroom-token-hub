# V2 Documentation Compliance Sweep

**Last Updated:** 2026-04-25
**Purpose:** Track active-document updates required so repository documentation matches current v2 runtime truth and launch framing.

## Active v2 Truth

- `codex/v2.0` is the active protected v2 branch.
- `ClassEconomy` and `ClassMembership` define class authority.
- `current_join_code` is the active class context.
- Public teacher references use `public_id` / `teacher_public_id`, not numeric teacher IDs.
- Historical logs remain preserved, but active guidance must point to current trackers and SOPs.

## Sweep Results

| Area | Status | Finding | Action |
|---|---|---|---|
| `DEVELOPMENT.md` quick links | `fixed` | The old v2 checklist link pointed to `docs/development/multi-tenancy-rebuild/v2_release_checklist.md`, which no longer exists | Replaced with links to the new reconciliation tracker, launch readiness matrix, and documentation sweep |
| `README.md` v2 references | `fixed` | Top-level docs section did not point to the active reconciliation/readiness artifacts | Added links to the new v2 tracker and readiness matrix |
| `LOG-ARC-049` role | `fixed` | Historical checklist still contained the only visible main-feature reconciliation note | Converted it to point to the new active tracker and readiness matrix |
| `SOP-DEP-023` completeness | `fixed` | Scope and dependencies were incomplete or placeholder-level | Normalized scope/dependencies language so the runbook reads as an active v2 document |
| Active v2 authority wording | `reviewed` | Searched active architecture/SOP/dev/user docs for `TeacherBlock`, `teacher_id`, numeric teacher ID, and fallback wording | No new blocking contradiction found in the actively referenced v2 docs beyond the already-known stale checklist path |
| Documentation index coverage | `fixed` | The central documentation index did not list the active v2 tracker/readiness/compliance docs | Added the active v2 development docs to `SOP-DOC-002_DOCUMENTATION_INDEX.md` |
| Focused active-doc link validation | `fixed` | A focused active-doc link pass found a stale README support link to `docs/GITHUB_SITE/README.md` | Repointed the support link to `docs/README.md` and reran the focused link pass |
| V2 Hardening Blueprint Coverage | `fixed` | Major gaps identified in multi-tenancy, join-code isolation, ledger integrity, and analytics alerting specs | Created 4 new constitutional documents (ARC-OPS-015, ARC-SYS-002, DOM-ECON-003, DOM-ECON-004) and updated identity spec ARC-IDEN-001 |
| Historical development analyses | `defer` | Several development/historical docs still discuss legacy compatibility, `teacher_id`, or transition-only behavior | Preserve as historical unless they are promoted back into active guidance |
| Runtime stabilization tracker sync (2026-04-25) | `fixed` | Core v2 trackers had stale dates/status against current branch baseline | Updated reconciliation, launch readiness, launch checklist, parallel workstreams, temporal audit, and realignment checklist to current baseline (`619 passed, 123 failed, 1 skipped`) and current blockers |

## Interpretation Rules

- Treat architecture docs, SOPs, `README.md`, and `DEVELOPMENT.md` as active guidance.
- Treat `docs/LOGS/` and older development-analysis files as historical unless they are explicitly cited as active source of truth.
- When a historical doc is still useful, add supersession guidance instead of rewriting the historical record.

## Remaining Active-Doc Follow-Ups

1. If any must-port code changes alter runtime contract wording, update the corresponding architecture or SOP docs in the same change wave.
2. Re-run the focused active-doc link check after future production-required doc or workflow ports land.
3. Keep tracker baseline metrics synchronized whenever the full-suite snapshot changes materially.
