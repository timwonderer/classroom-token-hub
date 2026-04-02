# Design System Audit — Classroom Token Hub

**Original Audit:** 2026-04-01
**Updated Audit:** 2026-04-01
**Branch:** design-audit
**Files reviewed:** `tokens.css`, `style.css` (2,199 lines), `admin-insurance-advisor.css`, 111 HTML templates

---

## Progress Summary

Significant work has landed across 39 files since the original audit. The table below reflects current status.

| # | Issue | Original Score | Status |
|---|-------|---------------|--------|
| 1 | Pervasive `<style>` blocks in templates | 4/10 | **Partially fixed** — 50→30 templates |
| 2 | Broken `--student-primary` token | Critical | **Fixed** |
| 3 | Bootstrap version fragmentation | 5/10 | **Mostly fixed** — 22→6 outdated |
| 4 | Login layout duplication | High | **Fixed** — extracted to `style.css` |
| 5 | `pt`-unit icon sizing (76 instances) | High | **Fixed** — 76→12 instances, utilities added |
| 6 | Missing `--warning-text` token | Medium | **Fixed** |
| 7 | Duplicate sidebar implementations | Medium | **Partially fixed** — sysadmin brand unified |
| 8 | `student_setup_complete.html` divergence | Medium | **Fixed** |
| 9 | Hardcoded colors in `style.css` | Medium | **Open** — Easter egg colors remain |
| 10 | `admin-insurance-advisor.css` hardcoded RGBA | Medium | **Fixed** |
| 11 | `docs/timeline.html` parallel color system | Low | **Open** |
| 12 | Radius token naming mismatch | Low | **Open** |

**New issues identified in this pass:** 2 (see Issues 13–14 below)

---

## Resolved Issues

### ✅ Issue 2 — `--student-primary` Token (Fixed)

`tokens.css` now defines `--student-primary: #2F4F7F` inside the `body.student-shell` block. The `.bg-student`, `.text-student`, and `.border-student` utility classes now resolve correctly.

### ✅ Issue 4 — Login Layout Duplication (Fixed)

`style.css` now contains a full auth shell component system (`body.auth-page`, `.login-container`, `.login-left`, `.login-right`, `.auth-page--compact`, `.auth-welcome-copy`). The SVG crosshatch pattern is consolidated in one place. `admin_login.html`, `admin_signup.html`, and `student_account_claim.html` have had their `<style>` blocks removed. `student_setup_complete.html` now uses `.auth-page--compact`.

### ✅ Issue 5 — Icon Sizing (Mostly Fixed)

Icon utility classes added to `style.css`:

| Class | Size | Notes |
|-------|------|-------|
| `.icon-xl` | 2rem | Large decorative |
| `.icon-section` | 2rem + middle-align | Section headers |
| `.icon-inline` | 1rem + middle-align | Inline with text |
| `.icon-md` | 1.125rem + middle-align | Standard UI icons |
| `.icon-sm` | 0.875rem + middle-align | Small/compact |
| `.icon-hero` | 4rem | Hero/success displays |
| `.icon-success-hero` | Defined | Success state |

The 58× `font-size:25pt; vertical-align:middle` pattern for tab nav icons has been resolved. **12 inline font-size attributes remain** (see Issue 5 below).

Note: **`.icon-lg` is not defined** — there is a gap in the scale between `.icon-md` (1.125rem) and `.icon-xl` (2rem). Some callsites use `font-size: 2rem` inline as a result.

### ✅ Issue 6 — `--warning-text` Token (Fixed)

All three role themes in `tokens.css` now define `--warning-text`:
- Teacher (`:root`): `#856404`
- Student (`body.student-shell`): `#7a5d11`
- Sysadmin (`body.sysadmin-shell`): `#856404`

`style.css` now uses `var(--warning-text)` without a fallback.

### ✅ Issue 8 — `student_setup_complete.html` (Fixed)

The page now:
- Uses Bootstrap 5.3.3
- Uses `body class="student-shell auth-page auth-page--compact"`
- Uses `.login-container` and `.login-left` from the shared auth component
- Uses `.icon-success-hero` instead of `font-size:50pt` inline
- Uses `.btn.btn-primary.btn-lg` with no overrides
- Has no `<style>` block

### ✅ Issue 10 — `admin-insurance-advisor.css` (Fixed)

Hardcoded `rgba()` values replaced with token-based `color-mix()`:
```css
/* Before */
background: linear-gradient(180deg, rgba(236, 246, 252, 0.95) 0%, rgba(255, 255, 255, 1) 100%);
/* After */
background: linear-gradient(180deg, color-mix(in srgb, var(--info-subtle) 95%, transparent) 0%, var(--surface) 100%);
```

---

