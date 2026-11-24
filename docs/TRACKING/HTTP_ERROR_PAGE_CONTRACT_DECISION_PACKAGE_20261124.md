# HTTP error pages: draft contract and owner decisions

Date: November 24, 2026 (America/Los_Angeles). Status: **UNRATIFIED DRAFT — governs nothing.**
This is an informative tracking package under [SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md)
§V–VI, not a SPEC. It holds a proposed normative text (Part D) and the decisions the owner must make
before any of it can be ratified (Part E). Nothing here changes a template, stylesheet or handler.
On ratification the text in Part D becomes a numbered document, is registered through
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

## Where the contract should live

**Recommendation: a new `SPEC-UI-002` — HTTP Error Responses.** Placement is itself owner decision D1.

- Not an amendment to SPEC-DES-001. Its §II limits it to tokens, CSS and templates' visual layer and
  excludes "page rendering structure" (to SPEC-UI-001) and any persistence or response behaviour. An
  error-page contract has to govern handler output (HTML vs JSON, status codes, logging), which
  SPEC-DES-001 cannot hold without widening its scope.
- Not an amendment to SPEC-UI-001. Its §II and §V govern *authenticated* page routes through the
  INV-ARC-022 view-model pipeline. Error pages are standalone (they extend no layout and have no view
  model) and are served to signed-out visitors.
- A SPEC, not a FEAT: an error page performs no domain mutation (SOP-DOC-000 §V, §VI).
- `UI` area, because the subject is what a visitor receives. SPEC-DES-001 would keep its one sentence
  on shared CSS and cite the new SPEC for anatomy.

Per SOP-DOC-000 §V, a SPEC binds implementation only when incorporated by an `INV-*`, `DOM-*` or
`FEAT-*` contract. The natural incorporating documents are INV-ARC-020 (accessibility of the pages)
and DOM-OPS-001 (logging), which is decision D2.

### Why this draft is not registered now

SOP-DOC-000 does not provide for registering a draft. `tests/dom/docs/test_documentation_index_complete.py`
requires every numbered file in a normative root to appear in SOP-DOC-001, so a numbered draft would
have to be indexed beside ratified documents. The repository already shows the cost of that: an
unratified `FEAT-OBL-004` DRAFT was indexed and later read as authority. This package therefore stays
unnumbered in `docs/TRACKING/`, following the precedent of
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

## Part D — Proposed contract (UNRATIFIED)

> Draft text for the numbered SPEC. Every bracketed `[Dn]` marks a rule that depends on an owner
> decision in Part E; the text shows the **current behaviour** as a placeholder, not a choice.
> Unbracketed rules restate Part C or describe behaviour every page already shares.

### I. Purpose

Define what Classroom Token Hub returns when a request ends in an HTTP error status: the page a
browser receives, the body a script receives, and what is recorded, so that every error status is
answered the same way and a new one can be added without inventing a layout.

### II. Scope

Applies to every response the application itself produces with a 4xx or 5xx status through an
error handler: the `error_<code>.html` templates, the handlers that render them, the JSON bodies
returned in their place, and the shared Error Pages CSS. Does not govern: form validation errors
shown inside a working page, flash messages, redirects, responses produced in front of the
application (proxy, Cloudflare, maintenance gate), or the status site.

### III. Authority Level

Normative (Tier 2), technical contract. Subordinate to INV-CORE-000, INV-ARC-005, INV-ARC-007,
INV-ARC-020 and SPEC-DES-001's token and shared-surface rules. Binding when incorporated by `[D2]`.

### IV. Dependencies

INV-ARC-005, INV-ARC-007, INV-ARC-020, SPEC-DES-001, SPEC-OPS-003, SPEC-OPS-004, SPEC-OPS-006,
SOP-TEST-002, REF-TERM-002 (informative).

### V. Statuses with a page

1. A status with its own page has exactly one template, `templates/error_<code>.html`, and exactly
   one application-level handler. The set today is 400, 401, 403, 404, 429, 500, 503 `[D13: 418]`.
2. A status without its own page `[D12]`.

### VI. Page anatomy

Every error page is a standalone document with, in this order:

1. **Shell.** `<html lang="en">`, the four shared stylesheets in the order Bootstrap, `fonts.css`,
   `tokens.css`, `style.css`; `<title>` of the form `<code> - <Label>`; `<body class="error-page">`;
   `<main id="main-content" aria-labelledby="error-heading">`.
