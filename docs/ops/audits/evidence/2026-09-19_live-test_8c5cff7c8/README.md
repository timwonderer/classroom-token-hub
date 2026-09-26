# Gate evidence — live test deployment, 2026-09-19

Release SHA: `8c5cff7c894eb38e2f4908fbf49b08e41f8f3e9a`
Record: [`../../LIVE_TEST_DEPLOYMENT_2026-09-19.md`](../../LIVE_TEST_DEPLOYMENT_2026-09-19.md)

`pytest_result/` at the repository root is gitignored: every targeted run writes
its own CSV, summary and failures log, and tracking them would add thousands of
files a week. Only **gate runs** — a full suite backing a deployment record —
are promoted here, where they are immutable and readable without the operator's
machine.

| File | Contents |
|---|---|
| `pytest_full_summary.md` | Generated run summary. `git_commit` records `8c5cff7c8`, matching the release SHA. |
| `pytest_full_results.csv` | Per-test outcome and duration, 2997 rows. The source for the skip disposition in the record. |
| `pytest_full_failures.txt` | The run's failures log, which records no failures. Retained so its emptiness is evidence rather than an absent file. Renamed from `.log` only because `*.log` is gitignored repository-wide; contents are unmodified. |

Copied verbatim from `pytest_result/`; not regenerated or edited.
