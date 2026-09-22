# Status simplification validation — 2026-09-22

This report covers the isolated `simplify-status-observations` worktree. It does not establish deployment or production end-to-end readiness.

## Runtime and isolation

The verification used a temporary Python 3.13 virtual environment. A read-only `.pth` reuses existing application dependencies; pinned status dependencies were installed only in this temporary virtual environment. The configured application virtual environment was not modified.

The temporary isolation wrapper read only the dedicated `TEST_DATABASE_URL`, validates a loopback host and an explicitly named test database, rejects a worktree `.env`, and passes a clean environment. No production credentials or environment were copied. Local test database connectivity was verified with `SELECT 1`. Sandbox escalation was needed for localhost database/browser access. No full-suite tests were run.

## Targeted tests

The commands below are portable test invocations run from the repository root with
the documented test dependencies and dedicated test database configured. During
this verification they were launched through the temporary isolation wrapper
described above. The wrapper is not a repository tool.

Before status UI changes, the required accessibility files passed with **20 passed in 6.26 seconds**, no skips:

```sh
python -m pytest -q tests/test_accessibility.py tests/test_axe_compliance.py
```

Final combined verification passed with **209 passed in 29.38 seconds**, no skips or failures:

```sh
python -m pytest -q tests/test_status_measurements.py tests/test_status_platform.py tests/test_status_store.py tests/test_status_page.py tests/test_status_sampler.py tests/test_status_identity.py tests/test_status_collector.py tests/test_status_resolution.py tests/test_status_deploy_workflow.py tests/dom/operation/test_health.py tests/test_accessibility.py tests/test_axe_compliance.py
```

The final run includes all platform checks, seven new mockup/order/state-mapping regressions, and the malformed Loki Boolean-value regression. Its 209 passing cases include all 20 mandatory accessibility cases. Earlier intermediate successful runs returned 185 and 202 passed; they are not the final verification count. The run generated these repository-relative test artifact names:

- `pytest_result/20260922_pytest_test_status_measurements_summary_7.md`
- `pytest_result/20260922_pytest_test_status_measurements_results_7.csv`
- `pytest_result/20260922_pytest_test_status_measurements_failures_7.log`

An earlier integration run returned 167 passed and 14 failures. Every failure called the intentionally removed public `derive_overall_status` helper from superseded projection tests. Those tests and the obsolete public observation/projection modules were retired as part of the requested simplification; no legacy compatibility helper was restored. Relevant independent notice, timestamp, freshness, and pure-GET assertions are covered by the new page/store tests and retained notice tests. The earlier failure count is retained here for traceability; the temporary run artifacts are not published with this document.

Independent review also reproduced malformed numerical and Loki-element failures; fixes and regressions are included in the passing final run. An additional transaction simulation confirmed that a different payload within an already persisted source minute cannot change its immutable snapshot, daily counters, or current pointer; all transactional reads preceded writes.

Supplemental documentation verification reported four focused documentation tests passed and 136 relative links resolved. These checks are separate from the 209-test integration count.

## Visual references and rendered accessibility

The first simplified preview passed automated checks but was rejected for changing the established presentation. Automated accessibility results did not establish visual fidelity. The correction restores the original icon wordmark and public-page design and follows the supplied `up mode.png` and `degraded.png` mockups: hero, human update banner, compact question/result cards, then platform details.

The actual original `b7db24437` status template/base/CSS and canonical `github-pages/index.html` were served locally as visual references. Screenshots were inspected at desktop width 1280 and mobile width 390. The corrected `.landing-brand` subtree, including all three decorative icons, matches both references after whitespace normalization. Inspected computed font family, size, weight, line height, gaps, padding, borders, colors and hero grid styles match the original status page at both widths. The canonical marketing page has a pre-existing 40-pixel narrower desktop right grid track due to its Bootstrap shell sizing; the correction preserves the original status sizing. Shared `cth-public.css` is byte-identical to `github-pages/style.css`.

