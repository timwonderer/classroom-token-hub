# HTTP error pages: draft contracts and owner decisions

Date: November 24, 2026 (America/Los_Angeles). Status: **UNRATIFIED DRAFT — governs nothing.**
This is an informative tracking package under [SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)
§V–VI, not a SPEC. It holds two proposed normative texts — **Draft 1, design** (Part D) and
**Draft 2, content and actions** (Part E) — each followed by the decisions the owner must make before
it can be ratified. Nothing here changes a template, stylesheet or handler. On ratification each draft
becomes a numbered document, is registered through
[SOP-DOC-001](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md), and this package
moves to `docs/archive/v2-tracking-2026/`.

## Why this exists

The application's HTTP error pages have no governing contract. A search of every normative root
(`docs/INVARIANT`, `docs/DOMAIN`, `docs/FEATURE-EXECUTION`, `docs/SPEC`,
`docs/STANDARD_OPERATING_PROCEDURES`, `REF-TERM-001`) finds three mentions, none of which defines
the pages:

- [SPEC-DES-001](../SPEC/SPEC-DES-001_DESIGN_SYSTEM_AND_VISUAL_IDENTITY.md) §IX *Shared-surface rule*:
  the error pages' shared chrome is defined once under `body.error-page` in `style.css`, and each page
  keeps only the rules specific to it.
- [SPEC-OPS-004](../SPEC/SPEC-OPS-004_SYSTEM_ADMINISTRATION_CONSOLE.md): `/sysadmin/test-errors/<code>`
  probes are diagnostic, not operator features.
- [SOP-TEST-002](../STANDARD_OPERATING_PROCEDURES/TESTING/SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md)
  §X: error pages are covered by accessibility render fixtures, and "error pages" is not an exemption reason.

Structure, content, buttons, response format and logging are each decided per template and per
handler, and they have drifted (Part B).

## Where the contracts live

**Owner ruling (2026-11-24): two documents, not one.** In the owner's words: "we define two docs,
SPEC-DES level for the design of the error page, SPEC-OPS for the content errors pages should convey,
should not convey, and user actions".

| Draft | Proposed id | Governs |
|---|---|---|
| 1 — Design (Part D) | `SPEC-DES-002` HTTP Error Page Design | Layout and anatomy, shared vs per-page styling, icons, headings, accessibility of the presentation |
| 2 — Content and actions (Part E) | `SPEC-OPS-007` HTTP Error Page Content and Actions | What a page conveys, what it must not convey, and the actions it offers (buttons, guidance list, status-page link) |

Both ids are the next free number in their area (no `SPEC-DES-002` or `SPEC-OPS-007` is cited
anywhere in `docs/`, `app/` or `tests/`). Whether Draft 1 is a new `SPEC-DES-002` or a new section of
`SPEC-DES-001` is decision **DES-1**. Where response format (HTML vs JSON) and recording (logging,
persistence) belong is decision **OPS-1**: the ruling names content and actions for the SPEC-OPS
document, and these two subjects are neither. Draft 2 carries them provisionally, marked as such.

Per SOP-DOC-000 §V, a SPEC binds implementation only when incorporated by an `INV-*`, `DOM-*` or
`FEAT-*` contract. The natural incorporating documents are INV-ARC-020 for Draft 1 and DOM-OPS-001
for Draft 2 (decisions DES-2, OPS-2).

### Why the drafts are not registered now

SOP-DOC-000 does not provide for registering a draft. `tests/dom/docs/test_documentation_index_complete.py`
requires every numbered file in a normative root to appear in SOP-DOC-001, so a numbered draft would
have to be indexed beside ratified documents. The repository already shows the cost of that: an
unratified `FEAT-OBL-004` DRAFT was indexed and later read as authority. The drafts therefore stay
unnumbered in this `docs/TRACKING/` package, following the precedent of
[HISTORICAL_ATTENDANCE_PROOF_DECISION_PACKAGE_20261003.md](HISTORICAL_ATTENDANCE_PROOF_DECISION_PACKAGE_20261003.md).

---

