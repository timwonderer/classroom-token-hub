# Status activity policy validation

Implementation branch: `codex/status-bursty-activity`.
Scope: DOM-OPS-001 2.10 and SPEC-OPS-006 1.2. No production deployment performed.
The external status boundary is authorized directly by DOM-OPS-001/SPEC-OPS-006;
FEAT-OPS-001 governs protected application audit writes and is not invoked here.

- 99 focused tests passed across status page, store, measurements, platform,
  collector and sampler. Coverage includes burst-to-idle retention, original
  timestamps, failed collection, single 5xx, 404-only activity, recovery,
  duplicate delivery, invalid/future/expired context and platform freshness.
- Synthetic quiet, failure and monitoring-unavailable views rendered in Chromium
  at desktop 1440x1100 and mobile 390x844 widths. No horizontal overflow.
- axe-core WCAG 2.0/2.1 A/AA: zero violations in all three desktop views.
- Native disclosure toggles verified using focus and Enter. One h1 per view.
- Screenshots: `output/playwright/status-activity/` (local validation artifacts).
- All database tests use in-memory Firestore doubles; no production business
  activity or database writes. No full suite run.