2. **Header** (`.error-header`). A decorative Material Symbol (`aria-hidden="true"`) `[D5: required
   on every page?]`, the status code as the page's only `h1` with `id="error-heading"`, and the
   status label as a `<p>`.
3. **Explanation card.** One `alert_card` with `heading_tag='h2'` and `role='alert'`, stating in plain
   language what happened. Its level is `[D6]`.
4. **Status detail** (optional, per status). Facts about this request that help the visitor: the
   requested URL (404), the limit (429), a reference to quote to support (500) `[D8]`, the request's
   error description (400) `[D9]`. Presented as `[D4]`.
5. **Guidance.** A heading at the next level below the card heading (`h2`) and a list of what the
   visitor can do, rendered as a real `<ul>` with list semantics preserved. Required on every page
   `[D3: including 500?]`; heading text, element and styling are `[D4]`.
6. **Actions** (`.actions`). Per §VII.

Rules:

- One `h1`, and no heading level is skipped (INV-ARC-020 §VI.1–2). Nothing styled as a heading that is
  not one, and no heading chosen for its size.
- Shared presentation lives once under `body.error-page` in `style.css` (SPEC-DES-001 §IX). A
  page-local `<style>` block holds only rules no other error page uses; a rule needed by two pages
  is promoted.
- Icons are decorative and hidden from assistive technology in the markup itself `[D11: drop the
  inline aria-hidden script?]`.
- Wording follows REF-TERM-002 where it does not conflict with INV-ARC-020 `[D10]`.
- A page shows no stack trace, exception class, internal identifier other than the support
  reference, or PII (INV-ARC-005).
- No page changes the location or reloads itself on a timer the visitor cannot stop, extend or turn
  off `[D7]`.

### VII. Actions

| Action | Element | Present on |
|---|---|---|
| Leave to a safe page `[D10: label and destination]` | link to `/` | every page |
| Go back | `<button type="button">`, `history.back()` | every page except 503 `[D3]` |
| Try again | `<button type="button">`, reload | 503 `[D7]` |
| Sign in | links to the student and teacher sign-in pages | 401 `[D10]` |
| Status page | link, new tab, with "(opens in a new tab)" in its accessible name and a decorative `open_in_new` icon | `[D4b: which statuses]` |

- Button order is the same on every page `[D10]`.
- The status link's destination is `[D4b: hard-coded vs get_validated_status_page_url()]`.

### VIII. Response format

1. A browser receives the HTML page. A JSON client receives a JSON body with the same status code.
2. How the handler decides a client wants JSON is `[D14]`.
3. The JSON body shape is `[D14]`.
4. 429 responses carry `Retry-After` when the limiter knows the reset time.
5. If rendering the error page itself fails, the handler returns a plain-text body with the same
   status rather than raising.

### IX. Disclosure

1. A request for class-scoped data the actor may not see is answered 404, not 403, wherever the
   owning blueprint already maps context errors that way (student blueprint, API). `[D15: make this
   the rule everywhere?]`
2. The 400 page shows the request's error description `[D9]`.

### X. Recording

1. Every handled error status writes one application log line carrying the request id, method, path
   (sanitised) and status, without PII. Level: `[D2b]`.
2. Persistence beyond the log `[D2]`.
3. Recording never raises and never turns the original response into a different status.
4. An error that ends a GET may not commit or flush application state (INV-ARC-007). Any persistent
   record is written outside the request's unit of work `[D2]`.

### XI. Diagnostics and tests

1. Every status in §V.1 has a sysadmin probe at `/sysadmin/test-errors/<code>` `[D16: add 429]`.
2. Every error template has a SOP-TEST-002 render fixture, with a state for each optional section that
   changes the rendered surface.
3. Each handler has a test asserting its status code, its HTML/JSON choice and its log line.

### XII. Adding a status page

1. Confirm the status is produced by the application, not by the proxy or limiter in front of it.
2. Create `templates/error_<code>.html` from the anatomy in §VI, using only shared classes plus
   rules unique to the page.
3. Register one handler following §VIII–X.
4. Add the probe (§XI.1), the render fixture and the handler test.
5. Amend §V.1 of this document in the same change.

### XIII. Amendment