## Part A — Sources inventoried

| Surface | Location |
|---|---|
| Templates | `templates/error_400.html`, `error_401.html`, `error_403.html`, `error_404.html`, `error_429.html`, `error_500.html`, `error_503.html`. `error_418.html` exists only on the unmerged `claude/teapot-418` branch. |
| Status handlers | `wsgi.py`: `@app.errorhandler` for 500, 404, 403, 401, 400, 429, 503 |
| Unhandled-exception handler | `app/__init__.py` `register_error_handlers` (`@app.errorhandler(Exception)`) |
| Blueprint handlers | `app/routes/api.py` `handle_api_context_resolution_error`; `app/routes/student.py` `handle_context_forbidden`, `handle_context_not_established`, `_setup_storage_unavailable` (503), `_setup_state_expired` (409) |
| Shared CSS | `static/css/style.css`, section "Error Pages" (`body.error-page`, `.error-container`, `.error-header`, `.error-body`, `.troubleshooting`, `.actions`) |
| Probes | `app/routes/system_admin.py` `/sysadmin/test-errors/{400,401,403,404,500,503}` |
| Accessibility fixtures | `tests/a11y_fixtures/public.py` (one or two states per page) |
| Tests | `tests/test_error_handlers.py` (429 page; `/recover` not limited), `tests/test_404_dedupe_cache.py` (cache pruning) |

## Part B — What exists today, and where the pages disagree

All seven templates share: a standalone document (no layout), Bootstrap + `fonts.css` + `tokens.css` +
`style.css`, `<body class="error-page">`, `<main id="main-content" aria-labelledby="error-heading">`,
`.error-container` > `.error-header` (status code as `h1#error-heading`, label as `<p>`) >
`.error-body` > `.actions`, a primary `alert_card` with `heading_tag='h2'`, and an inline script that
forces `aria-hidden` on every Material Symbol.

### B.1 Anatomy

| | 400 | 401 | 403 | 404 | 429 | 500 | 503 |
|---|---|---|---|---|---|---|---|
| Header icon | `problem` | `lock_person` | `gpp_bad` | `unknown_document` | `hourglass_top` | `error` | **none** |
| Primary card (level / `role`) | warning / alert | info / alert | danger / alert | info / alert | warning / alert | warning / alert | warning / alert |
| Guidance list | `alert_card` info, `role=note`, h2 | `alert_card` warning, **no role**, h2 | `alert_card` info, `role=note`, h2 | **`.troubleshooting` div, h5** | `alert_card` info, `role=note`, h2 | **none** | **`.status-box` div, h5** |
| Guidance heading | "Steps you can try right now" | "What should you do?" | "Troubleshooting steps" | "What can you do?" | "Steps you can try right now" | — | "What's happening?" / "What can you do?" |
| List bullets | browser bullets (`ps-4`) | browser | browser | `list-style: none` + typed `•` | browser | — | browser |
| Detail box | `.error-message` (h5 + `<code>` of `error.description`) | — | — | `.requested-url` (`request.url`) | `.error-message` (h5 + limit) | "This error was logged" card when `error_id` | `.auto-refresh` 30 s countdown |
| Extra panel | — | `.login-links` (h6, Student / Admin login) | — | — | — | — | — |
| Page-local `<style>` | `.error-message` | `.login-links`, `.login-buttons` | none | `.troubleshooting`, `.requested-url` | `.error-message` (warning colours) | none | `.status-box`, `.auto-refresh`, `.countdown` |
| Dead code | — | — | — | — | — | `copyLogs()` reads a `#logOutput` that does not exist | — |

### B.2 Actions

| | 400 | 401 | 403 | 404 | 429 | 500 | 503 |
|---|---|---|---|---|---|---|---|
| First button | Back | Return | Return | Return | Back | Return | **Try Again** (reload) |
| "Return to Login Page" → `/` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| "Go Back to Last Page" (`history.back()`) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| "Check System Status" (new tab) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

- `/` (`main.home`) is not a login page: signed in it redirects to the role's dashboard, signed out to
  the marketing site. The label does not describe the destination.
