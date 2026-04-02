# Design System Audit — Classroom Token Hub

**Audit Date:** 2026-04-01
**Branch:** design-audit
**Files reviewed:** `tokens.css` (197 lines), `style.css` (1,378 lines), `admin-insurance-advisor.css` (38 lines), 111 HTML templates

---

## Summary

| Category | Score | Issues Found |
|----------|-------|--------------|
| Token Architecture | 8/10 | 3 broken/missing tokens |
| Component Consistency | 6/10 | Duplicate sidebar implementations, missing abstractions |
| Template Hygiene | 4/10 | **50 of 111 templates** contain `<style>` blocks |
| Standalone Styling | 3/10 | Login, auth, and setup flows are largely isolated |
| Bootstrap Version | 5/10 | 3 different versions in use simultaneously |
| Icon System | 5/10 | 76 `pt`-unit icon sizes, no standardized scale |
| Aesthetics/Visual | 7/10 | Coherent role themes, some gradient drift |

**Overall: 5.4/10 — Functional but fragmented. Core token architecture is solid; template hygiene is the dominant failure mode.**

---

## Issue 1 — CRITICAL: Pervasive Template-Scoped `<style>` Blocks

**50 of 111 templates** contain inline `<style>` blocks. This is the single largest systemic issue.

These blocks fragment the design system, make changes require multi-file edits, and in several cases **override global component classes** like `.btn-primary` and `.card`.

**Impacted templates (selected):**

| Template | What it defines |
|----------|----------------|
| `admin_login.html` | `.login-container`, `.login-left`, `.login-right`, `.btn-primary` |
| `student_login.html` | Same `.login-container` pattern (near-duplicate) |
| `admin_signup.html` | Login layout (third copy) |
| `student_account_claim.html` | Overrides `.btn-primary` |
| `student_setup_complete.html` | Overrides `.btn-primary` with gradient, redefines `.card` |
| `admin_signup_totp.html` | Overrides `.btn-primary` |
| `admin_reset_credentials.html` | Overrides `.btn-primary` |
| `student/recovery/layout.html` | Overrides `.btn-primary` |
| `admin_insurance.html` | `#advancedInsuranceAccordion` styles |
| `admin_analytics_dashboard.html` | Styles inserted at line 585 (below fold) |
| `admin_students.html` | `.block-tab-content`, `.quick-action-btn`, `.hold-delete-btn` |
| `student_detail.html` | `.stat-value`, `.stat-label`, `.negative-balance`, `.positive-balance` |
| `admin_feature_settings.html` | Standalone styles |
| `components/getting_started_widget.html` | TWO separate style blocks (lines 250 and 741) |
| `docs/timeline.html` | Self-contained color system (20+ custom tokens) |
| `hall_pass_queue.html` | TWO separate style blocks |
| `hall_pass_terminal.html` | TWO separate style blocks |
| `error_400/401/403/404/500` | Each has its own style block |

**Specific `.btn-primary` override pollution** — 7+ templates redefine `.btn-primary` with different styles. `student_setup_complete.html` replaces it with a gradient using `var(--info)` (blue) instead of the intended primary color — a semantic mismatch.

---

## Issue 2 — CRITICAL: Broken Token `--student-primary`

`style.css` lines 309–319 define three utility classes that reference an **undefined token**:

```css
/* These silently produce no color — computed as `initial` */
.bg-student     { background-color: var(--student-primary) !important; }
.text-student   { color: var(--student-primary) !important; }
.border-student { border-color: var(--student-primary) !important; }
```

`tokens.css` scopes the student primary as `--primary` under `body.student-shell`, not as `--student-primary`. These three classes are broken in all contexts.

**Fix options:** Either add `--student-primary: #2F4F7F` to the student-shell block in `tokens.css`, or remove these three utility classes if unused.

---

## Issue 3 — HIGH: Three Nearly Identical Login Layout Implementations

`admin_login.html`, `student_login.html`, `admin_signup.html`, and `student_account_claim.html` each define their own version of the same two-column login layout via duplicated `<style>` blocks:

```css
/* Repeated 4 times across different templates */
.login-container { max-width: 900px; display: flex; min-height: 600px; }
.login-left      { flex: 1; padding: 3rem; }
.login-right     { flex: 1; background: linear-gradient(...var(--primary)...); }
.login-right::before { /* SVG crosshatch pattern */ }
```

**Visual divergence found between copies:**
- `admin_login.html` `.login-right`: uses `linear-gradient(135deg, var(--primary), var(--primary-hover))`
- `student_login.html` `.login-right`: uses `var(--primary)` (flat, no gradient)

---

## Issue 4 — HIGH: Bootstrap Version Fragmentation

