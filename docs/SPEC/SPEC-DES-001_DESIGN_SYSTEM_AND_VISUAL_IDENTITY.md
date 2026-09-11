# SPEC-DES-001: Design System and Visual Identity

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SPEC-DES-001 | 2.0 | 2026-09-10 | `FEAT-DES-001` v1.1 (archived) | Normative |

> Supersedes `docs/archive/v1-docs/FEATURES/DESIGN/FEAT-DES-001_Design_System.md` (archived, non-normative). That document described the v1 token set and carries values that no longer match the implementation; it governs nothing and is retained as history only.

---

## I. Purpose

This specification defines the canonical visual identity of the Classroom Token Hub: the design token architecture, the role-theme model, the semantic usage rules that bind templates to tokens, and the conformance criteria by which a surface is judged to be on-system.

It exists so that visual consistency is a checkable contract rather than a matter of per-template taste, and so that a color, space, or type decision has exactly one place it can legitimately be made.

---

## II. Scope

Applies to:

- `static/css/tokens.css` — the token layer, and the sole source of truth for design values
- `static/css/style.css` — the component and utility layer
- `static/css/fonts.css` — the typeface layer
- all Jinja templates under `templates/`
- template-embedded `<style>` blocks and inline `style` attributes
- any CSS that affects rendered color, spacing, typography, elevation, or motion

Does not govern:

- page rendering structure, view models, or builder organization — governed by `SPEC-UI-001`
- accessibility requirements — governed by `INV-ARC-020`, which this document is subordinate to and must not weaken
- `github-pages/` and `docs-site/` — separately published artifacts. See §XIII.
- domain, mutation, or persistence authority

---

## III. Authority Level

Normative (Tier 2). Subordinate to `INV-CORE-000`, `INV-ARC-020`, and `INV-ARC-022`.

Per `SOP-DOC-000` §V, this specification is a technical contract. Its requirements bind implementation where incorporated by the applicable `INV-*` or `DOM-*` contract. Where a requirement here conflicts with `INV-ARC-020`, the invariant wins.

---

## IV. Dependencies

- `docs/INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-022_REQUEST_CONTEXT_AND_PAGE_RENDERING.md`
- `docs/SPEC/SPEC-UI-001_PAGE_RENDERING_SPECIFICATION.md`
- `docs/STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md`

---

## V. Design Philosophy

The interface serves three audiences from one codebase. A teacher administering an economy, a student participating in it, and a system administrator operating it are looking at the same structures with different stakes. The design system encodes that as **one layout vocabulary, three color identities**.

### 1. Core Principles

1. **Context-aware roles.** The same markup renders in the active role's identity. The role is carried by a single body class; nothing downstream re-decides it.

   | Role | Identity | Character |
   |---|---|---|
   | Teacher (default) | Advisor Green | Professional, authoritative, warm |
   | Student (`body.student-shell`) | Steward Blue | Trustworthy, calm, focused |
   | Sysadmin (`body.sysadmin-shell`) | Guardian Gray | Neutral, technical, high-contrast |

2. **Semantic over literal.** A template names the *role* a value plays, never the value itself. `var(--danger)`, not `#c0392b`.

3. **Minimal and flat.** Hierarchy comes from spacing, type weight, and restrained borders — not from heavy shadow or gradient. Elevation is reserved for genuine overlay.

4. **One definition per decision.** A design value is defined once, in the token layer. A value that appears literally in two places is drift that has not yet been noticed.

### 2. The Role-Theme Contract

Role theming is achieved **only** by token reassignment under a body class. Consequences that are binding:

- A template MUST NOT branch on role to pick a color, class, or asset.
- A component MUST NOT be duplicated per role.
- A role theme MUST define the complete theme-layer token set (§VI.3). A theme that omits a token inherits a value designed for a different identity, which is a defect, not a fallback.

---

## VI. Token Architecture

Tokens live in `static/css/tokens.css` in two layers.

### 1. Base Layer — role-agnostic

Defined on `:root`, identical in every role.

