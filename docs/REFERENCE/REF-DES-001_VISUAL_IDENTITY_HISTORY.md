# REF-DES-001: Visual Identity History

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| REF-DES-001 | 1.0 | 2026-09-20 | None | Informative — historical reference |

## I. Purpose

Preserve the repository-supported history of Classroom Token Hub's visual identity: its name and positioning, role colors, logos and text wordmarks, fonts, layouts, components, public website, and developer documentation. This reference combines the role-color investigation with the broader visual-history investigation, including predecessor names, literal values, reversals, recorded reasons, and unresolved questions.

## II. Scope and Evidence

The investigation covers the initial commit of April 9, 2025 through the repository snapshot at **`61d5e78dc287bca68ebc6af05d588289e2635df8`**, inspected on September 20, 2026. It covers the material transitions found in Git, not every individual spacing or page-copy edit.

Evidence consists of commit messages, changes to templates and stylesheets, historical design documents, and inspection of retained logo artwork. Searches followed literal colors and predecessor names as well as current token names, across available Git refs in a non-shallow checkout. Source commits and consolidated commits can describe overlapping work; they are not separate releases merely because both exist.

The following distinctions apply throughout:

- **Implementation evidence:** a value, declaration, asset, or structure exists in a particular revision. This does not establish when it was deployed.
- **Documented reason:** a commit message or contemporaneous document explicitly explains the change. Statements about comfort or accessibility are attributed intentions unless independently verified.
- **Inference:** an interpretation of the sequence, identified as such rather than presented as original intent.
- **Unknown:** the examined history does not establish the answer. Absence from the available history is not proof that no discussion occurred elsewhere.

Dates are the dates recorded on cited commits, whose offsets vary. For example, the first December teal redesign is dated December 13 in UTC, equivalent to December 12 in Pacific time. Branch author dates do not necessarily establish merge order, first production use, or release dates. Historical font imports and CSS declarations are not equivalent to browser-rendered font or color evidence.

## III. Authority Level

**Informative only.** This document records history; it neither defines a new design system nor authorizes restoration of superseded styling. The current visual contract is [SPEC-DES-001](../SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md), subordinate to the applicable invariants. No domain mutation or FEAT implementation is introduced by this reference.

The archived `FEAT-DES-001` is historical evidence only, superseded by `SPEC-DES-001`. The original February design reference is cited at its historical Git revision, not as current authority. Retained image files likewise do not authorize their use under today's text-brand contract.

## IV. Related Current Documents

- [INV-CORE-000 — Core Invariants](../INVARIANT/CORE/INV-CORE-000_CORE_INVARIANTS.md)
- [INV-ARC-020 — Accessibility Requirements and Template Contract](../INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md)
- [INV-ARC-022 — Request Context and Page Rendering Pipeline](../INVARIANT/ARCHITECTURE/INV-ARC-022_REQUEST_CONTEXT_AND_PAGE_RENDERING.md)
- [SPEC-DES-001 — Design System and Visual Identity](../SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md)
- [SOP-DOC-000 — Documentation Standard](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)
- [SOP-DOC-001 — Documentation Index](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md)

## V. Historical Overview

The durable role primaries formed in December 2025. Their current names arrived in February 2026. The typography system formed in stages during July and August 2026, and September consolidated the implementation and its written contract.

| Period | Main visual direction | Important qualification |
|---|---|---|
| April–July 2025 | Bootstrap pages, individually styled account panels, Inter and then Noto families | Inter existed from the first commit; no single global identity yet |
| November 2025 | Separate dark sysadmin surface, then logo-led blue/cyan/gold styling with gradients and motion | Student bright-blue styling preceded Dark Slate Blue |
| December 2025 | Softer teal, distinct student slate blue, sysadmin gray, text/icon wordmark and PNG role logos | Today's primaries existed before today's theme names |
| February 2026 | Named role themes, shared tokens, warm neutrals, smaller radii | The layout revamp was partly rolled back while the token system survived |
| Spring–June 2026 | Public-site and docs-site experiments, contrast corrections, revised positioning | Public palette alignment was reversed and only partially restored |
| July–August 2026 | Inter / Atkinson / IBM Plex Mono, shared gold, local font hosting | Token introduction preceded the app's global heading adoption |
| September 2026 | Normative visual specification, shared auth wordmark, token enforcement, titled alert cards, cross-site reconciliation | Historical declarations and reported rendered results must remain distinct |