Three different Bootstrap versions are loaded across the 111 templates:

| Version | Template Count | Status |
|---------|---------------|--------|
| 5.3.0 | 22 | Outdated |
| 5.3.3 | 33 | Project standard |
| 5.3.8 | 1 | Ahead of standard |

Templates using the outdated 5.3.0 are mostly auth flows, error pages, and standalone pages that load Bootstrap directly rather than inheriting from a base layout.

---

## Issue 5 — HIGH: `pt`-Unit Icon Sizing (76 instances)

| Size | Count | Context |
|------|-------|---------|
| `font-size:25pt` | 58 | Tab nav icons (banking, insurance, analytics, issues queue) |
| `font-size:50pt` | 1 | Success page check icon |
| `font-size:28pt` | 1 | — |
| `font-size:15pt` | 1 | Welcome text (not an icon) |
| `font-size:12pt` | 2 | — |
| `font-size:10pt` | 2 | — |

The `25pt ≈ 33.3px` tab icon pattern is the highest-volume case. It relies on `vertical-align:middle` to compensate for the non-standard sizing. The global `.material-symbols-outlined` default is already `font-size: 24px`.

The system has no named icon size classes, so every callsite uses a raw inline `style=` attribute.

---

## Issue 6 — MEDIUM: Missing `--warning-text` Token

`style.css` line 1103 references an undefined token with a hardcoded fallback:

```css
.bg-warning-subtle {
    color: var(--warning-text, #856404);  /* #856404 is Bootstrap's value, not ours */
}
```

All other subtle variants (`success`, `danger`, `info`) use their color tokens directly. The `warning` subtle background will render text in a Bootstrap default color rather than deriving from the custom warning token (`#c08c15`).

---

## Issue 7 — MEDIUM: Duplicate Sidebar Implementations

Three sidebar classes duplicate the same structural rules:

| Class | Used In | Z-index |
|-------|---------|---------|
| `.sidebar` | `layout_admin.html` | 1000 |
| `.student-sidebar` | `layout_student.html` | 1000 |
| `.sysadmin-sidebar` | `layout_system_admin.html` | 1050 |

All three repeat: `width: 260px`, `top: 0; left: 0; bottom: 0`, `overflow-y: auto`, `transition: transform 0.3s ease`, `padding: 1.5rem`. Their differences (colors, accent rules) should come from tokens, not separate class definitions.

Additionally, the three layouts use different structural patterns:
- Admin/Student: `margin-left: 260px` on content wrapper
- Sysadmin: `display: flex` on body

---

## Issue 8 — MEDIUM: `student_setup_complete.html` Aesthetic Divergence

This is the **first page a new student sees after account creation** and is the most visually divergent from the design system:

- Loads Bootstrap 5.3.0 (outdated)
- Redefines `.card` with `border-radius: 16px` (bypasses `--radius-sm: 4px`)
- Overrides `.btn-primary` with a **blue gradient using `var(--info)`** — button is blue, not student-blue
- Body background is solid blue (`var(--info)`) — doesn't reflect the Steward Blue role identity
- Uses `font-size:50pt` on success icon and `font-size:15pt` on welcome text
- Defines `font-variation-settings` inside a media query (incorrect placement)

---

## Issue 9 — MEDIUM: Hardcoded Colors in `style.css`

| Line | Value | Context | Suggested Token |
|------|-------|---------|----------------|
| 756 | `#ffd900` | `.student-brand:hover` icon | `--secondary` or new brand token |
| 760 | `#00ffbf` | `.student-brand:hover` icon | new token |
| 764 | `#ff6c7d` | `.student-brand:hover` icon | new token |
| 882 | `#ff6666` | `.sysadmin-nav-signout:hover` | `color-mix(in srgb, var(--danger) 120%, white)` |
| 890 | `#f5f5f3`, `#fafaf8` | `.sysadmin-main` gradient | `var(--neutral-100)`, `var(--neutral-50)` |

The three student brand hover icon colors are a playful Easter egg. They are fine as-is if intentional but should be commented as such.

---

## Issue 10 — MEDIUM: `admin-insurance-advisor.css` Uses Hardcoded RGBA

```css
/* Should use token-based color-mix() instead */
background: linear-gradient(180deg, rgba(236, 246, 252, 0.95) 0%, rgba(255, 255, 255, 1) 100%);
background: rgba(255, 255, 255, 0.92);
```

`rgba(236, 246, 252, 0.95)` is an approximation of `var(--info-subtle)`. Replace with:

```css
background: color-mix(in srgb, var(--info-subtle) 95%, transparent);
background: color-mix(in srgb, var(--surface) 92%, transparent);
```

---

## Issue 11 — LOW: `docs/timeline.html` Parallel Color System