| Category | Tokens | Notes |
|---|---|---|
| Typeface | `--font-family`, `--font-display`, `--font-data` | Inter / Atkinson Hyperlegible Next / IBM Plex Mono |
| Type scale | `--text-2xs` … `--text-4xl`, `--leading-*`, `--weight-*` | §VI.2 |
| Spacing | `--space-0` … `--space-16` | §VI.2 |
| Radius | `--radius-xs` (2px), `--radius-sm` (4px), `--radius-md` (6px), `--radius-lg` (8px), `--radius-pill` (999px) | `sm` cards/inputs, `md` buttons, `lg` modals |
| Elevation | `--shadow-sm`, `--shadow-md`, `--shadow-lg` | Overlay only; not decoration |
| Motion | `--duration-fast/base/slow`, `--ease-standard` | §VI.2 |
| Opacity | `--alpha-subtle/soft/medium/strong` | §VI.2 |
| Icon size | `--icon-xs` … `--icon-2xl` | §VI.2 |
| Layout | `--sidebar-width`, `--bottom-nav-height`, `--breakpoint-*` | Structural, role-agnostic |
| Neutrals | `--neutral-50` … `--neutral-900` | Warm-tinted grayscale |
| Surfaces | `--background`, `--surface`, `--border-color` | `--background` is `--neutral-100` |
| Text | `--text-primary`, `--text-secondary`, `--text-muted`, `--text-inverse` | |
| Contrast-pinned text | `--accent-text-on-light`, `--alert-warning-text`, `--alert-danger-text`, `--alert-info-text`, `--text-on-dark-muted` | §VI.6 |

### 2. Required Scales

The v1 system defined color and radius but left spacing, typography, motion, opacity, and icon sizing untokenized. Measured cost at the time of this revision: 25 distinct font sizes, 19 spacing values, 20+ opacity values, and 6 transition durations hardcoded across `style.css`, plus ~180 inline `font-size` declarations on icons in templates. These scales are therefore normative.

**Spacing** — 4px base, geometric after `--space-4`:

`--space-0` 0 · `--space-1` 4px · `--space-2` 8px · `--space-3` 12px · `--space-4` 16px · `--space-5` 20px · `--space-6` 24px · `--space-8` 32px · `--space-10` 40px · `--space-12` 48px · `--space-16` 64px

**Type scale** — rem-based, 16px root:

`--text-2xs` 0.6875rem · `--text-xs` 0.75rem · `--text-sm` 0.875rem · `--text-base` 1rem · `--text-lg` 1.125rem · `--text-xl` 1.25rem · `--text-2xl` 1.5rem · `--text-3xl` 1.875rem · `--text-4xl` 2.5rem

Weights `--weight-normal` 400 · `--weight-medium` 500 · `--weight-semibold` 600 · `--weight-bold` 700.
Line heights `--leading-tight` 1.25 · `--leading-snug` 1.4 · `--leading-normal` 1.6.

**Motion** — `--duration-fast` 120ms · `--duration-base` 200ms · `--duration-slow` 300ms · `--ease-standard` `cubic-bezier(0.2, 0, 0.2, 1)`.

All motion MUST remain subject to the `prefers-reduced-motion` override in §XI.

**Opacity** — `--alpha-subtle` 0.08 · `--alpha-soft` 0.16 · `--alpha-medium` 0.35 · `--alpha-strong` 0.6.

**Icon size** — `--icon-xs` 1rem · `--icon-sm` 1.125rem · `--icon-md` 1.25rem · `--icon-lg` 1.5rem · `--icon-xl` 2rem · `--icon-2xl` 3rem.

Icon sizing MUST be applied through the `.icon-*` utility classes, never through an inline `font-size`.

### 3. Theme Layer — role-specific

Every role theme MUST define the following complete set. Absence is a defect.

