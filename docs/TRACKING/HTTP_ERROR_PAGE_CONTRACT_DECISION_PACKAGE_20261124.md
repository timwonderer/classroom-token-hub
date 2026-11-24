# HTTP error pages: draft contracts, rulings and ratification plan

Date: November 24, 2026 (America/Los_Angeles), revision 3. Status: **UNRATIFIED DRAFT — governs
nothing.** This is an informative tracking package under
[SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) §V–VI, not a
SPEC. It holds two proposed normative texts — **`SPEC-DES-002` HTTP Error Page Presentation**
(Part D) and **`SPEC-OPS-007` HTTP Error Communication** (Part E) — a proposed amendment to
`SPEC-OPS-003` for recording (Part G), the incorporation amendments (Part H), and the plan for
taking them to ratification and implementation: existing defects vs new requirements (Part F),
remaining owner decisions (Part I), affected surfaces (Part J), sequence (Part K) and validation (Part L). Nothing here changes a template,
stylesheet, handler or ratified document. On ratification each text becomes or amends a numbered
document, is registered through
[SOP-DOC-001](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md), and this package
moves to `docs/archive/v2-tracking-2026/`.

**Revision history.** r1: one draft contract, 18 open decisions. r2: split into a design and an
operations document (owner ruling 2026-11-24, first round). r3: owner feedback of 2026-11-24 (second
round) applied — DES-1…6 and OPS-1…15 decided, an error-communication, outcome-safety, disclosure,
accuracy, resilience and protocol contract added, and every question already settled by a governing
document removed from the decision list.

> **Governing principle (owner, 2026-11-24).** An error page must reduce uncertainty without
> inventing certainty. It must help the user recover without compromising privacy, authority,
> economic integrity, or operational correctness. The presentation communicates the error; it does
> not establish domain truth. The teapot remains subject to the same requirements.
> *知其所知，不妄言其所不知。*

## Why this exists

The application's HTTP error pages had no governing contract. A search of every normative root
found three mentions, none of which defines the pages: SPEC-DES-001 §IX (shared error-page CSS lives
once under `body.error-page`), SPEC-OPS-004 (`/sysadmin/test-errors/<code>` are diagnostic probes)
and SOP-TEST-002 §X (error pages are covered by render fixtures and cannot be exempted). Structure,
content, actions, response format and logging were each decided per template and per handler, and
they drifted (Part B).

---

## Part 1 — Owner rulings applied

Both rounds of owner direction are applied in the drafts below; none is reopened. Existing
implementation is evidence of current behaviour, not authority over intended behaviour.

| Ruling | Lands in |
|---|---|
| Two documents: a SPEC-DES document for presentation, a SPEC-OPS document for communication, disclosure, response semantics and recovery actions | Part D, Part E |
| Neither document has independent authority; each operationalizes its incorporating document | D §III, E §III, Part H |
| DES-1 separate `SPEC-DES-002`; DES-2 incorporated through INV-ARC-020 | Part D, Part H.1 |
| DES-3 shared guidance and detail components, centrally styled, semantically structured | D §VI–VII |
| DES-4 header icon on every page | D §V.2 |
| DES-5 one semantic severity mapping, not derived from the status family alone | D §VIII |
| DES-6 no runtime JavaScript for accessibility attributes; they are in the markup | D §IX.2 |
| Status code + meaning together form the heading; consistent anatomy; optional sections only when applicable; tokens and shared components; no duplicated CSS or markup; icons and colour support, never carry, meaning; resilient rendering; DES does not choose content | D §V–X |
| OPS-1 response format and communication in SPEC-OPS-007; recording in the existing observability specification | Part E, Part G |
| OPS-2 incorporate through DOM-OPS-001 after verifying its scope | Part 2, Part H.2 |
| OPS-3 every page gives meaningful recovery guidance; Back only where appropriate and safe | E §IX |
| OPS-4 status link on service-failure pages, instance-configured and validated, omitted when unset | E §IX.4 |
| OPS-5 application logging, no database persistence for HTTP errors; remove the stubs and dead machinery | Part G; removal in Part F (X6) and Part K step 2 |
| OPS-5b severity by the nature of the event, not the status | Part G (already SPEC-OPS-003 §VI) |
| OPS-6 no auto-refresh on 503 | E §IX.3 |
| OPS-7 the existing opaque request identifier is the support reference; no separate error identity | E §VII.4 |
| OPS-8 never expose raw exception descriptions; only approved, sanitized explanations | E §VIII |
| OPS-9 accurate action labels, destinations, terminology, consistent order, fitted to the condition | E §IX |
| OPS-10 one response-format resolution contract and one JSON error shape; inventory consumers; preserve legitimate contracts in migration | E §X, Part B.6, Part K |
| OPS-11 standard headings, terminology and plain language | E §VI |
| OPS-12 one disclosure rule across all surfaces; distinguish authorization refusal from protected existence | E §VIII.3 |
| OPS-13 a canonical generic page for statuses without a template, preserving their semantics | E §V.2, D §XI |
| OPS-14 418 is inside the contract | E §V.1, Part B.5 |
| OPS-15 a controlled 429 probe that consumes no real rate-limit budget | E §XII |
| Communication contract (what happened, what it means, what is known of the outcome, what to do, whether to get help); no 4xx-is-your-fault rule | E §VI |
| Outcome and recovery safety (rejected / failed / succeeded / unknown; no reconstruction of domain truth; no unsupported assurances; retries never resubmit; Back never the only route) | E §VII, §IX |
| Disclosure and privacy list, including logs and fallbacks | E §VIII, Part G |
| Operational accuracy (no false "logged", no estimates, no whole-service claims for one refusal, instance-specific status, 418 not a health event) | E §XI |
| Rendering resilience | D §X, E §XIII |
| Protocol semantics (Retry-After, Allow, WWW-Authenticate; never convert an error to success; 418 stays 418) | E §X.4–6 |