The changelog timeline defines its own 20+ token color palette, several of which duplicate existing tokens:

| Timeline token | Value | Existing token |
|---------------|-------|----------------|
| `--tl-features` | `#2e7d5b` | Same as `--success` |
| `--tl-fixes` | `#c0392b` | Same as `--danger` |
| `--tl-arch` | `#2980b9` | Similar to `--info` |

This page is internal-facing so it is lower priority, but duplicated values drift over time.

---

## Issue 12 — LOW: Token Naming vs. Usage Mismatch in Radius Scale

`tokens.css` comments describe radius tokens as:
- `--radius-sm: 4px` — "Cards, Inputs, Dropdowns"
- `--radius-md: 6px` — "Buttons"
- `--radius-lg: 8px` — "Modals, Large Containers"

Actual usage in `style.css` treats alerts as `--radius-sm` (not mentioned in comments), and `student_setup_complete.html` bypasses the system entirely with `border-radius: 16px`. The comment descriptions are inaccurate guides for future contributors.

---

## Aesthetic Observations

**Strong areas:**
- Three-role color system (Advisor Green / Steward Blue / Guardian Gray) is well-considered and creates meaningful visual separation
- Badge and alert components follow the token system faithfully
- Sidebar navigation has strong visual hierarchy and role differentiation
- Card component is clean and consistent where the system is respected

**Weak areas:**
- Student setup completion flow (blue gradient body + blue gradient button) is disconnected from Steward Blue identity
- Tab navigation icons at `25pt`/`vertical-align:middle` have a dated feel vs. the refined rem-unit icons in newer sections
- Error pages are visually inconsistent — some are polished (500, 503), others have minimal standalone styles (400, 401, 403)
- Login pages have subtle visual divergence (gradient vs. flat on the right panel) that should be unified

---

## Suggested Fix Sequence

Work through these in order. Each phase is independently shippable.

---

### Phase 1 — Bug Fixes (1–2 hours, no visual risk)

These are silent failures that should be fixed immediately before any other work.

**1a. Fix broken `--student-primary` token** (`static/css/style.css`)

Either delete the three broken utility classes:
```css
/* DELETE these — --student-primary is undefined */
.bg-student { ... }
.text-student { ... }
.border-student { ... }
```
Or add the token to `tokens.css` in the `body.student-shell` block:
```css
--student-primary: #2F4F7F;
```

**1b. Add `--warning-text` token** (`static/css/tokens.css`)

Add to each role theme block (`:root`, `body.student-shell`, `body.sysadmin-shell`):
```css
--warning-text: color-mix(in srgb, var(--warning), black 20%);
```
Then update `style.css` line 1103:
```css
color: var(--warning-text);  /* remove the hardcoded #856404 fallback */
```

**1c. Fix `admin-insurance-advisor.css` hardcoded RGBA values**

Replace the two hardcoded rgba() values with token-based equivalents.

---

### Phase 2 — Icon Size System (2–3 hours, low risk)

Standardize the icon sizing before touching templates, so the classes exist to reference.

**2a. Add icon size utilities to `static/css/style.css`**

```css
/* ─── Icon Size Utilities ─── */
.icon-sm     { font-size: 1rem !important; }
.icon-md     { font-size: 1.5rem !important; }    /* 24px — default */
.icon-lg     { font-size: 2rem !important; }      /* 32px */
.icon-xl     { font-size: 3rem !important; }      /* 48px */
/* For icons embedded inline with text */
.icon-inline {
    font-size: 1.25rem !important;
    vertical-align: text-bottom !important;
}
```

**2b. Replace all 76 inline icon size attributes**

Search-replace pattern: `style="font-size:25pt; vertical-align:middle;"` → `class="icon-lg"`

Files to update (highest count first):
1. `admin_banking.html` — 4 instances
2. `admin_insurance.html` — 5 instances
3. `admin_issues_queue.html` — 5 instances
4. `admin_analytics_dashboard.html` — 4 instances
5. `admin_students.html` — many instances in accordion help panel
6. All remaining templates with any `font-size:Xpt` instances

---

### Phase 3 — Bootstrap Version Pinning (1 hour, low risk)

**3a. Update all 22 templates using Bootstrap 5.3.0 → 5.3.3**

Find all occurrences:
```bash
grep -rln 'bootstrap@5.3.0' templates/
```

Replace CDN URL in each:
```
https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css
→
https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css

https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js
→
https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js
```

**3b. Update the one template using 5.3.8 back to 5.3.3**

---

### Phase 4 — Login Layout Consolidation (2–3 hours, medium risk)

Extract the shared login layout into `style.css` so all auth pages reference the same implementation.

**4a. Add login layout component to `static/css/style.css`**