| Token | Purpose |
|---|---|
| `--primary`, `--primary-hover`, `--primary-subtle` | Brand and main interaction |
| `--secondary`, `--secondary-hover`, `--secondary-text`, `--secondary-subtle` | Accent |
| `--accent` | Emphasis alias |
| `--success`, `--success-hover`, `--success-subtle` | Status |
| `--info`, `--info-hover`, `--info-subtle` | Status |
| `--warning`, `--warning-hover`, `--warning-subtle` | Status |
| `--danger`, `--danger-hover`, `--danger-subtle` | Status |
| `--bs-primary` … `--bs-danger` | Bootstrap bridge (§VII) |
| `--bs-primary-rgb` … `--bs-danger-rgb` | Bootstrap bridge (§VII) |

### 4. Canonical Brand Values

These are the authoritative values. Where any other artifact disagrees, that artifact is wrong.

| Token | Teacher | Student | Sysadmin |
|---|---|---|---|
| `--primary` | `#1a4d47` | `#2F4F7F` | `#303030` |
| `--primary-hover` | `#15403b` | `#253f66` | `#1a1a1a` |
| `--primary-subtle` | `#e8f0ef` | `#e8edf4` | `#e8e8e8` |
| `--secondary` | `#D4A857` | `#D4A857` | `#D4A857` |
| `--secondary-text` | `--neutral-900` | `--text-inverse` | `--neutral-900` |

> **Naming note.** v1 documented the teacher accent as `#d3af37` and the student accent as bronze `#ac8255`. The implementation has since converged all three roles on a single gold `#D4A857`. The v1 values are superseded. The student theme retains a brown `--secondary-hover` and a warm `--secondary-subtle` from the bronze era; this is a deliberate carry-over, not drift, but the label "Bronze" no longer describes the base accent.

### 5. Adding a Token

1. Role-agnostic? Add to `:root`.
2. Role-dependent? Add to **all three** theme blocks (§VI.3).
3. Name it `--{category}-{property}-{modifier}` — e.g. `--chart-primary-fill`.
4. A token whose value is a literal duplicate of an existing token MUST instead alias it.
5. Name a token for the surface it is legible on, not for the first page that used it.

### 6. Contrast-Pinned Text Tokens

A brand token and a *legible text* token are not the same thing. A role theme is free to pick any `--secondary-hover` that reads well as a button fill; that same value is usually unusable as body text on white. Where the two requirements collide, the text value MUST be pinned in a separate role-agnostic token rather than inherited from the theme.

| Token | Pinned against | Why the theme token fails |
|---|---|---|
| `--accent-text-on-light` `#735816` | `--surface` / white | Sysadmin `--secondary-hover` `#c09840` is 2.69:1 — fails even the 3:1 large-text threshold. Pinned value is 6.70:1. |
| `--alert-warning-text` `#5f3d00` | `--warning-subtle` | `--warning` `#D4A857` is a fill, not a text color |
| `--alert-danger-text` `#8f1f1f` | `--danger-subtle` | ditto |
| `--alert-info-text` `#1f4f73` | `--info-subtle` | ditto |
| `--text-on-dark-muted` `#DEDEDE` | Dark hero / sidebar | The neutral ramp is tuned for dark-on-light and inverts poorly |

These are deliberately **not** per-role. A per-role definition would reintroduce exactly the failure it exists to prevent: the theme picking a value that happens to fail in one role only, silently, on one page.

A decorative, `aria-hidden` icon is exempt and MAY use the theme token directly.

---

## VII. The Bootstrap Bridge

Bootstrap is themed by remapping its variables onto project tokens. Two rules are binding because both have been violated in practice:

1. **RGB parity.** Every `--bs-*-rgb` MUST be the decimal decomposition of the hex its matching `--bs-*` token resolves to. These drift silently: nothing errors when they disagree, the UI just renders a stale color in any `rgba()` context.

2. **Bridge completeness.** A theme that defines `--bs-secondary` but omits `--bs-secondary-rgb` will fail silently wherever a component composes `rgba(var(--bs-secondary-rgb), α)` — the declaration is invalid and the property falls back. Every theme MUST define the full RGB set.

Per `INV-ARC-020` §IX.4, Bootstrap defaults MUST NOT be assumed to satisfy contrast once combined with project tokens.

---

## VIII. Semantic Usage Rules