Standard SOP-DOC-000 §XIII procedure; register through SOP-DOC-001.

---

## Part E — Owner decisions

Each item gives the current behaviour first. Where I lean one way it says so, as a proposal only.

| # | Decision | Current behaviour | Options |
|---|---|---|---|
| **D1** | Where does the contract live? | Nowhere | (a) new `SPEC-UI-002` *(proposed — see "Where the contract should live")*; (b) amendment section in SPEC-DES-001, widening its §II; (c) new `SPEC-OPS-*` |
| **D2** | Which statuses persist a record beyond the log, and where? Which document incorporates the SPEC? | None persist: `log_error_to_db` is a stub and `error_events` no longer exists. Log lines only, read in Grafana. | (a) log only, delete `log_error_to_db`, the 404 dedupe cache and the `error_events` insert; (b) persist 5xx only to `operational_events` (DOM-OPS-001); (c) persist all statuses, 404 deduped. Incorporation by INV-ARC-020 + DOM-OPS-001, or DOM-OPS-001 alone |
| **D2b** | Log level per status | warning for 400/401/403/404/429, error for 503, exception for 500 | keep; or align with SPEC-OPS-006 (4xx warning/info, 5xx error) |
| **D3** | Guidance list and Back button on every page? | 500 has no guidance list; 503 has no Back (has Try Again) | (a) every page has both; (b) 500 and 503 exempt |
| **D4** | How is the guidance (and detail box) styled? | Five pages use an info/warning `alert_card` with `h2`; 404 uses `.troubleshooting` with `h5`, `list-style: none` and typed `•`; 503 uses `.status-box` with two `h5`s | (a) all use `alert_card` (no page CSS); (b) all use one shared `.troubleshooting` block in `style.css`, `h2`, browser bullets; (c) keep per page |
| **D4b** | Status-page link: which pages, and which URL? | All seven, hard-coded `status.classroomtokenhub.com`; `status_page_url` passed by 500/503 and unused | Pages: all / 5xx and 429 only / 5xx only. URL: hard-coded / `get_validated_status_page_url()`, link omitted when unset (self-hosting) |
| **D5** | Header icon required on every page? | 503 has none | required / optional |
| **D6** | Explanation-card level per status | 400/429/500/503 warning, 401/404 info, 403 danger | keep; or a rule (4xx caused by visitor = info, 403 = warning, 5xx = warning) |
| **D7** | 503 auto-refresh | Reloads after a 30 s countdown with no way to stop it | (a) keep; (b) remove, keep Try Again; (c) keep with a Stop control (WCAG 2.2.1) |
| **D8** | 500 support reference | "Error ID" block can never render (`error_id` always `None`); `g.request_id` exists and is in every log line | (a) show the request id as the reference; (b) remove the block and fixture state |
| **D9** | Should 400 show `error.description`? | Yes, in `<code>`; probes show test text, `abort(400, description=...)` text reaches users | show / show only a fixed allowlist / never |
| **D10** | Wording and labels | "Return to Login Page" goes to `/`, which is not a login page; 401 offers "Admin Login" (REF-TERM-002 says teacher); "log in" vs "sign in"; button order varies | settle the label, the 401 button names and one button order |
| **D11** | Remove the inline script that sets `aria-hidden` on icons? | Present on every page, and redundant: every icon in the templates carries `aria-hidden="true"` in markup, and so does the icon `alert_card` renders (`templates/macros/cards.html`) | keep / remove |
| **D12** | What does a 4xx/5xx without its own page return? | Werkzeug's default page (e.g. 405, 409, 413) | Werkzeug default / a generic `error.html` from the same anatomy |
| **D13** | Is 418 (`/teapot`) a governed status page? | Unmerged branch | include in §V.1 / treat as an easter egg outside the contract |
| **D14** | JSON: how chosen, and what shape? | 429: path starts `/api/`; unhandled 500: `Accept` best match; others never. Shapes `{status, error, message}`, `{error}`, `{verified, message}` | Choose one switch (path, `Accept`, or either) and one shape (e.g. `{status: "error", error, message}` as the API already uses) |
| **D15** | 403 shown as 404 for out-of-scope data, everywhere? | Student blueprint and API map context errors to 404; admin routes `abort(403)` in 7 places | per blueprint as now / one rule |
| **D16** | Add a 429 probe? | None | add / not needed |

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