- Every status link is hard-coded to `https://status.classroomtokenhub.com`. The 500 and 503 handlers
  pass `status_page_url=get_validated_status_page_url()`, which no template reads. A self-hosted
  instance therefore links to this project's status page.

### B.3 Handler behaviour

| Status | Handler | Response | Logger | Database |
|---|---|---|---|---|
| 400 | `wsgi.bad_request_error` | HTML always; shows `error.description` to the visitor | warning (URL + description) | `log_error_to_db(...)` |
| 401 | `wsgi.unauthorized_error` | HTML always | warning | `log_error_to_db(...)` |
| 403 | `wsgi.forbidden_error` | HTML always | warning | `log_error_to_db(...)` |
| 404 | `wsgi.not_found_error` | HTML always, `request_url=request.url` | warning | `log_error_to_db(...)` once per path per hour (in-process dedupe cache, cap 10 000) |
| 429 | `wsgi.too_many_requests_error` | **JSON when the path starts with `/api/`** (`{status, error, message}` + `Retry-After`), else HTML | warning | `log_error_to_db(...)` |
| 500 (`abort(500)`, escaped errors) | `wsgi.internal_error` | HTML always, `error_id=log_error_to_db(...)` | exception | `log_error_to_db(...)` |
| 500 (unhandled exception in a view) | `app/__init__.handle_unhandled_exception` | **JSON when `Accept` best match is `application/json`** (`{error}`), else HTML without `error_id`; plain-text fallback if rendering fails | exception, with request id and actor context | inserts into `error_events` if the table exists |
| 503 | `wsgi.service_unavailable_error` | HTML always | **error** | `log_error_to_db(...)` |
| 503 (`SetupUnavailable`) | `student._setup_storage_unavailable` | JSON by `Accept` (`{verified, message}`), else HTML | — | — |
| 404/401 (API context errors) | `api.handle_api_context_resolution_error` | JSON `{status, message, error}` | — | — |
| 403 → 404 (student context) | `student.handle_context_forbidden` | `abort(404)`: forbidden or mismatched class context is shown as not found | warning | via 404 |

**Nothing is persisted to the database by any of these paths.**