The mockup layout was checked in 12 combinations: populated, healthy without an incident, idle, stale, monitoring unavailable, and severe errors, each at widths 1280 and 390. All had zero axe-core WCAG 2 A/AA violations, no horizontal overflow, the required section order, five simple cards without technical metrics, and detailed endpoint/database/request/history information in the lower platform section. Keyboard Enter and mobile touch opened history disclosures. These checks use synthetic data and do not access production.

A real contrast defect discovered during restoration was fixed: the inherited warning result bar had contrast 4.42:1; the scoped result text now uses the darker existing text token. A subsequent visual check found result bars misaligned when one same-row card question wrapped. The cards now use a column layout with bottom-aligned result bars.

After that final alignment correction, six combinations were repeated: populated, healthy, and severe, each desktop/mobile. All repeated axe, overflow, section-order, simple-card, platform visibility, keyboard/touch, and same-row result-bottom geometry checks passed. The idle/stale/unavailable checks apply to the immediately preceding layout version; those six combinations were not repeated after the alignment-only CSS change.

Synthetic platform times were also corrected to precede the render clock by five seconds. This corrected a fixture issue that had exercised the product's intentional future-time rejection. Final populated/healthy fixtures explicitly show both platform rows Responding; the final severe fixture shows the database Check failed and attendance Possibly down. Production future-time rejection was not weakened.

The mandatory accessibility files primarily audit application public/auth pages and published marketing pages; the separate rendered checks cover the changed standalone status surface. Axe and the bounded interaction checks are not comprehensive accessibility certification.

Local verification artifact groups (not repository files or published attachments):

- `brand-correction/`: original/canonical/corrected hero and viewport screenshots, computed properties, and `final-original-comparison.json`.
- `mockup-final/`: ten initial final-mockup scenarios and `results.json`.
- `mockup-final-healthy/`: the two healthy/no-incident scenarios before the final alignment correction.
- `mockup-final-alignment/`: final populated/healthy/severe desktop/mobile screenshots and `results.json`, including verified platform outcomes and result-bar alignment.
- `pytest/`: baseline, intermediate, and final integrated test artifacts.
- `all-states-before-final-spacing/` and `final-populated/`: superseded first-preview evidence, retained only for traceability.

Final healthy desktop screenshot: `mockup-final-alignment/healthy-1280-viewport.png`; mobile counterpart: `mockup-final-alignment/healthy-390-viewport.png`. Populated and severe counterparts use the same filename pattern. Each also has full-page and hero PNGs.

The local synthetic preview used fixture names `healthy`, `populated`, `idle`,
`stale`, `unavailable`, and `severe`. Separate local previews rendered the original
status page and canonical marketing page. Those temporary preview servers are not
durable review links; this report does not claim their availability.

## Read-only production checks

The sampler was executed against production Loki from a disposable temporary directory without calling `write_snapshot`, installing files or services, or starting a unit. The directory was removed afterward. The bounded output reported:

- Sample time: `2026-09-22T06:12:00+00:00`.
- Latest source event: `2026-09-22T06:11:10.064735+00:00`.
- Application request group: 9 requests, `LOW_TRAFFIC`, p80 27.4 ms, p95 82 ms.
- The other five route groups: `NO_TRAFFIC`.

A separate read-only parser check of the existing production `/health/status` returned HTTP_OK and DATABASE_REACHABLE at `2026-09-22 06:32:03 UTC`, preserving the database source timestamp. It did not test external Cloudflare-token transport or persist a platform observation.

This was tool-output evidence; no remote result file was retained. It validates the proposed query path against that production Loki snapshot, not deployment or business correctness.

`systemd-analyze verify` returned exit 0 for both proposed units in a disposable production directory. It emitted an unrelated existing `/lib/systemd/system/snapd.service:23` unknown `RestartMode` warning. No units were installed or started.

## Remaining deployment verification

Sampler user, paths, file ownership, filesystem permissions, timer execution, and service network restrictions require verification during deployment. The static nginx endpoint, authenticated collector transport, Firestore TTL provisioning, deployed collector scheduling, and production source → collector → Firestore → rendered-page path have not been certified by these local tests. No live rollout or end-to-end public status readiness claim is made here.
