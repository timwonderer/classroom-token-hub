# V2 Documentation Compliance Sweep

**Last Updated:** 2026-03-29
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
| Documentation index coverage | `needs update` | The central documentation index does not yet list the new v2 tracker/readiness/compliance docs | Add the new docs to `SOP-DOC-002_Documentation_Index.md` |
| Broader active-doc link validation | `needs update` | This sweep was targeted at v2 launch docs, not a full repo-wide broken-link crawl | Run a broader active-doc link pass after the first must-port wave lands |
| Historical development analyses | `defer` | Several development/historical docs still discuss legacy compatibility, `teacher_id`, or transition-only behavior | Preserve as historical unless they are promoted back into active guidance |

## Interpretation Rules

- Treat architecture docs, SOPs, `README.md`, and `DEVELOPMENT.md` as active guidance.
- Treat `docs/LOGS/` and older development-analysis files as historical unless they are explicitly cited as active source of truth.
- When a historical doc is still useful, add supersession guidance instead of rewriting the historical record.

## Remaining Active-Doc Follow-Ups

1. Add the new v2 tracker docs to the documentation index.
2. Re-run a focused active-doc link check after the live-test blocker ports land.
3. If any must-port code changes alter runtime contract wording, update the corresponding architecture or SOP docs in the same change wave.