## Part 2 — Authority chain, verified

| Text | Incorporating document | Verified | What ratification needs |
|---|---|---|---|
| `SPEC-DES-002` | **INV-ARC-020** (Constitutional) | §II covers templates, shared shells, template CSS and template-driven JS; §III says it "may be tightened by a stricter domain, spec, SOP, or gate document". Error templates are in scope. | INV-ARC-020 amendment: add SPEC-DES-002 to §IV and one line in §VII naming it as the presentation contract for HTTP error pages (Part H.1). SPEC-DES-001 §IX's sentence on error pages gains a pointer to SPEC-DES-002. |
| `SPEC-OPS-007` | **DOM-OPS-001** (Constitutional) | §1 makes Operations "the single authority over the Operational Truth", governing "how the system observes itself, records its behavior, and communicates its status to external actors"; it owns Correlation / Trace Identity (the request id used as support reference) and Status Page Publication State (the status link). It explicitly does **not** own business-domain truth — consistent with "the presentation does not establish domain truth". | DOM-OPS-001 amendment: add "HTTP error communication" to §1 *Operations OWNS* with SPEC-OPS-007 as its contract, and add SPEC-OPS-007 to §0 Dependencies (Part H.2). Without that line the scope fits only by reading "communicates its status" broadly; the owner asked for the chain to be verified, and the explicit line removes the inference. |
| Recording (Part G) | **SPEC-OPS-003** under DOM-OPS-001 | SPEC-OPS-003 is "Subordinate to … DOM-OPS-001"; DOM-OPS-001 owns Structured Operational Logs (INV-OPS-003) and §7 governs identifiers that leave the database. SPEC-OPS-003 §II today covers telemetry series only, so its scope must widen to error-response log records. | SPEC-OPS-003 v1.3 per Part G. |

### Already settled by governing documents (applied, not asked)

| Question | Settled by |
|---|---|
| Severity of an error event | SPEC-OPS-003 §VI: `SUCCESS` / `EXPECTED_DENIAL` / `SYSTEM_FAILURE`; "HTTP status alone MUST NOT determine this classification"; an expected denial "MUST NOT increase an operational failure metric" |
| No PII in logs or error output | INV-ARC-005 §V |
| Identifiers leaving the database | DOM-OPS-001 §7: logs and pages name a class by `class_public_id`/`join_code` and an actor by `seats.public_id`, never `class_id`, `seats.id` or `users.id` |
| Failed sign-in, lookup, claim or recovery must not reveal existence or membership | SPEC-SEC-001 §V (item 4) |
| Error paths on GET do not commit or flush | INV-ARC-007 §V |
| Heading order, accessible names, contrast, colour not the only carrier | INV-ARC-020 §VI, §VII, §IX |
| Shared CSS promoted, tokens only | SPEC-DES-001 §IX |
| Every error template has a render fixture, no exemption | SOP-TEST-002 §X |
| 404 is a descriptive signal, not a failure; only 5xx fails the endpoint check | SPEC-OPS-006 v1.5, v1.7 |
| `/teapot`'s 418 is not a request error (status sampler) | SPEC-OPS-006 v1.8 (PR #1839, pending merge) |
| Test-error routes are sysadmin-only diagnostics | SPEC-OPS-004 |
| Validation proportional, exact command recorded, accessibility boundary included | INV-ARC-017 §V–VI |

### Why the drafts are still not registered

SOP-DOC-000 does not provide for registering a draft, and
`tests/dom/docs/test_documentation_index_complete.py` requires every numbered file in a normative
root to be in SOP-DOC-001, so a numbered draft would be indexed beside ratified documents (the
`FEAT-OBL-004` DRAFT precedent). The texts stay unnumbered here until ratified.

---

## Part A — Sources inventoried