- `wsgi.log_error_to_db` returns `None` on every path: it skips outside a FEAT context, and inside
  one it gathers request details and returns without writing ("Legacy database error logging has
  been removed."). So the 500 page's `error_id` block can never render, and the 404 dedupe cache
  deduplicates calls that do nothing.
- The unhandled-exception path writes to `error_events` only if the table exists. Migration
  `7c3d4e5f6a7b` dropped it ("absorbed into operational_events (DOM-OPS-001)"), and
  `operational_events` was created later by `b8e1f4c2a5d9`. No error handler writes to
  `operational_events`.
- What is actually recorded is the application log line, which Grafana reads (SPEC-OPS-004 §6.5:
  the console has no log viewer, owner ruling 2026-10-07).

Status-code shapes for JSON clients differ three ways (`{status, error, message}`, `{error}`,
`{verified, message}`), and the JSON switch is chosen three ways (path prefix, `Accept`, none). An
`abort(404)` inside an `/api/` route returns the HTML 404 page.

### B.4 Probes and fixtures

- Probes exist for 400, 401, 403, 404, 500 and 503. There is none for 429.
- Accessibility fixtures cover all seven pages; 400 (with and without a message) and 500 (with and
  without `error_id`) have two states.

---

## Part C — Rules that already bind these pages

These are in force regardless of this draft. Where the pages break them (Part F), the fix needs no
owner decision.

| Authority | Rule as it applies here |
|---|---|
| [INV-ARC-020](../INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md) §VI | Exactly one meaningful `h1`; logical heading order with no unjustified level skips; accessible names for every link and button; WCAG 2.1 AA contrast; nothing communicated by colour alone |
| INV-ARC-020 §IX.3 | Heading semantics may not be downgraded for styling convenience |
| [SOP-TEST-002](../STANDARD_OPERATING_PROCEDURES/TESTING/SOP-TEST-002_Accessibility_Validation_And_PR_Gate.md) §X | Every error template has a render fixture, one state per materially different surface; error pages may not be exempted |
| SPEC-DES-001 §IX | CSS repeated across error templates belongs once under `body.error-page`; a page keeps only its own rules; design values come from tokens |
| [INV-ARC-007](../INVARIANT/ARCHITECTURE/INV-ARC-007_GET_MUST_BE_PURE.md) §V | A GET must not commit, flush or mutate domain state; this includes a GET that ends in an error |
| [SPEC-OPS-004](../SPEC/SPEC-OPS-004_SYSTEM_ADMINISTRATION_CONSOLE.md) | Test-error routes are sysadmin-only diagnostic probes; errors are read in Grafana, not in the console |
| [SPEC-OPS-006](../SPEC/SPEC-OPS-006_PUBLIC_REQUEST_MONITORING.md) v1.5 / v1.7 | Only a 5xx is a failure; 404 is a descriptive signal (failed-request 404s only on named hall-pass routes); 429 and other 4xx are `HTTP_REFUSED` (unknown), never "Mostly unavailable" |
| [REF-TERM-002](../REFERENCE/REF-TERM-002_USER_VOCABULARY.md) | Recommended user-facing vocabulary (teacher, student, class); internal terms not shown to users; accessibility (INV-ARC-020) wins over it |
| [INV-ARC-005](../INVARIANT/ARCHITECTURE/INV-ARC-005_NO_PII_LEAKAGE_IN_EXECUTION_LAYER.md) | No PII in logs or error output |

---

## Part D — Draft 1: `SPEC-DES-002` HTTP Error Page Design (UNRATIFIED)

> Draft text. Every bracketed `[DES-n]` marks a rule that depends on an owner decision in D.2; the
> text shows the **current behaviour** as a placeholder, not a choice. Unbracketed rules restate
> Part C or describe what every page already shares.

### D.1 Draft text

#### I. Purpose

Define how an HTTP error page looks and is built: its layout, the parts every page shares, what a
page may style for itself, and the accessibility of its presentation, so that every error page reads
as one surface and a new one is built from the same parts.

#### II. Scope

Applies to the `templates/error_<code>.html` templates, the macros they call, and the Error Pages
section of `static/css/style.css`. Does not govern what a page says or which actions it offers
(`SPEC-OPS-007`), handler behaviour, or responses produced in front of the application.

#### III. Authority Level

Normative (Tier 2), technical contract. Subordinate to INV-CORE-000, INV-ARC-020 and SPEC-DES-001,
whose tokens and shared-surface rule it applies and must not weaken. Binding when incorporated by
`[DES-2]`.

#### IV. Dependencies

INV-ARC-020, SPEC-DES-001, SOP-TEST-002, SPEC-OPS-007.

#### V. Page anatomy

Every error page is a standalone document (it extends no layout) with, in this order:

1. **Shell.** `<html lang="en">`; the stylesheets Bootstrap, `fonts.css`, `tokens.css`, `style.css`
   in that order; `<title>` of the form `<code> - <Label>`; `<body class="error-page">`;
   `<main id="main-content" aria-labelledby="error-heading">` holding everything below.
2. **Header** (`.error-header`, on the role-themed `var(--primary)` band). A decorative Material
   Symbol `[DES-4: required on every page?]`, the status code as the page's only `h1` with
   `id="error-heading"`, and the status label as a `<p>`.
3. **Explanation card.** One `alert_card` with `heading_tag='h2'` and `role='alert'`. Its level
   is `[DES-5]`.
4. **Detail block** (only where SPEC-OPS-007 calls for one). Presented as `[DES-3]`.
5. **Guidance block** (where SPEC-OPS-007 calls for one). A heading at `h2` and a real `<ul>` whose
   list semantics are kept. Presented as `[DES-3]`; markers are `[DES-3]`.
6. **Actions** (`.actions`): centred, wrapping row of buttons; the set and order are SPEC-OPS-007's.

#### VI. Shared and per-page styling

1. Everything in §V is styled once under `body.error-page` in the Error Pages section of
   `style.css` (SPEC-DES-001 §IX). A rule two error pages need is promoted there, never copied.
2. A page-local `<style>` block holds only rules that no other error page uses. Design values in it
   come from tokens; structural values may be literals (SPEC-DES-001 §IX).
3. Per-page variation is limited to the header icon, the card level and any panel unique to that
   status (e.g. 401's sign-in choices) `[DES-3]`.

#### VII. Headings and accessibility

1. One `h1`; card and block headings are `h2`; nothing skips a level and nothing is a heading for
   its size (INV-ARC-020 §VI.1–2, §IX.3).
2. Icons are decorative and carry `aria-hidden="true"` in the markup `[DES-6: drop the runtime
   script that re-applies it?]`.
3. A link that opens a new tab says so in its accessible name.
4. Contrast meets WCAG 2.1 AA in the rendered role theme; meaning is never carried by colour alone.
5. A visible countdown or timed change on the page can be stopped by the visitor (WCAG 2.2.1).
6. Every template has a SOP-TEST-002 render fixture, with a state for each optional block that changes
   the rendered surface.

#### VIII. Building a new status page

Create `templates/error_<code>.html` from §V using only shared classes plus rules unique to the page,
add its render fixture, and add the status to SPEC-OPS-007 in the same change.

#### IX. Amendment

SOP-DOC-000 §XIII; register through SOP-DOC-001.

### D.2 Design decisions for the owner

| # | Decision | Current behaviour | Options |
|---|---|---|---|
| **DES-1** | New document or a section of SPEC-DES-001? | Only SPEC-DES-001 §IX's one sentence exists | (a) new `SPEC-DES-002` *(proposed: keeps SPEC-DES-001 about tokens and the system)*; (b) new section in SPEC-DES-001 |
| **DES-2** | What incorporates it? | Nothing | INV-ARC-020 (proposed) / SPEC-DES-001 only |
| **DES-3** | How are the guidance and detail blocks styled, and what may a page style for itself? | Five pages use an `alert_card` with `h2`; 404 uses `.troubleshooting` with `h5`, `list-style: none` and typed `•`; 503 uses `.status-box` with two `h5`s; 400 and 429 each define `.error-message` | (a) all use `alert_card`, no page CSS; (b) one shared `.troubleshooting` block and one shared detail block in `style.css`, `h2`, browser bullets; (c) per page as now (needs the Part F fixes regardless) |
| **DES-4** | Header icon required on every page? | 503 has none | required / optional |
| **DES-5** | Explanation-card level per status | 400/429/500/503 warning, 401/404 info, 403 danger | keep; or a rule (e.g. visitor-caused 4xx = info, refused = warning, 5xx = warning) |
| **DES-6** | Remove the inline script that sets `aria-hidden` on icons? | On every page; redundant — every icon in the templates and the one `alert_card` renders (`templates/macros/cards.html`) already carry `aria-hidden="true"` | keep / remove |

---

## Part E — Draft 2: `SPEC-OPS-007` HTTP Error Page Content and Actions (UNRATIFIED)

> Draft text. `[OPS-n]` marks a rule that depends on an owner decision in E.2; the text shows the
> **current behaviour** as a placeholder. §VIII–X (response format, recording, diagnostics) are
> here provisionally pending OPS-1.

### E.1 Draft text

#### I. Purpose

Define what an HTTP error response tells the person or script that receives it, what it must never
tell them, and what they can do next, so that every error status answers the same three questions:
what happened, is it my fault or the system's, and what do I do now.

#### II. Scope

Applies to every 4xx or 5xx response the application produces through an error handler: the words
on the page, the facts it reports, the actions it offers, and the JSON body returned in its place.
Does not govern layout or styling (`SPEC-DES-002`), validation errors inside a working page, flash
messages, redirects, or responses produced in front of the application (proxy, Cloudflare,
maintenance gate).

#### III. Authority Level

Normative (Tier 2), technical contract. Subordinate to INV-CORE-000, INV-ARC-005, INV-ARC-007 and
INV-ARC-020. Binding when incorporated by `[OPS-2]`.

#### IV. Dependencies

INV-ARC-005, INV-ARC-007, INV-ARC-020, DOM-OPS-001, SPEC-OPS-003, SPEC-OPS-004, SPEC-OPS-006,
SPEC-DES-002, REF-TERM-002 (informative).

#### V. Statuses with a page

1. These statuses have a page and exactly one application-level handler: 400, 401, 403, 404, 429,
   500, 503 `[OPS-14: 418]`.
2. Any other status returns `[OPS-13]`.

#### VI. What a page conveys

Every page tells the visitor, in plain language and REF-TERM-002 vocabulary where it does not
conflict with INV-ARC-020 `[OPS-11]`:

1. **What happened**, in the explanation card, without blame.
2. **Whose side the problem is on**: the request (4xx) or the service (5xx).
3. **What to try**, as a guidance list `[OPS-3: on every page, including 500?]`.
4. **Status-specific facts** where they help: the requested URL (404); the limit that was reached
   (429); a reference to quote when asking for help (500) `[OPS-7]`; the reason the request was
   refused (400) `[OPS-8]`.

#### VII. What a page must not convey

1. No stack trace, exception class or message, SQL, file path, configuration value, internal
   identifier other than the reference in §VI.4, or PII (INV-ARC-005).
2. No statement that a resource exists to an actor who may not see it: class-scoped data the actor
   may not access is answered as not found `[OPS-12: on every blueprint?]`.
3. No promise the system does not keep (e.g. "this error was logged" when nothing is recorded)
   `[OPS-7]`.
4. No developer vocabulary that REF-TERM-002 lists as not for user-facing text.

#### VIII. User actions

| Action | Present on |
|---|---|
| Leave to a safe page `[OPS-9: label and destination]` | every page |
| Go back (`history.back()`) | every page except 503 `[OPS-3]` |
| Try again (reload) | 503 |
| Sign in, one choice per role | 401 `[OPS-9]` |
| Status page (new tab) | `[OPS-4: which statuses]`, destination `[OPS-4]` |

1. Actions appear in one order on every page `[OPS-9]`.
2. No action reloads or navigates on a timer the visitor cannot stop `[OPS-6]`.

#### IX. Response format (provisional — OPS-1)

1. A browser receives the HTML page; a JSON client receives a JSON body with the same status.
2. How JSON is chosen, and its shape: `[OPS-10]`.
3. 429 responses carry `Retry-After` when the limiter knows the reset time.
4. If the page itself fails to render, the handler returns plain text with the same status.

#### X. Recording (provisional — OPS-1)

1. Every handled error writes one log line with request id, method, sanitised path and status, no
   PII, at `[OPS-5b]`.
2. Persistence beyond the log: `[OPS-5]`.
3. Recording never raises and never changes the response's status.
4. An error ending a GET does not commit or flush application state (INV-ARC-007); any persistent
   record is written outside the request's unit of work.

#### XI. Diagnostics

1. Every status in §V.1 has a sysadmin probe at `/sysadmin/test-errors/<code>` (SPEC-OPS-004)
   `[OPS-15: add 429]`.
2. Each handler has a test asserting its status, its HTML/JSON choice and its log line.
3. Adding a status: amend §V.1, register one handler following §IX–X, add the probe and test, and
   build the page per SPEC-DES-002 §VIII in the same change.

#### XII. Amendment

SOP-DOC-000 §XIII; register through SOP-DOC-001.

### E.2 Content and action decisions for the owner

| # | Decision | Current behaviour | Options |
|---|---|---|---|
| **OPS-1** | Do response format (HTML vs JSON) and recording belong in this document? | Governed nowhere | (a) yes, as drafted; (b) amend SPEC-OPS-003 (observability) for recording and keep only response format here; (c) a third document |
| **OPS-2** | What incorporates it? | Nothing | DOM-OPS-001 (proposed) / INV-ARC-005 + DOM-OPS-001 |
| **OPS-3** | Guidance list and Back button on every page? | 500 has no guidance list; 503 has Try Again instead of Back | (a) both everywhere; (b) 500 and 503 exempt |
| **OPS-4** | Status-page link: which pages, and which URL? | All seven, hard-coded `status.classroomtokenhub.com`; the `status_page_url` the 500/503 handlers pass is never read | Pages: all / 5xx and 429 / 5xx only. URL: hard-coded / `get_validated_status_page_url()`, omitted when unset (self-hosting) |
| **OPS-5** | Which statuses persist a record beyond the log, and where? | None: `log_error_to_db` is a stub and `error_events` was dropped | (a) log only — delete `log_error_to_db`, the 404 dedupe cache and the `error_events` insert; (b) 5xx to `operational_events` (DOM-OPS-001); (c) all statuses, 404 deduped |
| **OPS-5b** | Log level per status | warning 400/401/403/404/429; error 503; exception 500 | keep / 4xx warning (or info), 5xx error |
| **OPS-6** | 503 auto-refresh | Reloads after 30 s, cannot be stopped | (a) keep; (b) remove, keep Try Again; (c) keep with a Stop control |
| **OPS-7** | 500 support reference | "Error ID" block can never render (`error_id` always `None`), and it claims the error "has been automatically logged"; `g.request_id` is in every log line | (a) show the request id as the reference, reworded; (b) remove the block and its fixture state |
| **OPS-8** | Does 400 show `error.description`? | Yes, verbatim in `<code>`, so `abort(400, description=...)` text reaches visitors | show / fixed allowlist / never |
| **OPS-9** | Labels, destinations and order of actions | "Return to Login Page" links to `/` (dashboard or marketing site, never login); 401 offers "Student Login" / "Admin Login"; "log in" vs "sign in"; order differs (Back first on 400/429) | settle the safe-page label and target, the 401 role names (REF-TERM-002 says teacher), and one order |
| **OPS-10** | JSON: how chosen, and what shape? | 429 by `/api/` prefix; unhandled 500 by `Accept`; others never (an `abort(404)` in `/api/` returns HTML). Shapes `{status, error, message}`, `{error}`, `{verified, message}` | one switch (path, `Accept`, or either) and one shape (e.g. the API's `{status: "error", error, message}`) |
| **OPS-11** | Tone and wording standard | Per page ("Pardon the interruption", "bug in our codes", "Troubleshooting steps") | REF-TERM-002 + plain-language rule only / a fixed heading set (e.g. "What happened", "What you can do") |
| **OPS-12** | 403 shown as 404 for out-of-scope data, everywhere? | Student blueprint and API map context errors to 404; admin routes `abort(403)` in 7 places | per blueprint as now / one rule |
| **OPS-13** | What do statuses without a page return? | Werkzeug's default page (e.g. 405, 409, 413) | Werkzeug default / a generic page built per SPEC-DES-002 |
| **OPS-14** | Is 418 (`/teapot`) a governed status? | Unmerged branch | include in §V.1 / an easter egg outside the contract |
| **OPS-15** | Add a 429 probe? | None | add / not needed |

---

## Part F — Departures from rules already in force

No owner decision is needed to fix these; they break Part C as written. They are listed, not fixed,
because this task changes no template.

1. **Heading skips (INV-ARC-020 §VI.2).** 400 and 429 (`.error-message h5` after an `h2`), 404
   (`.troubleshooting h5`), 503 (`.status-box h5`), 401 (`.login-links h6`).
2. **Duplicated CSS (SPEC-DES-001 §IX).** `.error-message` is defined in both 400 and 429 with only
   the colour differing; `.troubleshooting` rules exist in both `style.css` and 404's page block.
3. **List semantics.** 404 removes list styling and types `•` characters into each item, which screen
   readers announce as "bullet".
4. **Dead code.** `copyLogs()` in 500 references an element that does not exist.

## Not checked

- Rendered axe results for the current pages (the gate passed on `claude/teapot-418`; not rerun here).
- Error responses produced by Cloudflare or the Access gate in front of the application.