## VI. Detailed Chronology

### 1. April 2025 — An Individually Styled Classroom Utility

The [initial commit, `eab217571`](https://github.com/timwonderer/classroom-token-hub/commit/eab217571), dated April 9, used names including **My 107 Economy**, **107 Classroom Economy**, and **Classroom Economy**. Dashboards used Bootstrap; account setup and TOTP pages included their own CSS.

The setup page imported **Inter**, used a pale `#f4f7fa` background and white panel, `#333` body text, a 10px panel radius, a light shadow, and blue buttons `#007BFF` with hover `#0056b3`. Inter therefore did not originate with the November redesign. At this stage its presence on setup pages did not imply that every page used it.

The repository does not explain the original font selection or establish a single founding visual-design brief.

### 2. June–July 2025 — Reusable Layouts, Noto, and the CTH Name

June brought a reusable teacher sidebar layout. [June 15, `1b069431c`](https://github.com/timwonderer/classroom-token-hub/commit/1b069431c), added **Noto Sans** to the admin layout; [June 16, `365eb3381`](https://github.com/timwonderer/classroom-token-hub/commit/365eb3381), adjusted its loading and shared layout.

By [July 2, `de0182f86`](https://github.com/timwonderer/classroom-token-hub/commit/de0182f86), the student login displayed **Classroom Token Hub** and used Noto Sans. A dark teal authentication background, `rgb(5, 57, 54)` or `#053936`, appeared in this period. [July 4, `e337fd500`](https://github.com/timwonderer/classroom-token-hub/commit/e337fd500), introduced a shared base with **Noto Sans** for text and **Noto Sans Mono** for code, a white centered card, and the same teal background.

This is an early teal use, but not evidence that Advisor Green already existed: its value and its purpose differed from the later teacher primary. The precise motivation for the product-name change was not found.

### 3. November 16, 2025 — First Explicit Separate Role Palette Found

Teacher and student layouts used **primary blue `#4A7BA7`**, lighter blues `#6BA3D0` and `#81B9D8`, dark navigation `#2B3E50`, teal/green status colors `#4A9B8E` and `#6DB665`, and gold `#E8B856`.

[`f59c7f818`, PR #136](https://github.com/timwonderer/classroom-token-hub/commit/f59c7f818), created the separate sysadmin layout with a **Dark System Admin Theme**:

| Use | Literal value |
|---|---|
| Primary buttons (`--primary-purple`) | `#6f42c1` |
| Dark primary | `#1a1a2e` |
| Page background | `#0f0f1e` |
| Sidebar | `#16213e` |
| Cyan accent | `#00d4ff` |

The message describes a professional dark purple/cyan scheme and a full-width layout with organized sidebar navigation. This is the earliest explicit separate role palette found, not the origin of the present green/blue/gray trio. It does not provide a complete rationale for why those exact colors were selected.

### 4. November 19–24, 2025 — A Logo-Led Blue/Cyan Brand

[`ec66e4b29`, PR #213](https://github.com/timwonderer/classroom-token-hub/commit/ec66e4b29), added four SVG assets: `brand-logo.svg`, `student-logo.svg`, `admin-logo.svg`, and `sys-admin-logo.svg`. The commit explicitly derived the new palette from the logo:

| Name in the redesign | Value |
|---|---|
| Brand primary / deep blue | `#274174` |
| Cyan | `#00afdf` |
| Gold | `#fdb034` |
| Rich blue | `#035397` |
| Deep teal | `#005e77` |

The design used Inter, geometric cards, rounded controls, gradient sidebars and buttons, shadows, glowing active navigation, and hover movement. The message describes Inter as modern, clean typography. Student chrome was friendly and lighter; sysadmin chrome was darker for a secure, authoritative feel. These are documented descriptions of that redesign.

[`d445e90fd`, PR #214](https://github.com/timwonderer/classroom-token-hub/commit/d445e90fd), corrected logo contrast and proportions: white-inverted logos on gradients, smaller marks, less duplicate brand text, and more compact navigation. It also replaced sysadmin Bootstrap Icons with **Google Material Symbols**.

Later on November 19, [`31d060085`, PR #227](https://github.com/timwonderer/classroom-token-hub/commit/31d060085), brightened student surfaces. Sidebar and title gradients became `#4a9eff` to `#00afdf`; primary-button gradients used `#00d4ff` to `#00afdf`; the background became a pale sky-blue gradient. This was a distinct student treatment while the shared brand variables still existed.

Typography did not settle immediately. [November 20, `ad9cceb89`](https://github.com/timwonderer/classroom-token-hub/commit/ad9cceb89), declared **IBM Plex Sans** on student login, and [`5848c909e`](https://github.com/timwonderer/classroom-token-hub/commit/5848c909e) used it on account claim. Subsequent edits changed these declarations. [November 24, `5a414df8e`](https://github.com/timwonderer/classroom-token-hub/commit/5a414df8e), standardized authentication layouts but included Noto Sans imports alongside Inter declarations on some pages. Those mismatches prevent a reliable rendered-font claim from imports alone.

### 5. December 8–14, 2025 — Less Motion and the Teacher/Student Split

[December 8, `0666a23b4`](https://github.com/timwonderer/classroom-token-hub/commit/0666a23b4), removed card-hover transforms and shadow effects across many templates, explicitly seeking a consistent experience without hover animation. Shared card-hover removal continued in the December 21 sysadmin work.

[`d41acfb31`](https://github.com/timwonderer/classroom-token-hub/commit/d41acfb31), dated December 13 UTC, introduced a modern teal/gold redesign. [`b14756780`](https://github.com/timwonderer/classroom-token-hub/commit/b14756780) softened it later that day:

| Element | Initial redesign | Softened palette |
|---|---|---|
| Primary teal | `#003530` | `#1a4d47` |
| Secondary gold | `#f6c344` | `#d4a574` |
| Page background | `#fdfbf7` | `#f5f5f3` |
| Card surface | `#ffffff` | `#fafaf8` |
| Text | `#1a1a1a` | `#2c2c2c` |

The softening message explicitly cites harsh colors, eye strain, and extended-use comfort. It calls the result more professional and sophisticated. Its accessibility language is an attributed claim, not proof of contrast conformance.

[December 14, `78cdee9fd`, PR #635](https://github.com/timwonderer/classroom-token-hub/commit/78cdee9fd), introduced **Student Theme — Dark Slate Blue**, scoped to `body.student-shell` and `body.student-theme`:

- Primary: `#2F4F7F`; initial hover: `#3F5F8F`.
- Secondary: warm coral `#E89B6D`.
- Background: light blue-gray `#F4F6F9`.
- Teacher retained green `#1a4d47`, amber `#d4a574`, and background `#f5f5f3`.

**The reason is explicit:** the commit calls for distinct visual identities and says the change improves UX by preventing confusion about which role is logged in. This is direct evidence for the December teacher/student split, not an inferred color-psychology explanation.

The same revision already contains a three-row student-sidebar wordmark: **Classroom / Token / Hub**, accompanied by `local_atm`, `store`, and `finance_mode`. September 2026 standardized an existing motif rather than inventing it.

### 6. December 17–28, 2025 — PWA Assets, Role Logos, Gray, and Secondary Colors

[December 17, `6f105d9b6`, PR #671](https://github.com/timwonderer/classroom-token-hub/commit/6f105d9b6), added PWA support and PNG install icons. The manifest used background `#f5f5f3` and theme color `#1a4d47`. [December 18, `bfb703605`](https://github.com/timwonderer/classroom-token-hub/commit/bfb703605), added teacher/student PNG icon variants.

[December 20, `ac878d450`, PR #686](https://github.com/timwonderer/classroom-token-hub/commit/ac878d450), removed the four SVG files and added transparent role PNGs and sysadmin logo variants. The retained artwork shows stacked **CLASSROOM / TOKEN / HUB**, money/store/growth icons, role labels, and the tagline **Classroom Economy System, Reimagined.** The exact font family embedded in those raster assets was not established. Authentication pages used large image-brand panels beside forms.

That revision also changed the teacher's amber secondary and student's coral secondary to bronze `#ac8255`, and moved the student background to warm `#f5f5f3`.

[December 21, `c0f0fd9fb`, PR #703](https://github.com/timwonderer/classroom-token-hub/commit/c0f0fd9fb), established **System Admin Theme — Dark Gray**: primary `#303030`, darker primary `#1a1a1a`, sidebar `#2C2C2C`, gold accent `#D4A857`, and bright accent `#FDB034`. Its consolidated message records an initial gold-primary proposal followed by a correction to gray **to match the sysadmin logo**. That intermediate proposal is not proof of a separately deployed gold-primary release.

By this point all three present-day role primaries existed. [December 26, `c27a9c8e2`](https://github.com/timwonderer/classroom-token-hub/commit/c27a9c8e2), changed the teacher secondary from bronze to `#D3AF37`; [January 3, `a7bcff5fb`](https://github.com/timwonderer/classroom-token-hub/commit/a7bcff5fb), changed its spelling to lowercase `#d3af37`, not its color.

The [December 26 UI overhaul, `62a8d0158`](https://github.com/timwonderer/classroom-token-hub/commit/62a8d0158), also records personalized greetings, side-by-side account cards, and accordion-style teacher navigation. These were layout/usability changes around the established palette, not a replacement of its primaries.

[December 28, `3faac2093`](https://github.com/timwonderer/classroom-token-hub/commit/3faac2093), used **Google Sans Code** on error surfaces, alongside existing generic monospace and Courier New uses. Google Sans was also requested in the font URL; that alone does not establish where it rendered. Error pages moved away from individually colored gradient backgrounds toward Inter and shared surfaces.

### 7. December 2025–January 2026 — The Public Website's Parallel Identity

The [initial December 22 landing-page source, `03f3f8d86`](https://github.com/timwonderer/classroom-token-hub/commit/03f3f8d86), used blue `#2563eb`, dark blue `#1e40af`, green `#10b981`, amber `#f59e0b`, and a system sans-serif stack. A [same-day revision, `5aa52c737`](https://github.com/timwonderer/classroom-token-hub/commit/5aa52c737), adopted Inter and Material Symbols, changed primary teal to `#236960`, dark teal to `#1a4742`, secondary bronze to `#ac8255`, accent to `#c49564`, and background to `#f5f5f3`.

This related-but-different public palette became a long-lived source of divergence from the app's `#1a4d47`. The public pages and assets were subsequently reorganized; historical source paths are not necessarily present-day paths. Source revisions should not be mistaken for independent deployment events.

### 8. February 17–18, 2026 — Named Themes and a Partial Layout Rollback

[`c3fdbf60f`](https://github.com/timwonderer/classroom-token-hub/commit/c3fdbf60f), dated February 17, introduced `static/css/tokens.css`, a shared base/theme architecture, and the current identity names. The [original design reference at that revision](https://github.com/timwonderer/classroom-token-hub/blob/c3fdbf60f/docs/development/design_system.md) is historical, superseded evidence, not current authority.

| Role | Identity | Primary | Secondary at introduction | Documented character |
|---|---|---|---|---|
| Teacher | Advisor Green | `#1a4d47` | `#d3af37` gold | Professional, authoritative, warm |
| Student | Steward Blue | `#2F4F7F` | `#ac8255` bronze | Trustworthy, calm, focused |
| Sysadmin | Guardian Gray | `#303030` | `#D4A857` gold | Neutral, technical, high-contrast |

The primary values were preserved. Hover values became `#15403b`, `#253f66`, and `#1a1a1a`, respectively. Shared warm neutrals, semantic colors, a 4px card radius and 6px control radius expressed a stated minimal, flat design. Inter remained the body font. The documentation says the semantic role system maintains consistency across three roles in one codebase; the descriptive character labels are evidence from February, not proof of the original November motivation.

The rollout included [PR #989, `7756f6c28`](https://github.com/timwonderer/classroom-token-hub/commit/7756f6c28). On February 18, [PR #990, `ab1f480b4`](https://github.com/timwonderer/classroom-token-hub/commit/ab1f480b4), explicitly restored fixed-sidebar layouts after the Bootstrap-grid revamp broke formatting. It retained tokens, Material Symbols, and role-aware themes. Its additional card-border/shadow corrections also show that the stated flat philosophy did not instantly eliminate every elevated card treatment.

### 9. April–June 2026 — Public and Documentation Experiments

[April 21, `eb724870d`](https://github.com/timwonderer/classroom-token-hub/commit/eb724870d), introduced developer-site CSS declaring teal `#0f6b6f`, creams `#fcfaf5` and `#fffaf0`, **Avenir Next** body text and **Georgia** headings, with system fallbacks and gradient treatment. These are declared styles; font availability and actual rendering were not reconstructed.

[May 23, `c12d825df`](https://github.com/timwonderer/classroom-token-hub/commit/c12d825df), introduced a public landing-page text-wordmark composition using **Classroom / Token / Hub** with `local_atm`, `storefront`, and `monitoring`. This was an intermediate glyph set; the later canonical mark uses `store` and `finance_mode`.

[June 13, `4813f1619`](https://github.com/timwonderer/classroom-token-hub/commit/4813f1619), darkened secondary/muted text from neutral-500 to neutral-600 and adjusted information colors: teacher/sysadmin `#3b7daa` to `#35719a`, student `#4a7fb3` to `#356a9e`. The commit explicitly framed these as WCAG-oriented contrast changes. It is not a blanket certification of all surfaces.

[June 15, `6a0e14c00`](https://github.com/timwonderer/classroom-token-hub/commit/6a0e14c00), changed product positioning from an educational banking simulation for financial literacy to a classroom-management platform using a simulated token economy to drive engagement and participation. This is a documented messaging decision, not evidence that the earlier colors were selected for that later framing.

[June 21, `ccb3796a7`](https://github.com/timwonderer/classroom-token-hub/commit/ccb3796a7), darkened teacher/student secondaries to `#8a6a1c` and `#8a643f`.

June 30 public-site changes were not a straight convergence:

1. [`16697d8fa`](https://github.com/timwonderer/classroom-token-hub/commit/16697d8fa) aligned values with the app, including green `#1a4d47`, gray `#303030`, and blue `#2F4F7F`.
2. [`3869540fa`](https://github.com/timwonderer/classroom-token-hub/commit/3869540fa) restored the divergent public palette, including green `#236960`, bronze `#ac8255`, gray `#4b5563`, and blue `#253f66`.
3. [`6c0678f87`](https://github.com/timwonderer/classroom-token-hub/commit/6c0678f87) restored canonical tokens alongside old literal aliases. Different selectors could still consume different greens.

### 10. July–August 2026 — Three Typography Roles and Local Hosting

[July 15, `f5fbfba5f`](https://github.com/timwonderer/classroom-token-hub/commit/f5fbfba5f), changed developer-site declarations to Inter, an Advisor-like palette, 12px radii, gradients, and a separate dark theme. September's investigation later found that the custom palette had lost to Infima specificity; the declarations cannot be treated as proof that the intended colors rendered.

[July 31, `13b508807`, PR #1289](https://github.com/timwonderer/classroom-token-hub/commit/13b508807), added:

- `--font-display`: **Atkinson Hyperlegible Next**.
- `--font-data`: **IBM Plex Mono**.
- Explicit data-font use on several credential and error surfaces, replacing assorted monospace declarations.

The public heading rule adopted Atkinson in [`a141f8d53`](https://github.com/timwonderer/classroom-token-hub/commit/a141f8d53). The app's global heading rule did not consume `--font-display` until [August 15, `e7486e7a1`](https://github.com/timwonderer/classroom-token-hub/commit/e7486e7a1). The latter also simplified font fallbacks and unified teacher/student secondaries with sysadmin gold **`#D4A857`**.

The font-selection commit describes the work as “font combination exploration.” The investigation found no fuller explanation establishing why those exact families were chosen. The code proves their roles; a selection rationale based on legibility, personality, or accessibility would remain inference without further evidence.

[August 16, `03c39f560`](https://github.com/timwonderer/classroom-token-hub/commit/03c39f560), made warning fills gold and distinguished prominent top-level card headings from calmer nested/alert headings.

[August 29, `608ef5dfc`](https://github.com/timwonderer/classroom-token-hub/commit/608ef5dfc), vendored Inter, Atkinson Hyperlegible Next, IBM Plex Mono, and Material Symbols as local WOFF2 files and introduced `fonts.css`. The actual replacement of external font links in 32 templates followed in [`2035a476c`](https://github.com/timwonderer/classroom-token-hub/commit/2035a476c). The documented goal was to remove the runtime Google Fonts dependency. Attribution to both changes avoids treating the first commit's message as proof that all template edits were already present.

### 11. September 2026 — Shared Brand, Enforced Tokens, and Cross-Site Reconciliation

[September 10, `45c050846`](https://github.com/timwonderer/classroom-token-hub/commit/45c050846), introduced the live `SPEC-DES-001` and replaced fourteen duplicated form-left/logo-right authentication layouts with one stacked composition: role-colored text-brand band above the form. Its documented reason is concrete: the old image panel was hidden below 768px, so the brand disappeared on phones.

The wordmark became a shared macro, using **CLASSROOM / TOKEN / HUB** with `local_atm`, `store`, and `finance_mode`. The specification explains the move to live text in terms of role-color inheritance, token-driven recoloring, and accessibility. Existing image assets remained historical assets; the new contract did not require their deletion to prohibit their use as the public brand.

[`613c91385`](https://github.com/timwonderer/classroom-token-hub/commit/613c91385) distinguished gold fills from readable text, standardized secondary hover to `#c09840`, and gave student gold buttons dark text. The dark accent-text token `#735816` serves light surfaces; the gold itself is not a general-purpose text color.

[September 11, `52d539ee8`](https://github.com/timwonderer/classroom-token-hub/commit/52d539ee8), centralized repeated styling and introduced token-contract enforcement. Its recorded audit reported 1,156 violations in 72 of 103 templates; those figures describe that audit, not a fresh count in this investigation.

[September 17, `bfd950109`](https://github.com/timwonderer/classroom-token-hub/commit/bfd950109), replaced inline rounded Bootstrap alert boxes with cards carrying semantic borders, icon/title headers, and explanatory bodies. Toasts were unchanged. [`17b503be0`](https://github.com/timwonderer/classroom-token-hub/commit/17b503be0) then tied alert borders to role tokens rather than Bootstrap's palette.

[September 19, `834182d60`](https://github.com/timwonderer/classroom-token-hub/commit/834182d60), brought developer docs into the canonical identity: default Advisor Green, the three self-hosted fonts, a text-wordmark hero, restrained radii, and flat resting surfaces. The message records that Infima specificity had left stock blue visible despite prior custom declarations. It also disabled the unsupported dark theme; all three canonical role identities are light themes, even though their navigation or brand bands are dark.

[`bb2a7d8ff`](https://github.com/timwonderer/classroom-token-hub/commit/bb2a7d8ff) closed the public-site split by making old names such as `--primary-color` reference canonical tokens instead of retaining `#236960`. It likewise replaced old bronze/gold aliases and corrected table-of-contents hover text. The commit reports assembled-artifact verification; this history did not independently repeat that deployment or browser check.

## VII. Color Lineages

### Primary Identities

| Surface | Predecessors | Durable identity | Current name introduced |
|---|---|---|---|
| Teacher | Muted blue `#4A7BA7`; logo-led blue palette; shared teal `#003530` | Softened teal `#1a4d47`, December 13, 2025 | Advisor Green, February 17, 2026 |
| Student | Shared muted blue; logo-led blue; bright `#4a9eff`/`#00afdf`/`#00d4ff`; shared teal redesign | Dark Slate Blue `#2F4F7F`, December 14, 2025 | Steward Blue, February 17, 2026 |
| Sysadmin | Purple `#6f42c1` on dark navy; dark logo-led blue treatment | Dark Gray `#303030`, December 21, 2025 | Guardian Gray, February 17, 2026 |

These are surface/theme lineages, not a claim that every historical sidebar, button, and background used one uniform primary value.

**Dark Slate Blue is a proven ancestor of Steward Blue:** the December CSS and February tokens both assign `#2F4F7F` to the student primary. The latter still describes it as Dark Slate Blue. This is a naming and systematization change, not a new primary hue. By contrast, the CSS named color **`DarkSlateBlue` / `darkslateblue` is `#483D8B`**. The investigation did not establish application-theme ancestry for that different value.

### Secondary Colors

| Date / change | Teacher secondary | Student secondary | Sysadmin secondary/accent |
|---|---|---|---|
| December 13 initial teal redesign | `#f6c344` | Shared teal/gold redesign | Separate legacy styling |
| December 13 softening | `#d4a574` | Shared palette until split | Separate legacy styling |
| December 14 role split | `#d4a574` | `#E89B6D` coral | Separate legacy styling |
| December 20 auth update | `#ac8255` bronze | `#ac8255` bronze | Role-logo work |
| December 21 gray theme | `#ac8255` | `#ac8255` | `#D4A857`; bright accent `#FDB034` |
| December 26 teacher gold | `#D3AF37` | `#ac8255` | `#D4A857` |
| February 17 tokens | `#d3af37` | `#ac8255` | `#D4A857` |
| June 21 darker secondaries | `#8a6a1c` | `#8a643f` | `#D4A857` |
| August 15 shared gold | `#D4A857` | `#D4A857` | `#D4A857` |

The three application primary values remained unchanged through the inspected snapshot. Semantic colors, text contrast, secondary colors, hover states, and public-site copies did change. A public token named `--advisor-green` was not always equal to the application value, so names alone are insufficient historical evidence.

## VIII. Typography Lineage

| Family | Established use in the investigated history | Qualification |
|---|---|---|
| Inter | April 2025 setup/TOTP; November brand redesign; February base token; current body | Present from the initial commit, not continuously universal |
| Noto Sans | June teacher layout, July auth/base, November shared teacher/student styling | Some later imports disagreed with CSS declarations |
| Noto Sans Mono | July shared base/code | Predecessor on technical text, not current data token |
| IBM Plex Sans | November 20 student auth experiments | Different family from IBM Plex Mono; not today's body font |
| Google Sans Code | December 28 error displays | Google Sans also appeared in a request URL; requested is not necessarily applied |
| Courier New / generic monospace | Credential/error/log surfaces before consolidation | Not a single coherent prior data-font system |
| Avenir Next / Georgia | April 2026 developer-site body/heading declarations | Separate site; actual installed/rendered faces not established |
| Atkinson Hyperlegible Next | July 31 display token/public heading rule; August 15 app heading rule | Token existence preceded global app heading adoption |
| IBM Plex Mono | July 31 data token and selected credential/error uses | Replaced several different monospace predecessors |
| Material Symbols Outlined | November icon consolidation; December wordmark; August local hosting | Icon font, not body typography |

The inspected application uses Inter for body copy, Atkinson Hyperlegible Next for headings, and IBM Plex Mono for data/code/credential styling. All three, plus Material Symbols, are self-hosted. The exact font drawn into historical logo images remains unknown.

## IX. Current Snapshot and Its Limits

At `61d5e78dc`, the application token layer defines:

| Element | Value / form |
|---|---|
| Teacher / student / sysadmin primary | `#1a4d47` / `#2F4F7F` / `#303030` |
| Shared secondary / hover | `#D4A857` / `#c09840` |
| Accent text on light surfaces | `#735816` |
| Shared page background | Warm neutral-100, `#f5f5f3` |
| Shared surface | `#ffffff` |
| Body / display / data | Inter / Atkinson Hyperlegible Next / IBM Plex Mono |
| Brand | Live three-row text with Material Symbols |
| Auth composition | Brand band above form |
| Component direction | Restrained radii and borders, semantic titled cards, role-aware colors |

These are repository facts at a fixed revision, not a claim about the present state of every deployed host or every historical screenshot. Normative values must be obtained from the current `SPEC-DES-001` and token source, not from this historical snapshot.

## X. Documented Reasons, Inferences, and Open Questions

| Question | Supported answer |
|---|---|
| Why the November blue/cyan palette? | The commit explicitly derives it from the brand logos. |
| Why Inter in that redesign? | The commit describes modern, clean typography; Inter itself was already present earlier. |
| Why soften December teal/gold? | The commit cites eye strain and extended-use comfort. This is intent, not independent accessibility proof. |
| Why separate teacher and student colors? | December 14 explicitly cites visual role distinction and avoiding confusion about the logged-in role. |
| Why gray for sysadmin? | December 21 explicitly says to match the sysadmin logo and retain gold as an accent. |
| Why semantic role tokens? | February documentation says to maintain consistency across three roles in one codebase. |
| Why move fonts local? | August work explicitly removes runtime Google Fonts dependency. |
| Why stack the auth brand above the form? | September identifies the prior brand panel disappearing on narrow screens. |
| Why live text rather than image branding? | The September contract explains role inheritance, token recoloring, and accessibility. |
| Why the exact words Advisor, Steward, Guardian? | Not established by the examined history. |
| Why exactly `#2F4F7F` or the exact new font families? | Not established beyond implementation and the font-exploration label. |
| Was CSS `DarkSlateBlue` (`#483D8B`) used as Steward Blue's ancestor? | Not established. The project's descriptive Dark Slate Blue (`#2F4F7F`) was. |
| When did every change first reach production? | Not established by this repository-history investigation. |

**Interpretation:** the broad progression is from individually authored, decorative pages toward role recognition, readability, shared components, and enforceable consistency. This is a synthesis of the sequence, not evidence that one master plan existed in April 2025. Reversals, partial migrations, differing public-site values, and CSS specificity failures are part of the history and must not be edited out to make the progression appear inevitable.

## XI. Amendment

Increment the version and effective date when adding evidence or correcting this account. Preserve the distinction between source changes, recorded intent, historical rendering reports, and deployment proof. Cite the relevant commit and path for new claims, retain superseded interpretations as explicit corrections where material, and never silently update the fixed snapshot as though it described a later revision. Register changes through `SOP-DOC-001`.