| Surface | Location |
|---|---|
| Templates | `templates/error_400.html`, `error_401.html`, `error_403.html`, `error_404.html`, `error_429.html`, `error_500.html`, `error_503.html`. `error_418.html` is on the unmerged `claude/teapot-418` branch (PR #1839); see B.5. |
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

### B.5 HTTP 418 (`/teapot`, PR #1839, branch `claude/teapot-418`, not merged)

Read from the branch, not edited. `main.teapot` (GET, `abort(418)`, no writes); `wsgi.im_a_teapot`
renders `error_418.html` with status line `418 I'm a teapot`, logs nothing and calls no
`log_error_to_db`; `status_service/log_sampler.py` excludes `/teapot` (SPEC-OPS-006 1.8); render
fixture and handler test added. The page: header icon `emoji_food_beverage`, `info` card "BREW is not
defined" (icon `kettle`), guidance in a `.troubleshooting` div under an **`h5`** with browser bullets
and no page-local CSS, actions "Return to Login Page" (`/`), "Go Back to Last Page", and an external
"Read RFC 2324" link; the inline `aria-hidden` script. The branch also makes the 404 header icon a
link to `/teapot` (`aria-label="Something is brewing"`) and drops 404's typed `•` bullets.

### B.6 JSON error consumers

| Producer | Shape | Known consumers |
|---|---|---|
| 429 on `/api/*` | `{status: "error", error, message}` + `Retry-After` | any `/api/` caller; scripts calling `r.json()` (the reason the branch exists, per the handler comment) |
| API context errors (`api.handle_api_context_resolution_error`) | `{status: "error", message, error}`, 404 or 401 | `static/js/attendance.js` branches on `r.status === 401` (lines 94, 192) |
| Unhandled 500 with `Accept: application/json` | `{error: "Internal Server Error"}` | `templates/admin_students.html` (≈1200) treats `status >= 500` or a body without `status ∈ {success, error}` as failure — compatible with the API shape |
| `student._setup_storage_unavailable` (503), `_setup_state_expired` (409) | `{verified, message}`, `{verified, redirect}` | student setup / credential pages (`Accept: application/json` fetches) |
| Other `accept_mimetypes.best == 'application/json'` branches | route-specific | 18 occurrences across `app/`; e.g. `identity_establishment.py:90`, `student.py:864–908` |

22 files under `static/js/` and `templates/` call `fetch(`, and 54 lines read `data.error` /
`data.message`. They were not each traced to a producer; Part K step 3 does that before any shape
changes.

### B.7 What an error render depends on

Error templates are standalone, but every `render_template` runs all global context processors
(`app/__init__.py` ≈708–975). For a signed-in request they call `get_current_user()` (session +
`users` query), `resolve_canonical_context()`, `ClassEconomy` and `IdentityProfile` queries and the
feature-settings lookups. Each is wrapped in `try/except` with a default, so a database failure does
not stop the page, but each still attempts its query (paying connection timeouts when the database
is unreachable) and works through a session whose transaction may already be aborted. The 500
handler in `app/__init__.py` falls back to plain text if the template fails; the `wsgi.py` handlers
have no fallback.

### B.8 Protocol behaviour

| Header / semantic | Today |
|---|---|
| `Retry-After` on 429 | Only on the `/api/` JSON branch; the HTML 429 sends none |
| `WWW-Authenticate` on 401 | Never sent (`wsgi.unauthorized_error`, API JSON 401). RFC 9110 §15.5.2 requires it on every 401 |
| `Allow` on 405 | Werkzeug's default 405 response carries it; no application handler exists for 405, so it survives |
| 418 status line | `418 I'm a teapot`, a real 418 (branch) |
| Error converted to success | None found |
| `STATUS_PAGE_URL` validation | `get_validated_status_page_url()` accepts only `https://status.classroomtokenhub.com` and `https://stats.uptimerobot.com`; a self-hosted instance cannot configure its own (already recorded in `docs/self-hosting/handbook-overview.md` and `configuration.md`) |
| Request identifier | `g.request_id` is the caller's `X-Request-Id` / `X-Correlation-Id` header when present (≤128 chars, otherwise unvalidated), else `uuid4().hex` |
| Logged URL | `wsgi.py` handlers log `request.url` (with query string) through `sanitize_for_log`, which escapes control characters but keeps query values |

---

## Part D — Draft: `SPEC-DES-002` HTTP Error Page Presentation (UNRATIFIED)

> Specific wording in this draft — heading texts, labels, the severity table's rows, class names —
> is a proposal inside the ruled direction. The owner may change any of it at ratification without
> reopening a ruling. Items marked I-n are the remaining genuine decisions (Part I).

### I. Purpose

Define the presentation contract for HTTP error pages: the anatomy every page shares, the shared
components that render it, the semantic structure and accessibility of that presentation, and how
it stays renderable when ordinary infrastructure is not. It decides how a page looks and is built,
never what it says.

### II. Scope

Applies to every `templates/error_<code>.html` template, the canonical generic error template
(§XI), the macros they call, and the Error Pages section of `static/css/style.css`. Does not govern
which information, recovery actions or operational claims appear on a page, response format, or
recording — those belong to `SPEC-OPS-007` and `SPEC-OPS-003`. Does not govern responses produced in
front of the application (proxy, Cloudflare, maintenance gate).

### III. Authority Level

Normative (Tier 2), technical contract. It has no independent authority: it operationalizes
INV-ARC-020 for HTTP error pages and binds through INV-ARC-020's incorporation. Subordinate to
INV-CORE-000, INV-ARC-020 and SPEC-DES-001, whose token architecture and shared-surface rule it
applies and must not weaken. Where this document and INV-ARC-020 disagree, INV-ARC-020 governs.

### IV. Dependencies

INV-CORE-000, INV-ARC-020, INV-ARC-007, SPEC-DES-001, SPEC-OPS-007, SOP-TEST-002.

### V. Anatomy

Every error page has the same anatomy; content and actions vary by status (SPEC-OPS-007). In order:

1. **Shell.** `<html lang="en">`; stylesheets Bootstrap, `fonts.css`, `tokens.css`, `style.css`, in
   that order, from local static files; `<title>` "`<code>` – `<meaning>`"; `<body class="error-page">`;
   one `<main id="main-content" aria-labelledby="error-heading">` holding everything below.
2. **Header.** A decorative Material Symbol, required on every page, then the page heading. The
   HTTP status code and its human-readable meaning **together** form the one `h1`
   (`id="error-heading"`), e.g. `<h1 id="error-heading"><span class="error-code">404</span>
   <span class="error-meaning">Page not found</span></h1>`, styled as two lines. A screen reader
   hears "404 Page not found" as the page's heading; neither part stands alone as a heading or as a
   `<p>`.
3. **Explanation.** The shared explanation component (§VI) with an `h2`, stating what happened.
4. **Detail** — only when SPEC-OPS-007 supplies a fact for this response (e.g. a support reference).
5. **Guidance** — the shared guidance component (§VI): an `h2` and a `<ul>` of what the visitor can
   do. Present on every page, because SPEC-OPS-007 §IX requires guidance on every page.
6. **Actions** — the shared action row; set and order come from SPEC-OPS-007 §IX.

A section with nothing to show is omitted entirely, never rendered empty, as a placeholder, or as
"none".

### VI. Shared components

1. Explanation, detail, guidance and the action row are each rendered by one macro in
   `templates/macros/` (or the existing `alert_card` where it meets §VII), called with content from
   the handler. Pages differ in the arguments they pass, not in markup they repeat.
2. A page does not re-create one of these components in its own markup or CSS because its words
   differ. Duplicated structure is a defect under SPEC-DES-001 §IX.
3. A component unique to one status (e.g. 401's sign-in choices) is allowed only when no shared
   component expresses it, and it still uses tokens and shared classes.

### VII. Styling

1. All error-page styling lives once under `body.error-page` in the Error Pages section of
   `style.css`. An error template carries no `<style>` block and no inline `style` attribute.
2. Values come from design tokens (SPEC-DES-001 §VI). The header band takes the role theme carried by
   `tokens.css`; no page sets a role colour.
3. Lists keep native list semantics and markers; a marker is never typed as text.

### VIII. Severity mapping

1. Visual severity expresses the **condition being communicated**, not the HTTP status family. The
   mapping is one table, owned here and applied by the explanation component:

   | Condition (from SPEC-OPS-007 §VI) | Severity token |
   |---|---|
   | Informational, nothing went wrong (e.g. 418) | `info` |
   | Request not completed, visitor can correct or wait (e.g. 400, 401, 404, 429) | `info` |
   | Request refused by a rule (e.g. 403) | `warning` |
   | Application could not complete the request (e.g. 500, 503) | `warning` |
   | Outcome of a state-changing action unknown (SPEC-OPS-007 §VII) | `danger` |

   *(Proposed mapping; the owner decided that one mapping exists and that status family alone does
   not set it, not this table's rows — see Part I, I-4.)*
2. Severity is never conveyed by colour or icon alone: the heading and explanation state it in words.

### IX. Accessibility

1. One `h1` (§V.2); every other heading is `h2` unless nested under an `h2`; no level is skipped
   (INV-ARC-020 §VI.1–2, §IX.3).
2. Every attribute accessibility depends on (`aria-hidden` on decorative icons, accessible names,
   "(opens in a new tab)") is present in the server-rendered markup. No script adds, repairs or
   removes accessibility attributes.
3. Icons are decorative (`aria-hidden="true"`), and never the only carrier of meaning. An icon that
   is a control has an accessible name describing its destination or effect (INV-ARC-020 §VI.4).
4. Contrast meets WCAG 2.1 AA in the rendered role theme (INV-ARC-020 §VII.D).
5. Nothing on the page moves, changes or navigates on a timer.
6. Every template has a SOP-TEST-002 render fixture, with one state for each optional section that
   changes the rendered surface.

### X. Rendering resilience

1. An error template depends only on: the values its handler passes, `url_for`/`static_url`, and
   static files served by the application. It reads no session value, current user, class context,
   feature setting or domain row, and calls no service.
2. It extends no layout and includes no partial that does.
3. A script on an error page is optional to its meaning: with scripts disabled every section and
   every action other than "Go back" still works.
4. The handler-side obligations (no context-processor queries, plain-text fallback) are
   SPEC-OPS-007 §XIII.

### XI. Generic error page

`templates/error.html` renders any status without a dedicated template, with the §V anatomy, a
generic icon, and content supplied by SPEC-OPS-007 §V.2. A dedicated template exists only where a
status needs content or a component the generic page cannot take as arguments.

### XII. Adding a status page

Prefer the generic page with status-specific arguments. Where a dedicated template is needed, build
it from §V–VII using only shared components and classes, add its render fixture, and add the status
to SPEC-OPS-007 §V.1 in the same change.

### XIII. Amendment

SOP-DOC-000 §XIII; register through SOP-DOC-001; INV-ARC-020's incorporation reference is updated in
the same change.

---

## Part E — Draft: `SPEC-OPS-007` HTTP Error Communication (UNRATIFIED)

> Specific wording in this draft — heading texts, labels, the outcome table's examples, the resolver
> rule, the JSON field names — is a proposal inside the ruled direction. The owner may change any of
> it at ratification without reopening a ruling. Items marked I-n are the remaining genuine decisions
> (Part I).

### I. Purpose

Define what the application communicates when ordinary execution of a request cannot proceed: what
an error response tells its recipient, what it must never tell them, what is and is not known about
the outcome of what they attempted, what they can safely do next, and how the response is formed at
the protocol level. An error response reduces uncertainty without inventing certainty.

### II. Scope

Applies to every 4xx or 5xx response the application produces through an error handler — the HTML
page, the JSON body, the plain-text fallback — including easter-egg statuses. Does not govern
presentation (`SPEC-DES-002`), recording and observability (`SPEC-OPS-003`), validation messages
inside a working page, flash messages, redirects, or responses produced in front of the application.

### III. Authority Level

Normative (Tier 2), technical contract. It has no independent authority: it operationalizes
DOM-OPS-001's authority over how the system communicates its status to external actors and binds
through DOM-OPS-001's incorporation. Subordinate to INV-CORE-000, INV-ARC-004, INV-ARC-005,
INV-ARC-007, INV-ARC-020 and DOM-OPS-001. It establishes no domain truth: Operations does not own
business-domain truth (DOM-OPS-001 §1).

### IV. Dependencies

INV-CORE-000, INV-ARC-004, INV-ARC-005, INV-ARC-007, INV-ARC-020, DOM-OPS-001, SPEC-OPS-003,
SPEC-OPS-004, SPEC-OPS-006, SPEC-SEC-001, SPEC-DES-002, REF-TERM-002 (informative).

### V. Statuses

1. Dedicated pages: 400, 401, 403, 404, 418, 429, 500, 503. Each has exactly one application-level
   handler.
2. Every other 4xx/5xx the application emits is answered by the generic error response
   (SPEC-DES-002 §XI) with its **original status code, reason phrase and status-specific headers**
   preserved, and with content chosen by the condition classes in §VI.
3. 418 is an intentional, informational response. It is subject to every rule here.

### VI. What every error response communicates

Where applicable, in plain language and REF-TERM-002 vocabulary (accessibility governs where they
conflict):

1. **What happened** — the established fact, e.g. "This page doesn't exist" or "Too many attempts in
   a short time".
2. **What it means for the user** — e.g. "Nothing on this page needs your attention".
3. **What is known about the outcome** of the attempted action (§VII).
4. **What the user can safely do next** (§IX).
5. **Whether further help is appropriate and how to get it**, with the support reference (§VII.4)
   when one applies.

Rules:

- State established facts; assign no blame that the facts do not support. An HTTP status family
  describes response semantics, not responsibility: a 400 may come from defective application
  JavaScript, a 404 from a stale link the application itself rendered.
- Fixed section headings on every page: the explanation's heading is the condition in words; the
  guidance heading is **"What you can do"**; a help line, where present, is **"Getting help"**.
- One vocabulary: "sign in" (not "log in"/"login"), "teacher" and "student" (not "admin"),
  REF-TERM-002 terms throughout, no developer terms.

### VII. Outcome and recovery safety

An unsuccessful HTTP response does not establish an unsuccessful domain operation: an operation may
have committed before a later step (rendering, a follow-on call) failed.

1. Every handler classifies the attempted action's outcome as one of:

   | Outcome | Known when | Communicate |
   |---|---|---|
   | **Rejected before execution** | Refused before any command ran: routing (404), authentication (401), authorization (403), validation (400), rate limit (429), 418 | The condition and its correction. Nothing changed because nothing was attempted. |
   | **Confirmed unsuccessful** | The owning execution contract reported the command rolled back | Retry guidance where safe |
   | **Confirmed successful** | The owning execution contract reported commit | Never instruct a repeat |
   | **Unknown** | Anything else, including every unhandled exception after a state-changing request began, and 500/503 on a non-GET request | "This may or may not have gone through." Advise checking the relevant page (balance, history, the item) before trying again |

2. The classification is taken from facts the request already holds — the method (a GET is
   read-only by INV-ARC-007, so its outcome cannot be a changed state), whether the failure was
   raised before the command boundary, and what the execution contract reports. A handler or template
   never queries domain state to reconstruct an outcome.
3. No response claims that an account, balance, transaction, attendance record or class is
   unchanged unless the execution contract supports it.
4. **Support reference.** Where help is appropriate, the page shows the request's existing opaque
   identifier (`g.request_id`) as the reference to quote. It is shown only when it is an opaque token
   (`[A-Za-z0-9-]{1,128}`; the identifier can come from a request header), and omitted otherwise. No
   separate error identity is created.

### VIII. What an error response must not convey

In HTML, JSON, plain-text fallbacks and the log lines they cause:

1. Raw exception messages or descriptions (`str(e)`, `error.description`), stack traces, exception
   class names, SQL or database internals, filesystem paths, credentials, tokens, configuration
   values or secrets, PII (INV-ARC-005).
2. Unsanitized URLs or query parameters. A page may show the requested **path**, escaped and without
   query string or fragment, only where it helps (404).
3. **Protected resource existence.** One rule on every surface: a resource the actor may not know
   exists is answered exactly as one that does not exist (404, the same body). An authorization refusal (403) is used only where the resource's existence is already
   known to the actor and the refusal is the useful fact (e.g. a student opening a teacher-only page
   they reached from a public link). Sign-in, lookup, claim and recovery follow SPEC-SEC-001 §V.
   *(The boundary between the two is proposed wording; see I-6.)*
4. Internal identifiers without an established disclosure purpose (DOM-OPS-001 §7). The support
   reference (§VII.4) is the one established purpose.
5. Explanations come from an approved set per condition class, owned by the handler; a `description`
   passed to `abort()` is not shown.

### IX. Recovery actions

1. **Every page offers meaningful guidance** (§VI.4) and **a safe destination**: a link that does
   not depend on re-running the failed request — the role's home when signed in, the sign-in page
   when not. Its label names that destination ("Go to your dashboard", "Go to sign in"), never
   "Return to Login Page" for `/`.
2. **Go back** appears only when returning is appropriate and safe: on a GET-initiated error page,
   and never as the only route. It is omitted after an Unknown outcome on a state-changing request,
   where going back can resubmit.
3. **Try again** appears only for a Confirmed-unsuccessful or a read-only (GET) failure, and re-issues
   a GET of the same URL. It never resubmits a form or repeats a state-changing request. No page
   refreshes itself.
4. **Status page** appears only where the condition is, or may be, a service failure (500, 503,
   generic 5xx). Its URL is the instance's configured, validated `STATUS_PAGE_URL`; with none
   configured, the link is omitted — absence is a legitimate deployment state and there is no
   fallback URL. A refusal (4xx) never links to the status page.
5. **Sign in** (401): one choice per role, labelled "Student sign in" and "Teacher sign in".
6. Order on every page: safe destination, then the condition-specific action (Sign in / Try again),
   then Go back, then Status page.

### X. Response format and protocol

1. **Resolution.** One function decides HTML vs JSON for every error handler: JSON when the request
   path is under `/api/`, or when the request's best `Accept` match is `application/json`; HTML
   otherwise. *(Proposed rule — the owner decided there is one resolver, not this rule; see I-5.)*
2. **JSON shape.** `{"status": "error", "error": <short condition>, "message": <plain-language
   explanation>}`, plus `"reference"` when §VII.4 applies. This is the shape `/api/` already emits.
   Existing route-specific shapes with consumers (B.6) are migrated per Part K, not broken.
3. The status code is never changed by presentation. The resolver never turns an error into a 2xx
   or 3xx; 418 is sent as 418.
4. Status-specific headers are preserved or supplied: `Retry-After` on every 429 (HTML and JSON)
   when the limiter knows the reset time; `Allow` on 405 (from the `HTTPException`'s headers);
   `WWW-Authenticate` on 401 per Part I, I-1.
5. **Fallback.** If the page cannot render, the response is a short fixed plain-text message with
   the same status and headers, and no exception detail.
6. Presentation is separate from status: a handler first fixes status and headers, then chooses the
   representation.

### XI. Operational accuracy

A page never:

1. says an error was recorded, logged or reported unless that recording happened in this request;
2. gives a recovery estimate ("5–10 minutes", "as quickly as possible") the system cannot support;
3. says the service, the class or the account is unavailable when one operation was refused —
   a 503 raised by one capability (e.g. `SetupUnavailable`) says that capability is unavailable;
4. implies the hosted CTH instance's status represents another, independently hosted instance (§IX.4);
5. presents an expected denial (SPEC-OPS-003 §VI `EXPECTED_DENIAL`) as an infrastructure failure.

An intentional 418 degrades no health check, monitor or alert (SPEC-OPS-006 1.8); ordinary access
logging still applies.

### XII. Diagnostics

1. Every status in §V.1 has a sysadmin probe at `/sysadmin/test-errors/<code>` (SPEC-OPS-004),
   including **429**, which raises `TooManyRequests` directly. It does not call the limiter, so it
   consumes no rate-limit budget and cannot lock the operator out.
2. Each handler has tests for: status and reason, headers (§X.4), HTML/JSON resolution, the fallback,
   the outcome class and the actions shown for it, and the disclosure rules (§VIII).

### XIII. Rendering resilience (handler side)

1. An error response does not require the infrastructure whose failure may have caused it. Error
   rendering performs no database query, class-context resolution, session restoration, domain
   query or external call; it uses already-established request facts (`g.request_id`, the status,
   the method) only where lawful and necessary.
2. Global context processors do not run their queries for error renders (or error templates are
   rendered without them).
3. No error path commits or flushes (INV-ARC-007); any pending transaction is rolled back before
   rendering.
4. No authority-sensitive operation is added to render an error.

### XIV. Amendment

SOP-DOC-000 §XIII; register through SOP-DOC-001; DOM-OPS-001's incorporation reference is updated in
the same change.

---

## Part F — Existing compliance defects vs newly established requirements

**Defects** break a rule already in force; they are remediation, not exceptions, and need no
decision. **New requirements** come from the drafts and bind only once ratified. Neither column turns
a current inconsistency into a permanent exception.

### F.1 Existing compliance defects

| # | Defect | Rule broken | Where |
|---|---|---|---|
| X1 | Heading levels skipped (`h5`/`h6` after an `h2`) | INV-ARC-020 §VI.2, §IX.3 | 400, 429 (`.error-message h5`), 401 (`.login-links h6`), 404 (`.troubleshooting h5`), 418 (branch, `h5`), 503 (`.status-box h5`) |
| X2 | Raw `error.description` shown to the visitor | INV-ARC-005; owner disclosure ruling | `error_400.html` `<code>{{ error_message }}</code>`; `wsgi.bad_request_error` |
| X3 | Full `request.url` (with query string) shown on the page | owner disclosure ruling (unsanitized URLs and query parameters) | `error_404.html` `.requested-url`; `wsgi.not_found_error` |
| X4 | Full `request.url` and raw `error.description` written to logs | INV-ARC-005 §V; DOM-OPS-001 §7 | every `wsgi.py` handler's `app.logger` call |
| X5 | Page says the error was logged with an Error ID; nothing is recorded and `error_id` is always `None` | owner accuracy ruling; INV-OPS-009 visibility | `error_500.html`; `wsgi.internal_error` |
| X6 | Logging stubs and dead machinery: `log_error_to_db` (returns `None`), the 404 dedupe cache feeding it, the `error_events` insert into a dropped table, `get_last_log_lines` on the 500 path, `copyLogs()` reading a missing element | owner OPS-5 | `wsgi.py`, `app/__init__.py`, `error_500.html`, `tests/test_404_dedupe_cache.py` |
| X7 | No `WWW-Authenticate` on 401 | RFC 9110 §15.5.2; owner protocol ruling | `wsgi.unauthorized_error`, `api.handle_api_context_resolution_error` (subject to I-1) |
| X8 | No `Retry-After` on the HTML 429 | owner protocol ruling | `wsgi.too_many_requests_error` |
| X9 | Duplicated presentation (`.error-message` in 400 and 429; `.troubleshooting` in `style.css` and 404's block) | SPEC-DES-001 §IX | `error_400.html`, `error_429.html`, `error_404.html` |
| X10 | Status link hard-coded to the hosted instance on every page, including self-hosted ones | owner accuracy ruling | all templates |
| X11 | 503 claims the whole service is disrupted when one capability (`SetupUnavailable`) raised it; "as quickly as possible", "5–10 minutes" | owner accuracy ruling | `error_503.html`, `student._setup_storage_unavailable` |
| X12 | 500 advises "You may try again" after an unknown outcome | owner outcome-safety ruling | `error_500.html` |
| X13 | 503 auto-refresh after 30 s, not stoppable | owner OPS-6; WCAG 2.2.1 under INV-ARC-020 §VII | `error_503.html` |
| X14 | Inline JavaScript re-applying `aria-hidden` | owner DES-6 | every template |
| X15 | "Admin Login", "Return to Login Page" pointing at `/` | owner OPS-9; REF-TERM-002 | 401, all pages |

### F.2 Newly established requirements (after ratification)

| # | Requirement | Source |
|---|---|---|
| N1 | Code + meaning as one `h1`; required header icon on every page (503 has none) | DES §V.2 |
| N2 | Shared explanation / detail / guidance / action components; no page `<style>` | DES §VI–VII |
| N3 | One severity mapping | DES §VIII |
| N4 | Error templates and handlers independent of session, DB and context processors | DES §X, OPS §XIII |
| N5 | Generic `error.html` for statuses without a page, original semantics preserved | DES §XI, OPS §V.2 |
| N6 | Communication contract and fixed headings | OPS §VI |
| N7 | Outcome classification and outcome-safe actions | OPS §VII, §IX |
| N8 | Support reference from `g.request_id`, validated | OPS §VII.4 |
| N9 | One disclosure rule across surfaces (admin `abort(403)` sites reviewed) | OPS §VIII.3 |
| N10 | One response-format resolver and one JSON shape | OPS §X |
| N11 | 429 probe that bypasses the limiter | OPS §XII |
| N12 | Error-response log record (Part G) | SPEC-OPS-003 v1.3 |

## Part G — Proposed amendment: `SPEC-OPS-003` v1.3 (recording)

Proposed text, to be added after §VIII; §II's scope gains "and the log record of an HTTP error
response".

> ### VIII.A Error-response log records
>
> 1. An HTTP error response is recorded in the application log only. No table stores HTTP error
>    responses; the error-logging stubs are removed. *(A future persistence requirement must come
>    from a governing contract first.)*
> 2. Each handled error writes exactly one record, at the handler, carrying: request id, method,
>    route rule (or path without query string when unmatched), status, outcome class (§VI), and
>    for a `SYSTEM_FAILURE` the exception class name. Class and actor appear only as DOM-OPS-001 §7
>    public aliases.
> 3. Level follows the outcome, not the status: `SUCCESS` or an intentional informational response
>    (418) — no error record (access logging only); `EXPECTED_DENIAL` (routine 4xx, rate limiting,
>    refused access) — `INFO`, or `WARNING` where the owning contract marks it as a signal worth
>    attention; `SYSTEM_FAILURE` — `ERROR` with the traceback in the log record only.
> 4. A record never contains exception text other than in a `SYSTEM_FAILURE` traceback, a query
>    string, request body values, headers other than the request id, or PII (INV-ARC-005).
> 5. Recording never raises, never changes the response, and never writes to the database
>    (INV-ARC-007 on GET; §VII here).

## Part H — Incorporation amendments (for ratification)

1. **INV-ARC-020** (minor version): add `SPEC-DES-002` to §IV; add to §VII: "HTTP error pages follow
   `SPEC-DES-002`, which this invariant incorporates as their presentation contract."
2. **DOM-OPS-001** (minor version): add to §1 *Operations OWNS*: "**HTTP Error Communication**: what
   the application tells a recipient when a request cannot proceed, governed by `SPEC-OPS-007`";
   add `SPEC-OPS-007` and `SPEC-OPS-003` to §0 Dependencies.
3. **SPEC-DES-001** (minor version): §IX's error-page sentence ends "…; their anatomy and components
   are governed by `SPEC-DES-002`."
4. **SPEC-OPS-004** (minor version): the probe list includes 418 and 429; probes never call the limiter.
5. **SOP-DOC-001**: register `SPEC-DES-002`, `SPEC-OPS-007` and the amended versions.

## Part I — Remaining genuine owner decisions

Only questions that no ruling and no governing document settles.

| # | Decision | Why it is genuine | Options |
|---|---|---|---|
| **I-1** | What does a 401 send as `WWW-Authenticate`? | RFC 9110 requires the header on every 401, but CTH authenticates with a session cookie and has no HTTP authentication scheme to name. The owner ruling says "where required" without choosing how. | (a) send a non-standard challenge naming the sign-in page (e.g. `WWW-Authenticate: Session realm="Classroom Token Hub"`); (b) stop answering cookie-authenticated HTML requests with 401 — redirect browsers to sign-in, keep 401 + challenge for `/api/` only; (c) use 403 for "not signed in" on HTML |
| **I-2** | How is an instance-specific `STATUS_PAGE_URL` validated? | The ruling requires a validated, instance-configured URL; today's validator is a two-origin allowlist written to stop an attacker planting a destination, and it rejects every self-hosted status page. | (a) `https` + the instance's own registrable domain (e.g. `status.<instance domain>`); (b) an operator-maintained allowlist in configuration; (c) `https` only, any host |
| **I-3** | May the 404 header icon stay a link to `/teapot`? | PR #1839 makes a decorative header icon an interactive control named "Something is brewing". DES §IX.3 requires a control's name to describe its destination; a hidden easter-egg control is a product choice the documents do not make. | (a) keep, named for its destination (e.g. "I'm a teapot"); (b) move the entry point out of the header; (c) remove the entry point |
| **I-4** | The severity table's rows (DES §VIII) | The ruling sets that one mapping exists and is not the status family alone; which condition gets which token is not ruled. | accept the proposed rows / revise |
| **I-5** | The resolver rule (OPS §X.1) | The ruling requires one resolver; JSON-by-path vs JSON-by-`Accept` changes behaviour for existing callers (B.6). | (a) path **or** `Accept` (proposed); (b) `Accept` only; (c) path only |
| **I-6** | Where 403 is allowed (OPS §VIII.3) | The ruling requires one rule distinguishing refusal from existence; 7 admin `abort(403)` sites and the student/API 404 mapping now disagree, and the boundary sentence is new wording. | accept the proposed boundary / revise |

Ratification also needs the owner's approval of Part G and Part H's amendments to ratified
documents; those are ratification steps, not open questions.

## Part J — Affected surfaces

| Surface | Items |
|---|---|
| Templates | `error_400/401/403/404/429/500/503.html`, `error_418.html` (PR #1839), new `error.html`, new error-page macros in `templates/macros/` |
| CSS | `static/css/style.css` Error Pages section (components move here; page blocks removed) |
| Handlers | `wsgi.py` (all error handlers, `log_error_to_db`, `get_last_log_lines`, 404 cache, `get_validated_status_page_url`); `app/__init__.py` (`register_error_handlers`, context processors, `_get_request_id`); `app/routes/api.py`, `app/routes/student.py` (context and setup handlers); admin `abort(403)` sites |
| API consumers | B.6 list; `static/js/attendance.js`; `templates/admin_students.html`; student setup pages; every remaining `fetch(` caller traced in Part K step 3 |
| Probes | `app/routes/system_admin.py` `/sysadmin/test-errors/*` (+418, +429) |
| Observability | application log format (SPEC-OPS-003 §VIII.A); Grafana queries reading error log lines; `status_service/log_sampler.py` (418 exclusion, PR #1839) |
| Accessibility fixtures | `tests/a11y_fixtures/public.py` (states per optional section, generic page) |
| Tests | `tests/test_error_handlers.py`, `tests/test_404_dedupe_cache.py` (deleted with the cache), new handler/resolver/disclosure tests |
| Docs | INV-ARC-020, DOM-OPS-001, SPEC-DES-001, SPEC-OPS-003, SPEC-OPS-004, SOP-DOC-001, `docs/self-hosting/` (status URL), CHANGELOG |

## Part K — Implementation and migration sequence (after ratification)

Specification work stays separate from runtime work: nothing below starts until Parts D, E, G and H
are ratified.

1. **Ratify and register** SPEC-DES-002, SPEC-OPS-007, SPEC-OPS-003 v1.3 and the Part H amendments,
   with I-1…I-6 answered. Merge PR #1839 first or rebase it onto the result; either way 418 is
   brought to the contract in step 5.
2. **Remove dead machinery** (X6): `log_error_to_db`, `get_last_log_lines` on the error path, the 404
   cache and its test, the `error_events` insert, `copyLogs()`, the `error_id` block. Pure deletion;
   behaviour unchanged because none of it did anything.
3. **Inventory JSON consumers**: trace every `fetch(` caller and `accept_mimetypes` branch in B.6 to
   the error statuses it can receive and the fields it reads. Output: a compatibility table attached
   to the PR.
4. **Handler layer**: one error module replacing the `wsgi.py` handlers — status/headers first
   (Retry-After everywhere, Allow preserved, WWW-Authenticate per I-1), outcome class, the resolver
   (I-5), the JSON shape with a compatibility path for any consumer step 3 finds reading another
   shape, the plain-text fallback, the log record (Part G), and rendering without context-processor
   queries. Fix X2, X3, X4, X7, X8 here.
5. **Presentation layer**: shared macros and CSS, then each template rebuilt on them, then `error.html`.
   Fixes X1, X9, X13, X14 and the N-requirements; content per OPS §VI–IX (X5, X10, X11, X12, X15).
6. **Disclosure rule** (N9, I-6): review each admin `abort(403)` site against OPS §VIII.3.
7. **Probes**: add 418 and 429 (limiter bypassed).
8. **Consumer migration**: move each route-specific JSON shape to the canonical one, consumer first,
   producer second, one PR per consumer group; remove compatibility paths when step 3's table is
   empty.
9. **Docs**: self-hosting status-URL guidance (I-2), CHANGELOG, release record.

Each step is its own PR with its own validation; steps 2 and 3 can run in parallel.

## Part L — Validation (INV-ARC-017)

Proportional to each step, scoped first, exact commands recorded, no partial run reported as whole.
Nothing is assigned to the operator as redundant or adversarial production testing; production is
checked only by the existing release SOP's browser checks (SOP-DEP-001B) for the changed pages.

| Boundary | Proved by |
|---|---|
| Protocol correctness | per status: status code and reason, `Retry-After` (HTML and JSON), `Allow` on 405, `WWW-Authenticate` on 401, 418 stays 418, no error becomes 2xx/3xx |
| Response format | resolver matrix (path × `Accept`), JSON shape, compatibility paths for traced consumers, plain-text fallback when the template raises |
| Outcome-safe recovery | GET vs non-GET, rejected vs unknown: Go back / Try again shown only where allowed; Try again is a GET; no page auto-refreshes |
| Disclosure | mutation tests: an `abort(400, description="SECRET")`, an exception message, a query string `?token=SECRET`, an internal id — none appears in HTML, JSON, fallback or the log record; forbidden and missing class-scoped resources give identical 404 responses |
| Operational accuracy | no "logged" text without a record; 503 from `SetupUnavailable` names the capability; status link present only with a configured URL, absent otherwise, only on 5xx |
| Rendering resilience | error pages render with the database unreachable and with an aborted transaction, signed in and signed out, issuing zero SQL statements (statement-count guard, as SOP-TEST-002 fixtures already use) |
| Recording | one record per error, level by outcome class, required fields, no prohibited fields (Part G) |
| Accessibility | SOP-TEST-002 axe gate on every error template and state, including `error.html` and 418; heading-order check |
| Structural guards | a guard that error templates carry no `<style>` and no accessibility-repair script, shipped with its mutation proof (SOP-TEST-003 §IX.A) |
| Adjacent regressions | `tests/test_error_handlers.py`, student/API context-error tests, status sampler tests, attendance.js 401 path, admin roster fetch error path |

## Not checked

- Rendered axe results for the current pages (not rerun for this package).
- Error responses produced by Cloudflare or the Access gate in front of the application.
- Each of the 22 `fetch(` callers individually (Part K step 3 does this).
- Grafana queries that read the current error log lines (affected by Part G's record format).
