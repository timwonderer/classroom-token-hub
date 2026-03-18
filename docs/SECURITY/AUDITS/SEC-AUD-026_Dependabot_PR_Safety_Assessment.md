# SEC-AUD-026: Dependabot PR Safety Assessment

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SEC-AUD-026      | 1.0     | 2026-03-18     | N/A        | Informative     |

**Assessment Date:** 2026-03-18  
**Assessor:** GitHub Copilot Security Analysis  
**Scope:** Four open Dependabot PRs against `main` branch

---

## 1. Overview

This report assesses the safety of merging the following open Dependabot pull requests:

| PR    | Package                   | Old Version      | New Version        | Type              |
|-------|---------------------------|------------------|--------------------|-------------------|
| #1079 | `pytz`                    | 2025.2           | 2026.1.post1       | pip / data update |
| #1080 | `qrcode[pil]`             | 7.4.2            | 8.2                | pip / major bump  |
| #1081 | `redis`                   | 5.0.8            | 7.3.0              | pip / major bump  |
| #1098 | `webfactory/ssh-agent`    | v0.9.1           | v0.10.0            | GitHub Action     |

---

## 2. Vulnerability Check

The GitHub Advisory Database was queried for all four current (old) package versions:

| Package                | Current Version | Known CVEs |
|------------------------|-----------------|------------|
| `pytz`                 | 2025.2          | None       |
| `qrcode`               | 7.4.2           | None       |
| `redis` (redis-py)     | 5.0.8           | None       |
| `webfactory/ssh-agent` | v0.9.1          | None       |

No security vulnerabilities are present in any of the current versions. These are regular maintenance upgrades, not security-driven updates (labels notwithstanding).

---

## 3. Individual PR Assessments

### 3.1 PR #1079 — `pytz` 2025.2 → 2026.1.post1

**Verdict: ✅ SAFE — Merge approved**

**Analysis:**

- `pytz` is a timezone database package. Version updates contain updated IANA timezone data, not API changes.
- The package API (`pytz.timezone()`, `pytz.utc`, `pytz.UnknownTimeZoneError`, `pytz.all_timezones`) has been stable for many years and is unchanged between these versions.
- The codebase uses pytz extensively across `app/__init__.py`, `app/routes/admin.py`, `app/routes/student.py`, `app/routes/api.py`, `app/routes/analytics.py`, `app/attendance.py`, and `app/utils/time.py` — all using only stable public APIs.
- No deprecated APIs, no removed functions, no behavioral changes beyond updated timezone data for 2026.

**Risk:** None.

---

### 3.2 PR #1080 — `qrcode[pil]` 7.4.2 → 8.2

**Verdict: ✅ SAFE — Merge approved**

**Analysis:**

The codebase uses only two patterns from the `qrcode` library:

1. `qrcode.make(totp_uri)` — convenience function returning a PIL image  
   Used in: `app/routes/admin.py`, `app/routes/system_admin.py`

2. `qrcode.QRCode(border=2)` / `qr.add_data()` / `qr.make(fit=True)` / `qr.print_ascii(invert=True)`  
   Used in: `wsgi.py`, `scripts/create_admin.py`

**Changelog review (7.4.2 → 8.2):**

- **8.0**: Added Python 3.11/3.12 support; dropped Python ≤3.8; removed `typing_extensions` dependency; changed embedded-image error correction behavior.
- **8.1**: Python 3.13 support.
- **8.2**: Performance optimizations; backward-compatible fix for `embeded_*` parameter typos.

The one potentially impactful change in 8.0 is restricting the error correction level when generating QR codes **with embedded images**. The codebase does **not** use embedded images in QR codes — it only generates plain TOTP QR codes — so this change has no effect.

All other changes are additive (new module drawers, performance improvements, SVG fixes). The two code patterns used by this codebase are unaffected.

**Risk:** None for this codebase's usage.

---

### 3.3 PR #1081 — `redis` 5.0.8 → 7.3.0

**Verdict: ✅ SAFE — Merge approved**

**Analysis:**

The `redis` package is **not imported directly** anywhere in the application code. It serves exclusively as a backend for Flask-Limiter's rate-limit storage via the URI string `redis://localhost:6379` (configured in `app/extensions.py`).

Flask-Limiter delegates all Redis interactions to its `limits` dependency. Inspection of the installed `limits` package reveals the following version constraint:

```
redis!=4.5.2,!=4.5.3,<8.0.0,>3; extra == "redis"
```

Redis 7.3.0 satisfies this constraint (`>3` and `<8.0.0`). The upgrade is therefore fully supported by the library stack in use.

**Breaking change risk for direct consumers:**

Redis-py 6.x and 7.x introduced breaking API changes (e.g., removal of some deprecated commands, protocol changes). However, because the application uses `redis` only indirectly as a storage backend — with zero direct calls to the redis-py client API — none of these breaking changes affect this codebase.

**Risk:** None for this codebase's usage pattern.

---

### 3.4 PR #1098 — `webfactory/ssh-agent` v0.9.1 → v0.10.0

**Verdict: ✅ SAFE — Merge approved**

**Analysis:**

- Used in `.github/workflows/deploy.yml` and `.github/workflows/toggle-maintenance.yml` for SSH key injection during deployment.
- This is a minor version bump (0.9 → 0.10), indicating backward-compatible changes under semantic versioning.
- The action is widely used and well-maintained by a trusted organization (`webfactory`).
- Only the version pin is changed; no configuration or interface changes are required.

**Risk:** Negligible (standard minor version bump from a trusted, well-maintained action).

---

## 4. CI Check Results

All four PRs passed the `audit-guard` CI check (the only applicable check given the nature of the changes):

| PR    | audit-guard | actionlint | Aikido Security | CodeQL   |
|-------|-------------|------------|-----------------|----------|
| #1079 | ✅ success  | —          | —               | neutral  |
| #1080 | ✅ success  | —          | —               | neutral  |
| #1081 | ✅ success  | —          | —               | neutral  |
| #1098 | ✅ success  | ✅ success | ✅ success      | neutral  |

PR #1098 additionally passed `actionlint` (YAML workflow linting) and Aikido Security scanning, both with success.

---

## 5. Summary and Recommendation

All four Dependabot PRs are safe to merge.

| PR    | Package                | Change Type       | Breaking Changes | Verdict        |
|-------|------------------------|-------------------|-----------------|----------------|
| #1079 | `pytz`                 | Timezone data     | None            | ✅ Merge        |
| #1080 | `qrcode[pil]`          | Major version     | None (for usage)| ✅ Merge        |
| #1081 | `redis`                | Major version ×2  | None (indirect) | ✅ Merge        |
| #1098 | `webfactory/ssh-agent` | Minor version     | None            | ✅ Merge        |

The upgrades have been applied to `requirements.txt` and the relevant workflow files in this branch.

---

**Assessment Completed:** 2026-03-18