## Open Issues

### Issue 1 — Template `<style>` Blocks (Partially Fixed)

**Progress:** 50 → 30 templates still contain `<style>` blocks (40% reduction).

**Removed from:** `admin_login.html`, `admin_signup.html`, `student_account_claim.html`, `student_setup_complete.html`, `admin_recovery_status.html`, `admin_recovery_saved.html`, `student_pin_setup.html`, `student_create_username.html`, `student_complete_profile.html`, `admin_recover.html`, `error_400.html`, `error_401.html`, `error_403.html`, `error_404.html`, `error_500.html`, `student_verify_recovery.html`, and others.

**Still present in (30 templates):**

| Template | Style block content | Extractable? |
|----------|---------------------|-------------|
| `student_login.html` | `.pin-input`, `.btn-outline-primary` border-width tweak | Yes |
| `admin_signup_totp.html` | `.subtitle`, `.form-group`, `.manual-code` | Yes |
| `admin_reset_credentials.html` | `.step-indicator` (1 rule) | Yes |
| `admin_students.html` | `.block-tab-content`, `.quick-action-btn`, `.hold-delete-btn` | Yes |
| `student_detail.html` | `.stat-value`, `.stat-label`, `.negative-balance`, `.positive-balance` | Yes |
| `admin_feature_settings.html` | `.feature-card`, `.feature-stack`, `.period-badge` | Yes |
| `student_transfer.html` | `.transfer-processing-note` (2 rules) | Yes |
| `admin_insurance.html` | `#advancedInsuranceAccordion` scoped styles | Yes (extract to `admin-insurance-advisor.css`) |
| `admin_analytics_dashboard.html` | Analytics-specific styles | Yes |
| `admin_analytics_student_detail.html` | Analytics styles | Yes |
| `admin_store.html` | Store-specific styles | Yes |
| `admin_rent_settings.html` | Rent-specific styles | Yes |
| `admin_edit_item.html` | Item editor styles | Yes |
| `admin_edit_insurance_policy.html` | Policy editor styles | Yes |
| `student_file_claim.html` | Claim form styles | Yes |
| `admin_view_issue.html` | Issue view styles | Yes |
| `components/getting_started_widget.html` | Two blocks (lines 250, 741) | Yes — move to `style.css` |
| `hall_pass_setup.html` | Hall pass specific styles | Yes |
| `hall_pass_queue.html` | Two blocks | Yes |
| `hall_pass_terminal.html` | Terminal + `.btn-primary` override | Partial |
| `system_admin_logs.html` | Log viewer styles | Yes |
| `docs/timeline.html` | Full self-contained color system | Internal only |
| `docs/view.html` | Doc viewer + `.btn-primary` override | Partial |
| `student_create_username.html` | Auth flow styles | Yes |
| `tos.html` | Legal page styles | Lower priority |
| `privacy.html` | Legal page styles | Lower priority |
| `offline.html` | `.btn-primary` override | Yes — 1 rule is redundant |
| `maintenance.html` | Maintenance page styles | Lower priority |
| `error_503.html` | Error page styles | Lower priority |
| `admin_rent_settings.html` | Rent styles | Yes |

**`.btn-primary` overrides still present in:**
- `offline.html` — redundant (sets `var(--primary)`, which is already the value)
- `hall_pass_terminal.html` — adds `box-shadow: var(--shadow-md)` (the only real change)
- `docs/view.html` — sets `var(--primary)` (also redundant)

---

### Issue 3 — Bootstrap Version Fragmentation (Mostly Fixed)

**Progress:** 22 → 6 templates still on Bootstrap 5.3.0.

**Remaining 5.3.0 templates:**
```
error_503.html
tos.html
hall_pass_queue.html
maintenance.html
hall_pass_terminal.html
privacy.html
```

All six are standalone pages (legal, error, hall pass terminal, maintenance) that load Bootstrap directly rather than inheriting a layout. The `components/getting_started_widget.html` now uses 5.3.8 — this should be pinned back to 5.3.3.

**Remaining distribution:**
| Version | Count |
|---------|-------|
| 5.3.0 | 6 |
| 5.3.3 | 48 |
| 5.3.8 | 1 (`getting_started_widget.html`) |

---

### Issue 5 — Icon Sizing (Residual)

12 inline `font-size` attributes remain on icon elements:

