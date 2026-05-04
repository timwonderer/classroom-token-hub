# Development Docs

`docs/development/` is organized by document role:

- `specs/` — target-state architecture, invariants, authority boundaries, and end-state design contracts
- `tracking/` — active execution tracker(s); current single authority is `tracking/V2_Full_compliance_migration_plan.md`
- `archive/` — historical or superseded analysis kept for reference but not treated as active implementation authority

Rule of thumb:

- if a doc answers "what should the system be?" it belongs in `specs/`
- if a doc answers "where are we relative to that target?" it belongs in `tracking/` (single active tracker policy)
- if a doc is useful history but not current authority, it belongs in `archive/`