### 1. Backgrounds

Use the subtle tokens for containers, alerts, and sections. Opacity hacks are prohibited.

| Use case | Correct | Prohibited |
|---|---|---|
| Page background | `var(--background)` | `#f5f5f3`, `bg-light` |
| Card surface | `bg-surface` | `bg-white` |
| Success alert | `bg-success-subtle` | `bg-success bg-opacity-10` |
| Primary container | `bg-primary` | `style="background-color: {{ theme_color }}"` |

### 2. Text

| Use case | Class / token |
|---|---|
| Primary action | `text-primary` |
| Body | `text-body` / `var(--text-primary)` |
| Muted / meta | `text-muted` / `var(--text-secondary)` |
| Numeric / ledger data | `var(--font-data)` |

### 3. Buttons

Standard Bootstrap buttons, themed by the bridge. `.btn-primary`, `.btn-secondary`, `.btn-danger` MUST resolve their colors from `--primary` / `--secondary` / `--danger`. A component rule that hardcodes a color defeats the theme it sits inside.

### 4. Icons

Material Symbols Outlined only. No Bootstrap Icons, no Font Awesome. Size via `.icon-*` (§VI.2).

Per `INV-ARC-020` §VII.B, an icon-only control requires an `aria-label`.

### 5. Borders

`border` uses `--border-color`. For semantic emphasis use `border-primary`, `border-danger`.

---

## IX. Template Contract

Templates render tokens; they do not define design values.

A template MUST NOT contain:

1. A hardcoded color in any form — hex, `rgb()`, `hsl()`, or a named CSS color — in markup, in a `<style>` block, or in template-embedded JavaScript.
2. An inline `style` attribute carrying a **static** presentational value. Static means the declaration is identical on every render.
3. A `<style>` block whose rules are not specific to that single page.
4. A role conditional that selects styling (§V.2).

A template MAY contain:

1. An inline `style` attribute whose value is **computed per render** — e.g. `style="width: {{ pct }}%"` on a progress bar. This is the legitimate use of the attribute and is not a violation. The dynamic portion MUST still reference tokens for any non-computed part.
2. A page-scoped `<style>` block for genuinely single-use layout, provided every value in it resolves to a token.

### Shared-surface rule

CSS repeated across templates MUST be promoted to `style.css`. At the time of this revision the error pages, login pages, and recovery pages each carried near-identical duplicated blocks. Duplicated presentation is drift with a delay: the copies diverge on the first edit that does not touch all of them.

### The brand mark

The brand is **text**, not an image. It is the three-row wordmark — `CLASSROOM` / `TOKEN` / `HUB`, each row prefixed by its Material Symbol (`local_atm`, `store`, `finance_mode`) — stacked vertically and rendered from a macro, never transcribed inline.

A raster or vector logo file MUST NOT be used to represent the brand on any public page. Image logos cannot take the role theme, cannot be recolored by a token, and cannot be read by a screen reader without a redundant `alt` string. The wordmark satisfies all three by construction.

Two macros render it, and a third surface MUST reuse one rather than add a fourth:

| Surface | Macro / class | Layout |
|---|---|---|
| Landing and docs heroes | `macros/docs_hero.html` → `.landing-brand` | Vertical stack, gold rule on the trailing edge |
| Auth shell (sign-in, sign-up, recovery) | `macros/auth_brand.html` → `.auth-brand` | Vertical stack in a full-width band |

### The auth shell

Sign-in, sign-up, and recovery pages use one stacked layout: the brand band on top, the interactive panel (`.auth-body`) beneath. A two-column split that places the brand beside the form is prohibited — it forces the brand to be dropped entirely at narrow widths, which is what the prior `@media (max-width: 768px) { .login-right { display: none } }` rule did on all fourteen pages.

The band's fill is `var(--primary)`, so the role theme carried on `<body>` selects it with no per-page override and no role conditional (§V.2). Wordmark text is `var(--text-inverse)`; the leading icons are `var(--secondary)` and are decorative (`aria-hidden="true"`), per §VIII.4.

---

## X. Anti-Patterns