| File | Inline style | Suggested class |
|------|-------------|-----------------|
| `hall_pass_verify.html` | `font-size:1rem` | `.icon-inline` |
| `hall_pass_setup.html` (×2) | `font-size: 1rem` | `.icon-inline` |
| `admin_banking.html` | `font-size: 2rem` | `.icon-section` |
| `admin_insurance.html` | `font-size: 2rem` | `.icon-section` |
| `admin_rent_settings.html` | `font-size: 2rem` | `.icon-section` |
| `admin_store.html` (×2) | `font-size: 2rem` | `.icon-section` |
| `admin_store.html` | `font-size: 13px` | `.icon-sm` |
| `system_admin_manage_admins.html` (×2) | `font-size: 20px` | `.icon-md` |
| `system_admin_manage_admins.html` | `font-size: 64px` | custom or `.icon-hero` |
| `maintenance.html` | `font-size:25pt` | `.icon-section` |
| `admin_analytics_dashboard.html` | `font-size:1.5rem` on `<small>` (text, not icon) | `fs-4` Bootstrap utility |

**Missing utility:** `.icon-lg` (no class exists between `.icon-md` at 1.125rem and `.icon-xl` at 2rem). Several callsites use `font-size: 2rem` inline that could use a `1.5rem` `.icon-lg` instead.

---

### Issue 7 — Duplicate Sidebar Implementations (Partially Fixed)

The sysadmin brand icon area has been unified (commit `ab8e3a6f`). The `.sysadmin-brand-icon` class was added to `style.css` to standardize icon rendering in the sysadmin sidebar brand.

The underlying structural duplication between `.sidebar`, `.student-sidebar`, and `.sysadmin-sidebar` still exists. All three repeat the same width, position, overflow, and transition declarations. This is lower-risk than the other open issues.

---

### Issue 9 — Hardcoded Colors in `style.css` (Open)

The following hardcoded hex values remain in `style.css`. White/black (`#fff`, `#ffffff`, `#000`) are acceptable — they are not theme-dependent. The non-neutral values are the concern:

| Line | Value | Context | Suggested replacement |
|------|-------|---------|----------------------|
| 870 | `#ffd900` | `.student-brand:hover .icon-bill` | Document as intentional Easter egg |
| 874 | `#00ffbf` | `.student-brand:hover .icon-store` | Document as intentional Easter egg |
| 878 | `#ff6c7d` | `.student-brand:hover .icon-stock` | Document as intentional Easter egg |
| 1004 | `#ff6666` | `.sysadmin-nav-signout:hover` | `color-mix(in srgb, var(--danger) 130%, white)` |

The three student brand hover colors are a deliberate Easter egg (bill=gold, store=green, stock=pink). They need a comment clarifying intent. The sysadmin signout hover color is a functional color that should derive from the danger token.

---

### Issue 11 — `docs/timeline.html` Parallel Color System (Open)

The changelog timeline defines 20+ custom CSS variables with hardcoded hex values that don't reference design tokens. Several duplicate existing tokens exactly:
- `--tl-features: #2e7d5b` = `--success`
- `--tl-fixes: #c0392b` = `--danger`

This is internal-facing documentation, so visual impact is low. Worth a cleanup pass when touching this file.

---

### Issue 12 — Radius Token Naming/Comments (Open)

Token comments in `tokens.css` still describe `--radius-sm` as "Cards, Inputs, Dropdowns" while actual usage also includes alerts, badges, and nav items. The comment is a minor inaccuracy that can mislead future contributors. No functional impact.

---

## New Issues Found in This Pass

### Issue 13 — Missing `.icon-lg` Class

The icon scale has a gap:

| Class | Size |
|-------|------|
| `.icon-sm` | 0.875rem |
| `.icon-md` | 1.125rem |
| *(missing)* | *~1.5rem* |
| `.icon-xl` | 2rem |

Several templates use `font-size: 2rem` inline where a `1.5rem` mid-size would be more appropriate. Without `.icon-lg`, contributors either reach for `.icon-xl` (too large) or write inline styles. Suggested addition:

```css
.icon-lg {
    font-size: 1.5rem;
    line-height: 1;
    vertical-align: middle;
}
```

---

### Issue 14 — `offline.html` and `docs/view.html` Redundant `.btn-primary` Overrides

Both templates define `.btn-primary { background-color: var(--primary); }` — which is already the value set by `style.css`. These overrides do nothing and should be removed to avoid confusion.

`hall_pass_terminal.html` overrides `.btn-primary` to add `box-shadow: var(--shadow-md)`. This is the only meaningful change; consider whether this should be a shared modifier class instead of a per-template override.

---

## Updated Fix Sequence

Work through these in order. Phases 1–3 close all critical and high-severity items.

---

### Phase 1 — One-Line Fixes (< 1 hour)

**1a. Add `.icon-lg` to `style.css`** (Issue 13)
```css
.icon-lg {
    font-size: 1.5rem;
    line-height: 1;
    vertical-align: middle;
}
```

**1b. Pin `getting_started_widget.html` Bootstrap back to 5.3.3** (Issue 3)