```css
/* ─── Auth / Login Layout ─── */
.login-layout {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background-color: var(--background);
}

.login-container {
    width: 100%;
    max-width: 900px;
    background: var(--surface);
    box-shadow: var(--shadow-lg);
    border-radius: var(--radius-sm);
    overflow: hidden;
    display: flex;
    min-height: 600px;
}

.login-panel-left {
    flex: 1;
    padding: 3rem;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.login-panel-right {
    flex: 1;
    background: linear-gradient(135deg, var(--primary), var(--primary-hover));
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: white;
    padding: 3rem;
    position: relative;
    overflow: hidden;
}

.login-panel-right::before {
    content: '';
    position: absolute;
    inset: 0;
    background: url("data:image/svg+xml,...");  /* extract SVG pattern here */
}

@media (max-width: 768px) {
    .login-container { flex-direction: column; min-height: unset; }
    .login-panel-right { display: none; }
}
```

**4b. Remove `<style>` blocks and update class names** in:
- `admin_login.html`
- `student_login.html`
- `admin_signup.html`
- `student_account_claim.html`

---

### Phase 5 — `student_setup_complete.html` Rebuild (1–2 hours, medium risk)

This page is isolated from the system. Rebuild it to use the design system properly.

**5a. Extend the student base layout** (or a minimal shared base)

**5b. Fix visual issues:**
- Replace `background: linear-gradient(135deg, var(--info)...)` with `var(--background)` or the student primary
- Replace `.btn-primary` gradient override with the standard system class (no override needed)
- Replace `border-radius: 16px` on card with `border-radius: var(--radius-lg)`
- Replace `font-size:50pt` icon with class `icon-xl` (after Phase 2)
- Replace `font-size:15pt` text with Bootstrap utility `fs-5` or a token-based class

---

### Phase 6 — Component Class Extraction (3–5 hours per component, ongoing)

Extract `<style>` block contents from high-traffic templates into `style.css`. Priority order:

| Template | Classes to extract | Why now |
|----------|--------------------|---------|
| `student_detail.html` | `.stat-value`, `.stat-label`, `.negative-balance`, `.positive-balance` | Stat cards used pattern-widely |
| `admin_insurance.html` | `#advancedInsuranceAccordion` styles | 157KB template, CSS should be external |
| `admin_analytics_dashboard.html` | Analytics-specific styles | Styles are at line 585, far from their context |
| `admin_students.html` | `.block-tab-content`, `.quick-action-btn` | Students page is a core admin view |
| `getting_started_widget.html` | Merge two style blocks → one external file | Widget has 741 lines of styles in two blocks |

For each: move styles to `style.css`, remove `<style>` block from template, verify no visual regression.

---

### Phase 7 — Sidebar Consolidation (3–4 hours, higher risk)

Unify the three sidebar implementations.

**7a. Extract shared sidebar structure to `style.css`**

```css
/* Shared structural rules for all sidebars */
.app-sidebar {
    width: var(--sidebar-width);
    position: fixed;
    top: 0; left: 0; bottom: 0;
    overflow-y: auto;
    z-index: 1000;
    transition: transform 0.3s ease;
    padding: 1.5rem;
    color: white;
}
```

**7b. Keep role-specific classes for color/accent only:**
- `.sidebar` → admin colors (inherits `.app-sidebar`)
- `.student-sidebar` → student colors
- `.sysadmin-sidebar` → sysadmin colors, `z-index: 1050`

**7c. Standardize layout approach** — pick either `margin-left` or `display: flex` and apply consistently. The sysadmin `display: flex` approach on body is cleaner for modern layouts.

---

### Phase 8 — Token Cleanup (1 hour, low risk)

**8a. Replace hardcoded colors in `style.css`** with token references:
- Lines 890: `#f5f5f3`/`#fafaf8` → `var(--neutral-100)`, `var(--neutral-50)`
- Line 882: `#ff6666` → `color-mix(in srgb, var(--danger) 120%, white)`
- Lines 756/760/764: Add comment documenting intentional Easter egg values

**8b. Update radius token comments** in `tokens.css` to match actual usage.

---

## Files Reference

| File | Role | Lines |
|------|------|-------|
| `static/css/tokens.css` | Design token source of truth | 197 |
| `static/css/style.css` | Core component styles | 1,378 |
| `static/css/admin-insurance-advisor.css` | Insurance advisor component | 38 |
| `templates/layout_admin.html` | Admin shell layout | — |
| `templates/layout_student.html` | Student shell layout | — |
| `templates/layout_system_admin.html` | Sysadmin shell layout | — |

---

*Audit conducted on branch `design-audit`. For questions, see the design token definitions in `static/css/tokens.css`.*