**Hardcoded color**
```html
<!-- Prohibited -->
<div style="background-color: #1a4d47; color: white;">…</div>
<!-- Required -->
<div class="bg-primary text-white">…</div>
```

**Opacity hack**
```html
<!-- Prohibited: Bootstrap's opacity is inconsistent across themes -->
<div class="bg-success bg-opacity-25">…</div>
<!-- Required -->
<div class="bg-success-subtle">…</div>
```

**Role branching**
```html
<!-- Prohibited -->
{% if role == 'student' %}<div class="bg-blue-800">{% else %}<div class="bg-teal-900">{% endif %}
<!-- Required: let the theme layer resolve it -->
<div class="bg-primary">…</div>
```

**Inline icon sizing**
```html
<!-- Prohibited -->
<span class="material-symbols-outlined" style="font-size: 1.25rem">settings</span>
<!-- Required -->
<span class="material-symbols-outlined icon-md">settings</span>
```

**Token whose value restates another token**
```css
/* Prohibited: will not follow --primary when it changes */
--sysadmin-primary: #303030;
/* Required */
--sysadmin-primary: var(--primary);
```

---

## XI. Accessibility Bindings

`INV-ARC-020` governs. This section records only where the design system carries specific obligations.

1. **Contrast is a token property.** Any token pair intended to be composed as foreground-on-background MUST meet WCAG 2.1 AA in its rendered state, in every role theme. `--secondary` is the highest-risk token: at `#D4A857` it requires dark foreground, which is why `--secondary-text` exists and why it differs by role.
2. **Never color alone.** A state communicated by a status token MUST also carry text, icon, or shape.
3. **Focus is not optional.** Focus-visible styling is part of the system, not a per-component decision.
4. **Reduced motion.** Every token in the motion scale is subject to the global `prefers-reduced-motion: reduce` override.
5. **Forced colors.** `forced-colors: active` support MUST be preserved when component styling changes.

---

## XII. Conformance

A surface conforms when:

- no design value is expressed literally; every one resolves through a token
- no template carries a hardcoded color, in markup, `<style>`, or script
- every inline `style` attribute is per-render computed
- role identity is carried solely by the body class
- every role theme defines the complete theme-layer token set, with RGB parity
- icon sizing uses `.icon-*` utilities
- `INV-ARC-020` §VI baseline is preserved

The token layer conforms when:

- no `--bs-*-rgb` disagrees with its paired token
- no theme omits a theme-layer token another theme defines
- no token restates another token's literal value
- `style.css` contains no raw color outside a token definition

---

## XIII. Separately Published Artifacts

`github-pages/` and `docs-site/` maintain their own stylesheets and are outside the runtime token layer. They are nonetheless **brand surfaces** and MUST NOT contradict §VI.4.

At the time of this revision `github-pages/style.css` defines `--secondary: #d3af37` and `--primary-color: #236960`, neither of which matches the canonical values. That is a live brand split on the public site. Reconciling it is tracked work; until reconciled, §VI.4 is the authority and the published site is the artifact that is wrong.

---

## XIV. Enforcement

Design-system conformance is mechanically checkable and SHOULD be gated rather than reviewed by eye. The checkable rules:

1. No hex/`rgb()`/`hsl()` literal under `templates/`.
2. No raw color in `style.css` outside a token definition block.
3. `--bs-*-rgb` parity with its paired token.
4. Theme-layer token set completeness across all three role blocks.
5. No inline `style` attribute lacking a Jinja expression.

Per `INV-ARC-020` §VIII.4, any change to `static/css/` affecting rendered color, spacing, display state, or focus styling is a high-risk change class and carries the accessibility validation obligation in `INV-ARC-020` §X.

---

## XV. Amendment

Revisions MUST:

1. Increment the version and update the effective date.
2. Preserve the role-theme contract (§V.2) and the token-layer single-source rule.
3. Preserve or strengthen `INV-ARC-020` obligations; a revision MUST NOT weaken them.
4. Update §VI.4 when a canonical brand value changes, and state what the prior value was.