**1c. Remove redundant `.btn-primary` overrides** from `offline.html` and `docs/view.html` (Issue 14)

**1d. Comment the three Easter egg hover colors** in `style.css` (Issue 9)
```css
/* Intentional Easter egg: student brand hover shows themed icon colors */
```

**1e. Fix `.sysadmin-nav-signout:hover` color** (Issue 9)
```css
/* Before */
color: #ff6666 !important;
/* After */
color: color-mix(in srgb, var(--danger) 130%, white) !important;
```

---

### Phase 2 — Icon Cleanup (1–2 hours)

Replace the 12 remaining inline icon `font-size` attributes with utility classes:

| File | Change |
|------|--------|
| `hall_pass_verify.html`, `hall_pass_setup.html` | `style="font-size:1rem"` → `class="icon-inline"` |
| `admin_banking.html`, `admin_insurance.html`, `admin_rent_settings.html`, `admin_store.html` | `style="font-size: 2rem"` → `class="icon-section"` |
| `admin_store.html` | `style="font-size: 13px"` → `class="icon-sm"` |
| `system_admin_manage_admins.html` | `style="font-size: 20px"` → `class="icon-md"` |
| `maintenance.html` | `style="font-size:25pt"` → `class="icon-section"` |
| `admin_analytics_dashboard.html` | `<small style="font-size:1.5rem">` → `<span class="fs-4">` |

---

### Phase 3 — Bootstrap Version Pinning (30 min)

Update the 6 remaining 5.3.0 templates to 5.3.3:
```
error_503.html, tos.html, hall_pass_queue.html,
maintenance.html, hall_pass_terminal.html, privacy.html
```

---

### Phase 4 — Finish Auth Template Cleanup (1–2 hours)

Three auth templates still have `<style>` blocks with small amounts of extractable CSS:

| Template | Content | Action |
|----------|---------|--------|
| `student_login.html` | `.pin-input` styles | Add `.pin-input` to `style.css` auth section; remove border-width tweak (use Bootstrap's default) |
| `admin_signup_totp.html` | `.subtitle`, `.form-group`, `.manual-code` | `.subtitle` already exists as a class in auth section; extract others |
| `admin_reset_credentials.html` | `.step-indicator` (1 rule) | Add to `style.css` |

After extraction, all auth/login templates will be `<style>`-free.

---

### Phase 5 — Extract High-Value Component Classes (3–5 hours)

Extract `<style>` blocks from the highest-traffic templates into `style.css`:

| Template | Classes to extract | Priority |
|----------|--------------------|----------|
| `student_detail.html` | `.stat-value`, `.stat-label`, `.negative-balance`, `.positive-balance` | High — pattern used elsewhere |
| `admin_students.html` | `.block-tab-content`, `.quick-action-btn`, `.hold-delete-btn` | High — core admin view |
| `admin_feature_settings.html` | `.feature-card`, `.feature-stack`, `.period-badge` | Medium |
| `student_transfer.html` | `.transfer-processing-note` | Low — 2 rules only |
| `admin_insurance.html` | `#advancedInsuranceAccordion` styles | Medium — move to `admin-insurance-advisor.css` |
| `components/getting_started_widget.html` | Merge two blocks → external | Medium |

---

### Phase 6 — Standalone Page Bootstrap Update (1 hour)

The six legal/error/hall pass pages currently load Bootstrap directly. Rather than updating the CDN URL each release, consider having them extend `base.html` or a shared minimal layout. At minimum, update to 5.3.3 and add a comment noting they are standalone.

---

### Phase 7 — Sidebar Consolidation (3–4 hours, higher risk)

Extract shared structural rules from `.sidebar`, `.student-sidebar`, `.sysadmin-sidebar` into a single `.app-sidebar` base class. Role-specific classes handle only color and accent differences. Standardize layout approach — the sysadmin `body { display: flex }` pattern is cleaner than `margin-left` and worth adopting consistently.

---

### Phase 8 — Minor Token/Comment Cleanup (30 min)

- Update radius token descriptions in `tokens.css` to match actual usage
- Consider aliasing `--tl-features` → `var(--success)` in `docs/timeline.html`

---

## Files Reference

| File | Role | Lines |
|------|------|-------|
| `static/css/tokens.css` | Design token source of truth | 197 |
| `static/css/style.css` | Core component styles | 2,199 |
| `static/css/admin-insurance-advisor.css` | Insurance advisor component | 41 |
| `templates/layout_admin.html` | Admin shell layout | — |
| `templates/layout_student.html` | Student shell layout | — |
| `templates/layout_system_admin.html` | Sysadmin shell layout | — |

---

*Original audit: 2026-04-01. Updated: 2026-04-01. Branch: `design-audit`.*
