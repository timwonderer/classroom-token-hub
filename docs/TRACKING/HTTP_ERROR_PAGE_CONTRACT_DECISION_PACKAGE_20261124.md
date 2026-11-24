# HTTP error pages: draft contracts, rulings and ratification plan

Date: November 24, 2026 (America/Los_Angeles), revision 5 — **final package for ratification**.
Status: **UNRATIFIED DRAFT — governs nothing.** This is an informative tracking package under
[SOP-DOC-000](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-000_DOCUMENTATION_STANDARD.md) §V–VI, not a
SPEC. It holds two proposed normative texts — **`SPEC-DES-002` HTTP Error Page Presentation**
(Part D) and **`SPEC-OPS-007` HTTP Error Communication** (Part E) — a proposed `SPEC-OPS-003`
amendment for error-response logging (Part F), the incorporation amendments (Part G), the
remaining conflicts with governing documentation (Part H), and the plan to ratification and implementation (Parts I–K).
Findings are classified in Part 3. Nothing here changes a template, stylesheet, handler or ratified
document. On ratification each text becomes or amends a numbered document, is registered through
[SOP-DOC-001](../STANDARD_OPERATING_PROCEDURES/SOP-DOC-001_DOCUMENTATION_INDEX.md), and this package
moves to `docs/archive/v2-tracking-2026/`.

**Revision history.**
r1: one draft contract, 18 open decisions.
r2: split into a design and an operations document (owner ruling, first round).
r3: owner feedback, second round — DES-1…6 and OPS-1…15 decided; communication, outcome-safety,
disclosure, accuracy, resilience and protocol contract added.
**r4: owner feedback, third round** — I-2…I-6 decided; I-1 investigated (Part H); request identifier,
path disclosure, diagnostic logging, outcome classification, transaction ownership, recovery actions
and scope corrected (B.1–B.7); findings split into invariant violations, implementation
inconsistencies, new requirements and unverified findings, with confirmed privacy violations
prioritized under existing authority (Part 3, Part J step 0).
**r5: owner feedback, fourth round** — H-1 ruled (401 kept for programmatic requests, documented as
a bounded protocol deviation); status-URL restrictions rebased on demonstrated risk (IP literals and
`localhost` allowed); no new card level (existing levels suffice); every page's safe destination
settled; V1 and V2 remediated separately under existing authority; historical exposure distinguished
from implementation violation (Part 3.5); remaining conflicts with governing documentation listed
(Part H). No owner decision remains open.

> **Governing principles (owner, 2026-11-24).** An error page must reduce uncertainty without
> inventing certainty. It must help the user recover without compromising privacy, authority,
> economic integrity, or operational correctness. The presentation communicates the error; it does
> not establish domain truth. The teapot remains subject to the same requirements.
> *知其所知，不妄言其所不知。* — *知其過，正其失，不以文飾其非。*

## Why this exists

The application's HTTP error pages had no governing contract. A search of every normative root
found three mentions, none of which defines the pages: SPEC-DES-001 §IX (shared error-page CSS lives
once under `body.error-page`), SPEC-OPS-004 (`/sysadmin/test-errors/<code>` are diagnostic probes)
and SOP-TEST-002 §X (error pages are covered by render fixtures and cannot be exempted). Structure,
content, actions, response format and logging were each decided per template, handler and route,
and they drifted (Part B).

---

## Part 1 — Owner rulings applied

All four rounds are applied in the drafts; none is reopened. Existing implementation is evidence of
current behaviour, not authority over intended behaviour. An owner-approved proposed requirement does
not make earlier implementation an invariant violation (Part 3 keeps the categories apart).

### Rounds 1–2 (structure, DES-1…6, OPS-1…15)

| Ruling | Lands in |
|---|---|
| Two documents; neither has independent authority | Part D, Part E, Part G |
| DES-1 separate `SPEC-DES-002`; DES-2 through INV-ARC-020 | D §III, G.1 |
| DES-3 shared guidance/detail components, central styling, semantic structure; DES-4 icon on every page; DES-6 no runtime accessibility script | D §V–VII, §IX |
| DES-5 one semantic severity mapping, not the status family | D §VIII (revised per I-4) |
| Code + meaning as the heading; consistent anatomy; optional sections only when applicable; tokens and shared components; no duplication; icons and colour support meaning; resilient rendering; DES does not choose content | D §V–X |
| OPS-1 communication and response format here; recording in the observability specification | Part E, Part F |
| OPS-2 through DOM-OPS-001 after verifying scope | Part 2, G.2 |
| OPS-3 meaningful guidance everywhere; Back only where appropriate and safe | E §IX (revised per B.6) |
| OPS-4 status link on service-failure pages, instance-configured | E §IX.4, E §XI (revised per I-2) |
| OPS-5 logging, no database persistence; remove stubs; OPS-5b severity by nature of the event | Part F; J step 2 |
| OPS-6 no 503 auto-refresh | E §IX.3 |
| OPS-7 existing opaque request identifier as support reference | E §VII.4 (revised per B.1) |
| OPS-8 no raw exception descriptions | E §VIII |
| OPS-9 accurate labels, destinations, terminology, order | E §IX |
| OPS-10 one resolver and JSON shape; inventory consumers; migrate | E §X (revised per I-5), B.6, J |
| OPS-11 standard headings, terminology, plain language | E §VI |
| OPS-12 one disclosure rule | E §VIII.3 (revised per I-6) |
| OPS-13 generic page preserving semantics; OPS-14 418 included; OPS-15 controlled 429 probe | E §V, §XII, D §XI |
| Communication contract; outcome safety; disclosure and privacy; operational accuracy; rendering resilience; protocol semantics | E §VI–XIII |

### Round 3

| Ruling | Lands in |
|---|---|
| **I-1** no invented challenge, no 403 for unauthenticated; investigate and recommend | B.10, Part H, E §X.5 |
| **I-2** operator-configured HTTPS status URL; structural validation; no provider allowlist; configuration is the trust boundary; none configured → no link | E §XI.6 |
| **I-3** keep the 404 icon as the easter-egg entry, accurately named, keyboard- and AT-reachable, icon decorative inside the link | D §V.2 |
| **I-4** five classes: informational, expected refusal, recoverable restriction, unexpected failure, uncertain outcome; uncertainty needs guidance, not escalation; severity is not incident classification | D §VIII |
| **I-5** path or explicit JSON preference; content negotiation; no inference from wildcards; consumer-preserving migration | E §X.1, J step 8 |
| **I-6** no assumptions about what a user knows; existence disclosed only where governing authority establishes visibility; no distinguishable lookup-failure vs unauthorized responses; 403 where the refusal itself discloses nothing protected; all surfaces | E §VIII.3 |
| **B.1** support references are server-generated and opaque; external correlation ids are not trusted, displayed or persisted | E §VII.4, Part 2.2, Part F, J step 0 |
| **B.2** no requested URL on the 404 page; route patterns in logs; privacy-safe representation for unmatched routes | E §VIII.2, Part F |
| **B.3** privacy-safe diagnostic representation; tracebacks and exception text stay under the privacy invariants | Part F |
| **B.4** outcomes from execution facts only, never from the status; Not applicable added; uncertainty when facts are missing | E §VII |
| **B.5** handlers own no transaction; commit, rollback and cleanup follow the established lifecycle | E §XIII, Part 2.3 |
| **B.6** no assumption that history navigation is safe; no resubmission; a history-independent safe destination; no GET presented as a retry of a POST | E §IX |
| **B.7** the contract covers every application-generated error response, route-local and blueprint-local included | E §II, B.9 |
| **C** keep four finding categories; prioritize confirmed privacy violations under existing authority; inventory Grafana before log-format changes | Part 3, J step 0, J step 4 |

### Round 4 (this revision)

| Ruling | Lands in |
|---|---|
| **H-1** keep explicit 401 for scripted and API requests without a valid session; keep browser-navigation redirects; no redirect of programmatic requests to HTML sign-in; no invented mechanism; the missing `WWW-Authenticate` is a bounded, documented protocol deviation, and no full RFC 9110 compliance is claimed for that response | E §X.5, Part 3 I5 |
| Status-URL restrictions rest on demonstrated security requirements; private-network instances are legitimate | E §XI.6 |
| Add no card level unless the existing design system cannot express the semantics | D §VIII (no new level) |
| Removing Back is acceptable only if every page keeps a meaningful, safe destination | E §IX.1, §XIII.1 |
| Remediate V1 and V2 now, separately scoped, under existing authority | Part 3.1, J step 0 |
| Read-only production investigation; never reproduce what it finds; separate implementation violation from historical exposure; keep audit lineage, retention and incident response; no silent rewriting of history | Part 3.5, J step 0c |
| Keep implementation and validation proportional; no authentication redesign | E §X.5, Part J, Part K |

## Part 2 — Authority chain, verified

### 2.1 Incorporation

| Text | Incorporating document | Verified | Ratification needs |
|---|---|---|---|
| `SPEC-DES-002` | **INV-ARC-020** | §II covers templates, shared shells, template CSS and template-driven JS; §III allows tightening by "a stricter domain, spec, SOP, or gate document" | G.1 |
| `SPEC-OPS-007` | **DOM-OPS-001** | §1: Operations governs how the system "communicates its status to external actors", owns Correlation / Trace Identity and Status Page Publication State, and does not own business-domain truth | G.2 (explicit "HTTP Error Communication" line) |
| Recording (Part F) | **SPEC-OPS-003** under DOM-OPS-001 | Subordinate to DOM-OPS-001, which owns Structured Operational Logs (INV-OPS-003) and §7 identifier rules; SPEC-OPS-003 §II covers telemetry only today | Part F (scope widened) |

### 2.2 Request identifier construction (B.1)

| Contract | Says |
|---|---|
| DOM-OPS-001 **INV-OPS-004** | Every request carries a stable `correlation_id`; "Identities must be generated at the entry point" |
| INV-ARC-001 §V | Request context contains `request_id` |
| INV-ARC-000 §X | Decisions are logged with `request_id` |
| DOM-OPS-002 §2.1 | `audit_events.request_id` is `String(64)`, "HTTP request identifier" |
| DOM-OPS-001 §5 | `correlation_id` columns are UUIDs |

The governing contracts already require a server-generated identifier; none authorizes adopting a
caller's. **No amendment to them is required.** The implementation that takes `X-Request-Id` /
`X-Correlation-Id` from the request (B.8) does not conform to INV-OPS-004 (Part 3, V3). Part F
states the construction explicitly for SPEC-OPS-003 so the rule sits beside the log format.

### 2.3 Transaction ownership (B.5)

INV-ARC-006 §V requires every mutation to occur inside explicit domain commands and forbids mutation
during request rendering. The FEAT layer owns the transaction:
`FEATContext.__enter__` opens it and `FEATContext.__exit__` commits on success and rolls back on
exception (`app/feats/base.py`). Request-level cleanup is Flask-SQLAlchemy 3.1's application-context
teardown, which removes the scoped session (rolling back anything uncommitted). An error handler is
neither: it commits nothing, rolls back nothing it does not own, and establishes no business outcome.
Today's `db.session.rollback()` calls in `wsgi.internal_error` and `app/__init__.handle_unhandled_exception`
exist so that the error render's own queries can run on an aborted session; once error rendering
issues no queries (E §XIII) they have no purpose and are removed (Part 3, I12).

### 2.4 Already settled by governing documents (applied, not asked)

| Question | Settled by |
|---|---|
| Severity of an error event in logs and metrics | SPEC-OPS-003 §VI (`SUCCESS` / `EXPECTED_DENIAL` / `SYSTEM_FAILURE`; status alone never decides) |
| No PII in request context or logs | INV-ARC-005 §V |
| Identifiers leaving the database (logs, pages, URLs) | DOM-OPS-001 §7 |
| Request identifier generated at the entry point | DOM-OPS-001 INV-OPS-004 |
| Failed sign-in, lookup, claim, recovery reveal no existence | SPEC-SEC-001 §V |
| GET purity on error paths | INV-ARC-007 §V |
| Transaction ownership | INV-ARC-006; FEAT layer (2.3) |
| Headings, names, contrast, colour | INV-ARC-020 §VI, §VII, §IX |
| Shared CSS promoted, tokens only, adding a token | SPEC-DES-001 §VI.5, §IX |
| Render fixtures, no exemption | SOP-TEST-002 §X |
| Only 5xx fails the endpoint check; 404 descriptive; `/teapot` excluded | SPEC-OPS-006 v1.5, v1.7, v1.8 (PR #1839) |
| Probes are sysadmin-only diagnostics | SPEC-OPS-004 |
| Validation proportional, commands recorded | INV-ARC-017 §V–VII |

### 2.5 Why the drafts are still not registered

SOP-DOC-000 does not provide for registering a draft, and
`tests/dom/docs/test_documentation_index_complete.py` requires every numbered file in a normative
root to be in SOP-DOC-001, so a numbered draft would be indexed beside ratified documents (the
`FEAT-OBL-004` DRAFT precedent). The texts stay unnumbered here until ratified.

## Part 3 — Findings, classified

Four categories, kept apart. A finding moves category only on new evidence.

### 3.1 Existing invariant violations (confirmed in code)

| # | Finding | Invariant | Evidence | Priority |
|---|---|---|---|---|
| **V1** | Error log lines carry the full request URL, including query values that hold a student's name or internal seat id (`?student=`) and internal class ids (`?class_id=`) | INV-ARC-005 §V; DOM-OPS-001 §7 | B.8 "Logged URL"; `wsgi.py` 400/401/403/404/429/503 handlers | **Remediated separately under existing authority** (J step 0a). Historical exposure: Part 3.5 |
| **V2** | The request identifier is taken from the caller's `X-Request-Id` / `X-Correlation-Id`, echoed in the response, written to every log line and persisted to `actor_request_trace` | DOM-OPS-001 INV-OPS-004 (generated at the entry point); INV-ARC-005 exposure if a caller places personal data in it | B.8 "Request identifier"; `app/__init__.py` `_get_request_id`, `attach_request_id_header`, `persist_request_trace` | **Remediated separately under existing authority** (J step 0b). Historical exposure: Part 3.5 |
| **V3** | Skipped heading levels (`h5`/`h6` after `h2`) | INV-ARC-020 §VI.2, §IX.3 | 400, 401, 404, 429, 503; 418 on PR #1839 | With the template rebuild (J step 6); small enough to fix earlier |

### 3.2 Existing implementation inconsistencies

No invariant is shown to be broken; each is inconsistent with another part of the system, a
ratified SPEC, an external standard, or the owner's intended behaviour.

| # | Finding | Measured against |
|---|---|---|
| I1 | `log_error_to_db`, the 404 dedupe cache, `get_last_log_lines` on the error path, the `error_events` insert into a dropped table and `copyLogs()` do nothing | dead code (OPS-5 removes it) |
| I2 | 500 page states the error "has been automatically logged" with an Error ID that can never render | the system's actual behaviour |
| I3 | 400 page shows `error.description` verbatim | intended disclosure rule; personal data in any description is unverified (U5) |
| I4 | 404 page shows the full requested URL, including the query string | intended disclosure rule; the same query values as V1 can appear on screen to the requester |
| I5 | No `WWW-Authenticate` on any 401 | RFC 9110 §15.5.2 (MUST). **Ruled (H-1):** a bounded, documented protocol deviation for cookie-session responses (E §X.5); not remediated, not claimed compliant |
| I6 | Credential-submission failures answered 401 although the sign-in endpoint requires no authentication | RFC 9110 §15.5.2 semantics. Folded into the H-1 deviation; not changed (proportionality: re-labelling would migrate three sign-in scripts for no user-visible effect) |
| I7 | `/api/` scope refusals (forbidden / mismatched class context) answered 401 "not logged in" by `login_required`, 404 by the API blueprint handler, 404 by the student blueprint, 403 in admin | consistency; owner I-6 |
| I8 | Three JSON shapes, three JSON-selection rules (path, `Accept` best match, none) | consistency |
| I9 | Status link hard-coded to the hosted instance; validator accepts two hosted origins only, so a self-hosted or private-network instance cannot configure its own | instance correctness |
| I10 | 503 claims a service-wide disruption and gives recovery estimates; it auto-refreshes; 500 advises "try again" | intended accuracy and outcome rules |
| I11 | Duplicated presentation (`.error-message` ×2; `.troubleshooting` in page block and `style.css`); runtime `aria-hidden` script | SPEC-DES-001 §IX; intended DES-6 |
| I12 | Error renders run every context processor (session, user, class, feature queries); handlers roll back a session they do not own so those queries can run | intended resilience and ownership rules (2.3) |
| I13 | "Admin Login", "Return to Login Page" → `/` (not a sign-in page) | REF-TERM-002; accuracy |

### 3.3 Newly established requirements (bind after ratification)

N1 code + meaning as one `h1`, icon on every page · N2 shared components, no page CSS · N3 five-class
severity on existing levels · N4 error rendering independent of session, database and context processors · N5 generic
`error.html` · N6 communication contract and fixed headings · N7 outcome classes from execution facts
· N8 server-generated support reference · N9 one disclosure rule across surfaces · N10 one resolver
and JSON shape · N11 limiter-free 429 probe · N12 error-response log record (Part F) · N13 every
application-generated error response in scope (B.9) · N14 instance-configured status URL validation.

### 3.4 Unverified findings

| # | Open question | How to settle it |
|---|---|---|
| U1 | Production nginx: does it set, clear or pass `X-Request-Id`? (repo has only the self-hosting template, which passes it) | read the production site config |
| U2 | Production `LOG_FORMAT`: with `json`, `JSON_LOG_FORMAT` interpolates values unescaped, so a quote in any value (including a caller's request id) would break the line | read the production environment |
| U3 | Do production application logs and nginx access logs contain V1's query values? (nginx logs the request line by default) | read-only Loki query over retained logs |
| U4 | Grafana dashboards, saved queries and alerts reading application error lines. None exists in the repository (`status_service/log_sampler.py` reads `nginx_access` only); production alert rules were recorded as 0 on 2026-10-03 | Grafana API inventory, read-only, before Part F changes the format (J step 4) |
| U5 | Do exception texts or `abort()` descriptions carry personal data? SQLAlchemy runs without `hide_parameters`, so statement errors include bound values; PII columns encrypt at bind (ciphertext), free-text columns are unchecked | trace in J step 3; Part F removes the exposure regardless |
| U6 | The 22 `fetch(` callers' dependence on error statuses and shapes | J step 3 |
| U7 | Error responses from Cloudflare and the Access gate | out of scope; separate review |

### 3.5 Implementation violation vs historical exposure (V1, V2)

A confirmed implementation violation (3.1) says the code could write prohibited information. Whether
it did is a separate fact, established only by reading what was written. The investigation was
read-only, reported aggregates only, and reproduced no value; nothing was modified, purged or
re-keyed.

**Implementation remediated** on branch `fix/error-log-url-and-request-id` (J step 0a/0b): one helper
(`loggable_route()`) now supplies the route pattern, or `<unmatched>`, to every site that logged or
persisted a raw path or URL. That covers the six `wsgi.py` handlers, the `endpoint` field of every
log record, the unhandled-exception record, the Cloudflare-origin warning, the two admin
class-context refusals, operational events and `actor_request_trace.endpoint`. The request id is
always generated. Four tests feed a sentinel through the path, query and `X-Request-Id` and assert it
reaches no log record, response header or trace row; with the fix reverted, all four and the updated
existing test fail.

**Historical exposure, production, 2026-11-24 (read-only, aggregate only):**

| Store | Retained window | Finding |
|---|---|---|
| `actor_request_trace` | 2026-11-17 → 2026-11-24 (bounded retention) | 1,604 rows; every `request_id` has the generated shape (32 lowercase hex); no `endpoint` looks like a raw path (numeric segment or characters outside a route pattern). **No exposure found in the retained window.** Rows older than the window have already been purged by retention and cannot be examined |
| `audit_events.request_id` | 2026-09-28 → 2026-11-24 | 5,374 rows; none has a `request_id` outside the generated shape. **No exposure found** |
| `operational_events` | — | 0 rows. **Nothing to expose** |
| Application journal (`classroom-economy` unit) | unknown | **Not examined.** Production shell access is the owner's; count-only commands are below |
| nginx access logs and their Loki copy (`nginx_access`) | unknown | **Not examined.** nginx logs the full request line, query included, by default; that is a proxy-layer record outside V1 (which concerns the application) and is listed as U3 |

A generated-shape id does not prove the id was generated, since a caller could send 32 hex
characters, but such an id carries no personal data, so the exposure question V2 raises is answered
for these stores.

**Count-only commands for the owner** (print numbers and a date, never a matching line):

```bash
journalctl -u classroom-economy --no-pager -o short-iso | head -1 | cut -c1-10
journalctl -u classroom-economy --no-pager -o cat | grep -cE '(Not Found|Forbidden|Unauthorized|Bad Request|Too Many|Rate|Service Unavailable)[^?]*[?&](student|class_id)='
sudo sh -c 'ls -1tr /var/log/nginx/access.log* | head -1 | xargs stat -c %y | cut -c1-10'
sudo sh -c 'zgrep -hcE "[?&](student|class_id)=" /var/log/nginx/access.log* | paste -sd+ - | bc'
```

**If a count is non-zero**, the exposure is confirmed for that store and is handled under
SOP-SEC-001 §V.4 (incident record: minimal, access-controlled, no values). Retention runs its normal
course; no log or trace is rewritten or selectively deleted outside the retention and incident
procedures, so audit lineage is kept. Whether earlier purging under retention has already removed
older exposure is recorded as unknown, not as absent.

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
| Other `accept_mimetypes.best == 'application/json'` branches | route-specific | 18 matching lines (`accept_mimetypes` or `wants_json`) across `app/`; e.g. `identity_establishment.py:90`, `student.py:864–908` |

22 files under `static/js/` and `templates/` call `fetch(`, and 54 lines read `data.error` /
`data.message`. They were not each traced to a producer; Part J step 3 does that before any shape
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
| `Retry-After` on 429 | Only on the `/api/` JSON branch; the HTML 429 sends none. RFC 6585 §4 makes it optional (MAY) |
| `WWW-Authenticate` on 401 | Never sent by any of the application's 401 responses (B.10). RFC 9110 §15.5.2: a server generating a 401 MUST send it |
| `Allow` on 405 | Werkzeug's default 405 response carries it (RFC 9110 §15.5.6: MUST); no application handler exists for 405, so it survives |
| 418 status line | `418 I'm a teapot`, a real 418 (branch) |
| Error converted to success | None found |
| `STATUS_PAGE_URL` validation | `get_validated_status_page_url()` accepts only `https://status.classroomtokenhub.com` and `https://stats.uptimerobot.com`; a self-hosted instance cannot configure its own (already recorded in `docs/self-hosting/handbook-overview.md` and `configuration.md`) |
| Request identifier | `g.request_id` is the caller's `X-Request-Id` / `X-Correlation-Id` header when present (any value up to 128 characters), else `uuid4().hex`. The value is echoed in the `X-Request-Id` response header, written into every application log line, and persisted in `actor_request_trace.request_id` (`String(128)`) by `persist_request_trace`. The self-hosting nginx template (`infra/self-hosting/templates/ingress.conf`) neither sets nor clears the header, so a client's value reaches the application |
| Logged URL | `wsgi.py` 400/401/403/404/429/503 handlers log `request.url` (full path and query string) through `sanitize_for_log`, which escapes control characters but keeps every value. Query strings that reach those lines include the teacher transaction filter `?student=` (a student's name or an internal seat id, `admin.py` ≈8776) and the admin class selector `?class_id=` (an internal class id, `admin.py` ≈399, `api.py` ≈1454) |

---

### B.9 Application-generated error responses outside the registered handlers

Route-local and blueprint-local code produces most of the application's error responses, so the
contract has to reach them (SPEC-OPS-007 §II).

| Form | Count in `app/` | Notes |
|---|---|---|
| `return …, <4xx/5xx>` (mostly `jsonify`) | ≈237 across 9 files: 400 ×105, 500 ×34, 403 ×28, 401 ×23, 409 ×22, 404 ×17, 503 ×8 | Shapes vary: `{status, error}`, `{status, message}`, `{error}`, `{verified, …}` |
| `abort(404)` | 82 | Rendered by the registered 404 handler |
| `abort(403)` | 7 (6 in `admin.py`, 1 in `class_configuration_query_service.py` docstring example) | Admin ownership checks (`verify_teacher_owns_class` returns `None` for both a missing and a foreign class, so missing and foreign answer alike) |
| Blueprint handlers | `api.handle_api_context_resolution_error` (403/404 → JSON 404, missing context → JSON 401), `student.handle_context_forbidden` (→ 404), `student._setup_*` (503/409) | |
| `login_required` (`app/auth.py`) | `/api/` callers with a forbidden or mismatched class context get **401 "User not logged in or session expired"**; browsers are redirected to sign-in | A scope refusal reported as an authentication failure |

Counts are pattern counts (`grep`), not a traced inventory; Part J step 3 traces them.

### B.10 Authentication flows and every 401 (I-1 investigation)

Authentication is a server-side signed session cookie (`RoleScopedSessionInterface`), established
by form, passkey or TOTP sign-in. The application implements no HTTP authentication scheme.

| Where | Who receives it | Today |
|---|---|---|
| `login_required`, `admin_required`, `system_admin_required` (`app/auth.py`) | Browser navigation | **302 redirect to the role's sign-in page** — never a 401 |
| same decorators, `/api/` or background requests (`_is_background_request`: `Sec-Fetch-Mode` ≠ navigate, JSON, or XHR) | Page scripts | JSON **401** (`authentication_required`, "Session expired", …), no `WWW-Authenticate` |
| Credential submission: `admin.py` ≈10299–10373, `system_admin.py` ≈318–390, `student.py` ≈3099, `admin.py` ≈7141 | Sign-in / passkey / TOTP scripts | JSON **401** "Invalid credentials" / "Authentication failed". The target (the sign-in endpoint) requires no authentication; the 401 reports a rejected submission |
| `api.py` ≈136, 355, 362, 1022, 1100 | `/api/` callers | JSON **401** for missing session or class context |
| `require_seat_context()` → `abort(401)` | Browser or script | HTML 401 page (`error_401.html`) |
| `system_admin.grafana_auth_check` | nginx `auth_request` only | 401 to nginx, which maps it to a sign-in redirect (`error_page 401 = @grafana_login_redirect`); a client never sees it |
| Known consumers | `static/js/attendance.js` (branches on `r.status === 401`, lines 94 and 192); sign-in pages' passkey/TOTP scripts; the onboarding-status poller on teacher pages | |

---

## Part D — Draft: `SPEC-DES-002` HTTP Error Page Presentation (UNRATIFIED)

> Specific wording — heading texts, class names, the severity table's token choices — is a proposal
> inside the ruled direction; the owner may change it at ratification without reopening a ruling.

### I. Purpose

Define the presentation contract for HTTP error pages: the anatomy every page shares, the shared
components that render it, the semantic structure and accessibility of that presentation, and how
it stays renderable when ordinary infrastructure is not. It decides how a page looks and is built,
never what it says.

### II. Scope

Applies to every full-page HTML error response the application renders: each
`templates/error_<code>.html`, the generic `templates/error.html` (§XI), the macros they call, and
the Error Pages section of `static/css/style.css`. Does not govern which information, recovery
actions or operational claims appear (`SPEC-OPS-007`), JSON or plain-text bodies, recording
(`SPEC-OPS-003`), or responses produced in front of the application.

### III. Authority Level

Normative (Tier 2), technical contract. No independent authority: it operationalizes INV-ARC-020 for
HTTP error pages and binds through INV-ARC-020's incorporation. Subordinate to INV-CORE-000,
INV-ARC-020 and SPEC-DES-001, whose token architecture and shared-surface rule it applies and must
not weaken. Where it and INV-ARC-020 disagree, INV-ARC-020 governs.

### IV. Dependencies

INV-CORE-000, INV-ARC-006, INV-ARC-007, INV-ARC-020, SPEC-DES-001, SPEC-OPS-007, SOP-TEST-002.

### V. Anatomy

Consistent anatomy; content and actions vary by condition (SPEC-OPS-007). In order:

1. **Shell.** `<html lang="en">`; stylesheets Bootstrap, `fonts.css`, `tokens.css`, `style.css`, in
   that order, from the application's static files; `<title>` "`<code>` – `<meaning>`";
   `<body class="error-page">`; one `<main id="main-content" aria-labelledby="error-heading">`.
2. **Header.** A Material Symbol icon on every page, then the heading. The HTTP status code and its
   human-readable meaning together form the one `h1` (`id="error-heading"`), e.g.
   `<h1 id="error-heading"><span class="error-code">404</span> <span class="error-meaning">Page not
   found</span></h1>`, styled as two lines.
   - The icon is decorative (`aria-hidden="true"`), except where it is the only content of a link.
   - **The 404 icon is the link to `/teapot`.** The link is keyboard-focusable in normal tab order,
     has a visible focus indicator, and its accessible name states its destination ("I'm a teapot
     (HTTP 418) page"); the icon inside it stays `aria-hidden`. It is the only interactive header
     element on any error page.
3. **Explanation** — the shared explanation component (§VI) with an `h2`.
4. **Detail** — only when SPEC-OPS-007 supplies a fact for this response (the support reference).
5. **Guidance** — the shared guidance component: an `h2` and a `<ul>`. Present on every page.
6. **Actions** — the shared action row; set and order from SPEC-OPS-007 §IX.

A section with nothing to show is omitted entirely: never rendered empty, as a placeholder, or as
"none". The 404 page has no requested-URL section (SPEC-OPS-007 §VIII.2).

### VI. Shared components

1. Explanation, detail, guidance and the action row are each rendered by one macro in
   `templates/macros/` (the explanation may be `alert_card` where it meets §VII–IX), called with
   content from the handler. Pages differ in the arguments they pass, not in markup they repeat.
2. A page does not re-create a component in its own markup or CSS because its words differ
   (SPEC-DES-001 §IX).
3. A component unique to one status (e.g. 401's sign-in choices) is allowed only when no shared
   component expresses it, and it uses tokens and shared classes.

### VII. Styling

1. All error-page styling lives once under `body.error-page` in the Error Pages section of
   `style.css`. An error template has no `<style>` block and no inline `style` attribute.
2. Values come from design tokens (SPEC-DES-001 §VI); a new token follows SPEC-DES-001 §VI.5. The
   header band takes the role theme from `tokens.css`; no page sets a role colour.
3. Lists keep native semantics and markers; a marker is never typed as text.

### VIII. Severity mapping

1. Visual severity expresses the **condition** SPEC-OPS-007 §VI.1 assigns to the response, never the
   HTTP status family, and it is **not** an operational or incident classification (SPEC-OPS-003 §VI
   classifies events; SPEC-OPS-006 classifies health).

   | Condition | Meaning | `alert_card` level |
   |---|---|---|
   | Informational | Nothing went wrong; the response is intended (e.g. 418) | `info` |
   | Expected refusal | A rule deliberately refused the request; nothing to recover beyond going elsewhere | `info` |
   | Recoverable restriction | The user can proceed by acting or waiting (sign in, correct input, wait out a limit) | `warning` |
   | Unexpected failure | The application could not complete the request | `danger` |

   Only existing `alert_card` levels are used; the design system gains no level for error pages.
   Informational and expected refusal share `info`: neither asks the user to act or signals a
   fault, and the condition is told apart in words, which §3 requires regardless. A distinct colour
   for refusal would carry no meaning the words do not already carry. (`login-notice`'s guardian
   gray is not reused: it is the operator's voice on the sign-in pages, a different meaning.)

2. **Uncertain outcome** is not a level. When SPEC-OPS-007 §VII reports an Unknown outcome, the page
   keeps its condition's level and adds the outcome notice — a shared component with its own `h2`
   and explicit check-before-retrying guidance. Uncertainty never raises the level by itself.
3. Severity is never conveyed by colour or icon alone; the heading and explanation state it in words.

### IX. Accessibility

1. One `h1` (§V.2); other headings are `h2`, or nested correctly under one; no skipped levels
   (INV-ARC-020 §VI.1–2, §IX.3).
2. Every attribute accessibility depends on is in the server-rendered markup. No script adds,
   repairs or removes accessibility attributes.
3. Icons never carry meaning alone. An interactive icon's accessible name describes its destination.
4. Contrast meets WCAG 2.1 AA in the rendered role theme.
5. Nothing on the page moves, changes or navigates on a timer.
6. Every template has a SOP-TEST-002 render fixture, one state per optional section that changes
   the rendered surface (outcome notice, support reference, sign-in panel, status link present/absent).

### X. Rendering resilience

1. A template depends only on the values its handler passes, `url_for`/`static_url`, and static
   files. It reads no session value, current user, class context, feature setting or domain row,
   and calls no service.
2. It extends no layout and includes no partial that does.
3. With scripts disabled, every section and action works.
4. Rendering performs no mutation (INV-ARC-006 §V, INV-ARC-007 §V). Handler-side obligations are
   SPEC-OPS-007 §XIII.

### XI. Generic error page

`templates/error.html` renders any full-page error without a dedicated template, with the §V
anatomy, a generic icon and content from SPEC-OPS-007 §V.2. A dedicated template exists only where
a status needs content or a component the generic page cannot take as arguments.

### XII. Adding a status page

Prefer the generic page. Where a dedicated template is needed, build it from §V–VII with shared
components and classes only, add its render fixture, and add the status to SPEC-OPS-007 §V.1 in
the same change.

### XIII. Amendment

SOP-DOC-000 §XIII; register through SOP-DOC-001; update INV-ARC-020's incorporation reference in
the same change.

---

## Part E — Draft: `SPEC-OPS-007` HTTP Error Communication (UNRATIFIED)

> Specific wording — heading texts, labels, JSON field names — is a proposal inside the ruled
> direction; the owner may change it at ratification without reopening a ruling.

### I. Purpose

Define what the application communicates when a request cannot proceed normally: what an error
response tells its recipient, what it must never tell them, what is and is not known about the
outcome of what they attempted, what they can safely do next, and how the response is formed at the
protocol level. An error response reduces uncertainty without inventing certainty.

### II. Scope

1. Applies to **every HTTP 4xx or 5xx response the application generates**, whatever produces it: a
   registered error handler, a blueprint error handler, a decorator, or route-local code returning an
   error status (B.9). Route-local and blueprint-local responses are not exempt from §VI–XIII.
2. Full-page HTML error responses are presented per `SPEC-DES-002`. A route-local JSON error or an
   in-page validation message follows §VI–X for content, disclosure and protocol, and keeps its own
   presentation.
3. Includes intentional statuses (418).
4. Does not govern presentation (`SPEC-DES-002`), recording (`SPEC-OPS-003`), redirects, flash
   messages on successful responses, or responses produced in front of the application (proxy,
   Cloudflare, maintenance gate).

### III. Authority Level

Normative (Tier 2), technical contract. No independent authority: it operationalizes DOM-OPS-001's
authority over how the system communicates its status to external actors and binds through
DOM-OPS-001's incorporation. Subordinate to INV-CORE-000, INV-ARC-004, INV-ARC-005, INV-ARC-006,
INV-ARC-007, INV-ARC-020 and DOM-OPS-001. It establishes no domain truth.

### IV. Dependencies

INV-CORE-000, INV-ARC-004, INV-ARC-005, INV-ARC-006, INV-ARC-007, INV-ARC-020, DOM-OPS-001,
SPEC-OPS-003, SPEC-OPS-004, SPEC-OPS-006, SPEC-SEC-001, SPEC-DES-002, REF-TERM-002 (informative).

### V. Statuses with dedicated pages

1. 400, 401, 403, 404, 418, 429, 500, 503 have dedicated pages and one application-level handler each.
2. Every other full-page error uses the generic page with its **original status code, reason phrase
   and status-specific headers** preserved.

### VI. What every error response communicates

1. Every response is assigned one **condition** — informational, expected refusal, recoverable
   restriction, unexpected failure — from the facts of the refusal or failure (what refused it, or
   that execution failed), not from the status family. The condition selects wording and, for pages,
   SPEC-DES-002 §VIII severity.
2. Where applicable, in plain language and REF-TERM-002 vocabulary (accessibility governs conflicts):
   1. **What happened** — the established fact.
   2. **What it means for the user.**
   3. **What is known about the outcome** of the attempted action (§VII).
   4. **What the user can safely do next** (§IX).
   5. **Whether further help is appropriate and how to get it**, with the support reference (§VII.4).
3. State established facts and assign no unsupported blame. A status family describes response
   semantics, not responsibility: a 400 may come from defective application JavaScript, a 404 from a
   link the application itself rendered.
4. Fixed headings: the explanation's heading names the condition in words; guidance is **"What you
   can do"**; the outcome notice is **"Did it go through?"**; help is **"Getting help"**.
5. One vocabulary: "sign in", "teacher", "student", REF-TERM-002 terms, no developer terms.

### VII. Outcome of the attempted action

An unsuccessful HTTP response does not establish an unsuccessful domain operation, and no HTTP status
establishes an outcome. A 400, 401, 403, 404 or 429 does not prove that a mutation was rejected before
it ran.

1. The outcome is derived **only from execution facts and the owning execution contract**:

   | Outcome | Established only by | Communicate |
   |---|---|---|
   | **Not applicable** | The request attempted no state-changing operation: its method is safe (`GET`, `HEAD`, `OPTIONS`; INV-ARC-007), or the execution layer records that no state-changing command was entered | No outcome notice; nothing about state |
   | **Rejected before execution** | A non-safe request whose failure the execution layer records as raised before any state-changing command was entered (e.g. a refusal raised by request preprocessing before the view ran) | The condition and its correction; that the action was not carried out |
   | **Confirmed unsuccessful** | The owning execution contract reports the command rolled back | That it did not go through; retry guidance only where §IX allows |
   | **Confirmed successful** | The owning execution contract reports the command committed | That it went through; never an instruction to repeat it |
   | **Unknown** | Any other case | "This may or may not have gone through." Check the relevant page (balance, history, the item) before trying again |

2. Today the execution layer records neither "no command entered" nor a per-request commit outcome
   (`FEATContext` keeps no record after it exits, Part 2.3). Until such a fact exists under its own
   contract, **every failed non-safe request is Unknown**. This document does not create that fact; a
   FEAT-layer contract would.
3. Handlers and templates never query domain state to reconstruct an outcome, and never claim that an
   account, balance, transaction, attendance record or class is unchanged unless the execution
   contract supports it.
4. **Support reference.** Where help is appropriate, the response shows the request's identifier,
   generated by the application at the entry point (DOM-OPS-001 INV-OPS-004) as an opaque random
   value with no derivation from request data. A caller-supplied identifier (e.g. `X-Request-Id`) is
   never adopted, displayed, echoed or persisted as the request's identity. No separate error
   identity is created.

### VIII. What an error response must not convey

In HTML, JSON, plain text and the log records they cause (SPEC-OPS-003 §VIII.A):

1. Raw exception messages or descriptions (`str(e)`, `error.description`), stack traces, exception
   class names, SQL or database internals, filesystem paths, credentials, tokens, configuration
   values or secrets, PII (INV-ARC-005).
2. **Request URLs or paths.** A path is not safe because its query string was removed: segments can
   hold identifiers, personal data or arbitrary user input. No error response displays the requested
   URL or path.
3. **Protected resource existence.** One rule on every surface:
   1. A resource's existence is disclosed only where the governing authority establishes that it is
      visible to the actor. No rule relies on what the actor is assumed to already know.
      Authentication, lookup, claim and recovery follow SPEC-SEC-001 §V.
   2. A failed lookup of a protected resource and an unauthorized request for an existing protected
      resource produce the same response: status, body, headers, and every other characteristic
      the application controls.
   3. **403** is used only where the refusal itself may lawfully be disclosed without revealing
      protected information — e.g. an actor's role may not use a route whose existence is public
      (a student requesting a teacher page). A refusal that depends on a protected resource uses
      the indistinguishable response in 2.
4. Internal identifiers without an established disclosure purpose (DOM-OPS-001 §7). The support
   reference (§VII.4) is the one established purpose.
5. Explanations come from an approved set per condition, owned by the code that produces the
   response. A `description` passed to `abort()` and exception text are never shown.

### IX. Recovery actions

1. **Safe destination, always.** Every page offers a link that depends neither on browser history nor
   on re-running the failed request, chosen by the handler (never the template) from the `role` key
   of the session cookie the session interface has already decoded:
   1. `student`, `admin` or `sysadmin` → that role's dashboard, labelled "Go to your dashboard";
   2. no role → the sign-in choices (§IX.5).

   The role is read, not validated: no database query, no nonce or expiry check. This is safe because
   the link discloses nothing and authorizes nothing; the destination enforces its own authentication
   and, for an expired or revoked session, redirects to sign-in. Every destination is a GET with no
   side effect (INV-ARC-007).
2. **No history navigation.** Pages offer no `history.back()` action: the application cannot establish
   what the previous history entry is, or that returning to it cannot resubmit a form, whatever the
   failed request's method.
3. **Try again** appears only when the failed request was safe (Not applicable outcome), and it
   re-issues that same safe request. A failed non-safe request is never offered a GET of its URL as a
   retry. No page refreshes itself.
4. **Status page** appears only on unexpected-failure conditions, using the instance's configured URL
   (§XI.6). Absent configuration, absent link. A refusal or restriction never links to it.
5. **Sign in** (401 pages and the sign-in redirect): one choice per role ("Student sign in",
   "Teacher sign in").
6. Order: safe destination, then the condition-specific action (Sign in / Try again), then Status page.

### X. Response format and protocol

1. **Resolution.** One resolver for every error response:
   1. Path under `/api/` → JSON (those resources have no HTML representation).
   2. Otherwise JSON only when the `Accept` header names `application/json` explicitly with q > 0 and
      with a q strictly greater than any explicitly named `text/html`. Wildcards (`*/*`,
      `application/*`) never count as a JSON preference. Absent, wildcard-only, tied or unparsable
      `Accept` → HTML.
2. **JSON shape.** `{"status": "error", "error": <condition code>, "message": <plain-language
   explanation>}`, plus `"reference"` when §VII.4 applies. Route-specific shapes with consumers
   (B.6, B.9) move to it through the migration in Part J, consumer first.
3. Presentation never changes the status. The resolver never turns an error into a 2xx or 3xx;
   418 is sent as 418.
4. Status-specific headers are preserved or supplied: `Allow` on 405 (from the exception);
   `Retry-After` on 429 whenever the limiter knows the reset time, HTML and JSON alike.
5. **Authentication failures.**
   1. Browser navigation to a protected page without a valid session is redirected to the role's
      sign-in page (as today), including from `require_seat_context()`.
   2. A programmatic request (an `/api/` path, or a background request as `_is_background_request`
      defines it) without a valid session is answered **401** in JSON. It is never redirected to an
      HTML sign-in page, so a client's automatic redirect-following cannot turn the failure into an
      apparent success.
   3. **Bounded protocol deviation.** CTH authenticates with a session cookie, and no registered HTTP
      authentication scheme describes cookie sessions, so these 401s carry no `WWW-Authenticate`
      challenge. This departs from RFC 9110 §15.5.2 ("MUST send a WWW-Authenticate header field").
      The deviation is bounded to: 401 responses to programmatic requests whose session is missing,
      expired or invalid, and 401 responses to failed credential submissions on the sign-in,
      passkey and TOTP endpoints. No document, test or response claims RFC 9110 conformance for
      them. No authentication scheme is invented to supply a header. Any other 401 is a defect.
   4. A refusal of scope (a valid session asking for a class it may not use) is not an
      authentication failure and is never answered 401 (§VIII.3; I7).
6. **Fallback.** If a page cannot render, the response is fixed plain text with the same status and
   headers and no exception detail.
7. A handler fixes status and headers first, then chooses the representation.

### XI. Operational accuracy

A response never:

1. says an error was recorded, logged or reported unless that happened in this request;
2. gives a recovery estimate the system cannot support;
3. says the service, class or account is unavailable when one operation or capability was refused;
4. implies the hosted CTH instance's status represents another instance;
5. presents an expected denial (SPEC-OPS-003 §VI) as an infrastructure failure.

6. **Status-page destination.** The link target is the operator-configured `STATUS_PAGE_URL` of this
   instance. The configuration mechanism is the trust boundary; no request-controlled input
   (header, query, cookie, form field) can supply or alter it. Validation is structural, not a
   provider allowlist, and each rule answers a demonstrated risk of placing an operator value in an
   `href` that every viewer's browser follows:

   | Rule | Risk it answers |
   |---|---|
   | An absolute URL that parses, with a host | A relative or malformed value would send the viewer somewhere unintended within the app |
   | Scheme `https` (owner ruling I-2) | `javascript:`, `data:`, `vbscript:` and `file:` would execute or read locally in the viewer's browser; plain `http` is excluded by I-2 |
   | No userinfo (`user:pass@`) | Credentials in the value would be shown to every viewer in page source |
   | No whitespace or control characters | Browsers strip some of them while parsing, so the URL followed could differ from the one validated |

   **Not restricted:** IP literals, `localhost`, private-network and internal hostnames, ports,
   paths, queries and fragments. The browser of the person viewing the page follows the link, and
   the server never fetches it, so the server-side request forgery reasoning that justifies
   blocking private addresses does not apply; an independently hosted instance on a private
   network legitimately points at a status page on that network. An invalid or absent value yields
   no link and one configuration warning at startup, never a fallback URL.

An intentional 418 degrades no health check, monitor or alert (SPEC-OPS-006 1.8); ordinary access
logging still applies.

### XII. Diagnostics

1. Every status in §V.1 has a sysadmin probe at `/sysadmin/test-errors/<code>` (SPEC-OPS-004). The 429
   probe raises `TooManyRequests` directly and is exempt from the limiter, so it consumes no
   rate-limit budget.
2. Each producer of an error response has tests for the boundaries in Part K of the decision
   package (carried into the ratified text as its validation section).

### XIII. Rendering resilience and transaction ownership

1. An error response does not require the infrastructure whose failure may have caused it. Error
   rendering performs no database query, class-context resolution, session restoration (validating
   the cookie against stored session state), domain query or external call, and no global context
   processor runs a query for it. Reading a key from the already-decoded session cookie (§IX.1) is
   not restoration.
2. Already-established request facts (the generated request id, status, method, condition, outcome)
   are used only where lawful and necessary.
3. Error handlers own no transaction. They commit nothing, roll back nothing they did not open, and
   establish no business outcome. FEAT transactions commit or roll back under the FEAT layer
   (INV-ARC-006); request-level cleanup follows the application-context teardown. Rendering mutates
   nothing (INV-ARC-006 §V, INV-ARC-007 §V).
4. No authority-sensitive operation is added to render an error.

### XIV. Amendment

SOP-DOC-000 §XIII; register through SOP-DOC-001; update DOM-OPS-001's incorporation reference in
the same change.

---

## Part F — Proposed amendment: `SPEC-OPS-003` v1.3 (recording)

§II's scope gains "and the application log record of an HTTP error response". New section after
§VIII:

> ### VIII.A Error-response log records
>
> 1. **Storage.** An HTTP error response is recorded in the application log only. No table stores
>    HTTP error responses. A future persistence requirement must first come from a governing contract.
> 2. **One record per error response**, written where the response is produced, carrying only:
>    request id; method; **route pattern** (`request.url_rule.rule`, e.g. `/admin/students/<int:seat_id>`)
>    or, when no route matched, the literal `<unmatched>` plus the registered blueprint prefix the path
>    falls under (e.g. `/admin`) or `/` if none; status; condition (SPEC-OPS-007 §VI.1); outcome
>    (SPEC-OPS-007 §VII); and for an unexpected failure the diagnostic record in 4. Class and actor
>    appear only as DOM-OPS-001 §7 public aliases. No raw path, query string, fragment, header value, body value or
>    form field is recorded.
> 3. **Level follows the event, not the status** (§VI): intentional informational responses (418) and
>    `EXPECTED_DENIAL` — `INFO`, or none where access logging already records the request;
>    `SYSTEM_FAILURE` — `ERROR`.
> 4. **Privacy-safe diagnostics** for `SYSTEM_FAILURE`, in place of `logger.exception` tracebacks and
>    exception text:
>    - the exception's fully qualified class name, and for chained exceptions each cause's class name;
>    - the stack as frames of `module:function:line` — no source text, no local variables, no
>      argument values;
>    - for database errors, the SQLSTATE / driver error code and the constraint or table name the
>      driver reports — never the statement or its parameters (engines run with `hide_parameters=True`);
>    - a keyed fingerprint (HMAC, operations key) of the exception class plus frame list, so repeats
>      group without storing the message;
>    - never exception message text, `repr` of arguments, request data, environment values or paths
>      outside the application package.
>    Fuller evidence for one incident is gathered by reproducing it under the operator's control, not
>    by widening the log record.
> 5. **Request identifier.** Generated by the application at the entry point as a random opaque token
>    (`uuid4().hex`, 32 characters, within `audit_events.request_id`'s `String(64)`). Inbound
>    `X-Request-Id` / `X-Correlation-Id` are ignored: not adopted, logged, echoed or persisted.
> 6. Recording never raises, never changes the response, and writes nothing to the database.
> 7. **Format safety.** Every interpolated value is escaped for the configured log format (including
>    `LOG_FORMAT=json`), so no value can add or alter fields.

## Part G — Incorporation and related amendments (approved in principle; for ratification)

1. **INV-ARC-020**: add `SPEC-DES-002` to §IV; add to §VII: "HTTP error pages follow `SPEC-DES-002`,
   which this invariant incorporates as their presentation contract."
2. **DOM-OPS-001**: add to §1 *Operations OWNS*: "**HTTP Error Communication**: what the application
   tells a recipient when a request cannot proceed, governed by `SPEC-OPS-007`"; add `SPEC-OPS-007`
   and `SPEC-OPS-003` to §0 Dependencies.
3. **SPEC-OPS-003** v1.3: Part F.
4. **SPEC-DES-001**: §IX's error-page sentence ends "…; their anatomy and components are governed by
   `SPEC-DES-002`". No level or token is added.
5. **SPEC-OPS-004**: probe list includes 418 and 429; probes never call the limiter.
6. **SOP-DOC-001**: register `SPEC-DES-002`, `SPEC-OPS-007` and every amended version.
7. **SOP-DEP-002** §VIII step 10 (C1): "the journal has no `ERROR`, `CRITICAL`, `Traceback` or
   `WORKER TIMEOUT` lines since the restart (application failures are `ERROR` records under
   SPEC-OPS-003 §VIII.A; `Traceback` now matches only gunicorn's own worker failures)". Ratified with
   Part F; takes effect when Part F ships.

No amendment to INV-OPS-004, INV-ARC-001 or DOM-OPS-002 is needed for the request identifier
(Part 2.2).

## Part H — Remaining conflicts with governing documentation

No owner decision remains open. H-1 is ruled (Part 1, round 4; E §X.5). Checking the drafts against
every ratified document they touch found the conflicts below. Each is resolved by an amendment in
Part G, ratified in the same change as the drafts; none needs a new ruling.

| # | Conflict | Governing text | Resolution |
|---|---|---|---|
| **C1** | Part F replaces `logger.exception` tracebacks with privacy-safe diagnostics, so the application will stop writing `Traceback` lines. The production release check greps the journal for `Traceback` to detect failures since the restart; after Part F it would stop seeing application failures and report a clean release falsely | SOP-DEP-002 §VIII step 10 ("the journal has no `ERROR`, `CRITICAL`, `Traceback` or `WORKER TIMEOUT` lines") | G.7: keep `ERROR` and `CRITICAL` (Part F logs every `SYSTEM_FAILURE` at `ERROR`, so the check still sees every application failure) and keep `Traceback` for gunicorn's own worker tracebacks, with a note that application failures appear as `ERROR` records. Ships with Part F, not before |
| **C2** | SPEC-OPS-003 §II limits its scope to telemetry, so the error-response log record (Part F) has no governing home today | SPEC-OPS-003 §II | G.3: scope widened in v1.3 |
| **C3** | The HTTP error communication responsibility is not named in DOM-OPS-001 §1, so SPEC-OPS-007 would have no incorporating clause | DOM-OPS-001 §1 | G.2 |
| **C4** | The 401 responses deviate from RFC 9110 §15.5.2. No CTH governing document requires RFC 9110 conformance, so this is not a conflict with governing documentation; it is recorded because the owner directed that it be named and bounded, and E §X.5.3 does so | RFC 9110 §15.5.2 (external) | None needed beyond E §X.5.3 |

Checked and **not** in conflict:

- INV-OPS-004 (request id generated at the entry point), INV-ARC-001 §V, INV-ARC-000 §X, DOM-OPS-002
  §2.1: V2's remediation conforms to them as written (Part 2.2).
- DOM-SUP-001 correlation pack: it copies `actor_request_trace` rows and reads `request_id` as an
  opaque value; the V2 remediation changes the value's source, not its shape or column.
- SPEC-OPS-006 (public request monitoring): it measures statuses from outside; 401/403 remain
  `ACCESS_DENIED` / `UNEXPECTED_DENIAL` where it already classifies them, and no status changes
  under H-1.
- SPEC-OPS-003 §VIII's metrics prohibitions (no request ids, URLs with parameters or exception text
  in metric labels) are untouched; Part F concerns log records.
- SPEC-DES-001 §VI: no level or token is added (D §VIII).
- INV-ARC-007 / INV-ARC-006: the safe destination reads the decoded cookie and writes nothing
  (E §IX.1, §XIII.1).
- DOM-OPS-001 Status Page Publication State: it governs the hosted status page's content, not which
  URL an instance links to; E §XI.6 governs only the link.

## Part I — Affected surfaces

| Surface | Items |
|---|---|
| Templates | `error_400/401/403/404/429/500/503.html`, `error_418.html` (PR #1839), new `error.html`, new macros in `templates/macros/` |
| CSS | `static/css/style.css` Error Pages section; `tokens.css` only if a token is added |
| Handlers | `wsgi.py` (every error handler, `log_error_to_db`, `get_last_log_lines`, 404 cache, `get_validated_status_page_url`); `app/__init__.py` (`register_error_handlers`, context processors, `_get_request_id`, `attach_request_id_header`, log formats); `app/auth.py` decorators; `app/routes/api.py`, `student.py`, `admin.py`, `system_admin.py`; ≈237 route-local error returns in 9 files (B.9) |
| Request identity | `app/__init__.py`; `app/services/tlcp.py` (`persist_request_trace`); `actor_request_trace.request_id`; support correlation pack (DOM-SUP-001) |
| API consumers | B.6, B.10; `static/js/attendance.js`; `templates/admin_students.html`; sign-in / passkey / TOTP scripts; onboarding poller; 22 `fetch(` callers |
| Probes | `app/routes/system_admin.py` `/sysadmin/test-errors/*` (+418, +429) |
| Observability | application log format (Part F); production Grafana dashboards, saved queries, alerts (U4); `status_service/log_sampler.py` (reads `nginx_access`, unaffected by Part F) |
| Accessibility fixtures | `tests/a11y_fixtures/public.py` |
| Tests | `tests/test_error_handlers.py`; `tests/test_404_dedupe_cache.py` (deleted with the cache); new resolver, disclosure, outcome, resilience, logging tests |
| Docs | Part G list; `docs/self-hosting/handbook-overview.md`, `configuration.md` (status URL); CHANGELOG |

## Part J — Implementation and migration sequence

**Step 0 — now, under existing authority, independent of ratification.** Confirmed invariant
violations are not deferred for the specification. 0a and 0b are done on branch
`fix/error-log-url-and-request-id` (Part 3.5); 0c's database part is done, its log part awaits the
owner's count-only commands:

- **0a (V1).** Error handlers stop logging `request.url`; log the route pattern or `<unmatched>` +
  blueprint prefix. Authority: INV-ARC-005 §V, DOM-OPS-001 §7. Small PR with a mutation test feeding
  `?student=<name>` and `?class_id=<id>`.
- **0b (V2).** Generate the request identifier at the entry point; ignore inbound `X-Request-Id` /
  `X-Correlation-Id` for identity, echo and persistence. Authority: DOM-OPS-001 INV-OPS-004.
  Check the support correlation pack and any operator tooling that matches on caller-sent ids first.
- **0c (U1–U3).** Read-only checks of production nginx, `LOG_FORMAT` and retained logs, to size any
  exposure already written; if found, handle under SOP-SEC-001 §V.4 and the retention rules.

Then, after ratification of Parts D–G:

1. **Ratify and register** (Part G). PR #1839 merges first or rebases onto the result; 418 is brought
   to the contract in step 6.
2. **Remove dead machinery** (I1, I2): `log_error_to_db`, the 404 cache and its test, the
   `error_events` insert, `get_last_log_lines` on the error path, `copyLogs()`, the `error_id` block.
3. **Trace consumers** (U5, U6): every `fetch(` caller, `accept_mimetypes` branch and route-local error
   return (B.9) mapped to the statuses and fields it produces or reads. Output: a compatibility table.
4. **Inventory Grafana** (U4): dashboards, saved queries and alerts that read application log lines,
   read-only. Nothing in Part F's format ships until each reader has a replacement query.
5. **Handler layer**: one error module — status and headers first, the resolver, condition and outcome,
   JSON shape with compatibility paths for traced consumers, plain-text fallback, Part F log record,
   rendering without context-processor queries, no transaction handling. Fixes I5–I8, I12.
6. **Presentation layer**: shared macros and CSS, each template rebuilt, `error.html`, the
   404→418 link, the safe destination (E §IX.1). Fixes V3, I3, I4, I9–I11, I13.
7. **Disclosure rule** across surfaces (N9): each `abort(403)`, each blueprint handler, `login_required`'s
   scope-to-401 mapping (I7), and route-local 403/404 returns.
8. **Consumer migration**: route-local JSON errors to the canonical shape and E §X.5 (401 kept; scope
   refusals stop answering 401),
   consumer first, producer second, one PR per consumer group; compatibility paths removed when the
   step 3 table is empty.
9. **Probes** (418, 429) and **docs** (self-hosting status URL, CHANGELOG, release record).

Step 0 PRs and steps 2–4 can run in parallel; each step is its own PR with its own validation.

## Part K — Validation (INV-ARC-017)

Proportional to each step, scoped first, exact commands recorded, no partial run reported as whole.
Nothing is assigned to the operator as redundant or adversarial production testing; production checks
are the release SOP's browser checks (SOP-DEP-001B) for the changed pages and the read-only step 0c.

| Boundary | Proved by |
|---|---|
| Protocol | per status: code and reason; `Allow` on 405; `Retry-After` on 429 (HTML and JSON); 401 only for programmatic requests without a valid session and failed credential submissions (E §X.5), never for browser navigation or scope refusals; no claim of RFC 9110 conformance for them in tests or docs; 418 is 418; no error becomes 2xx/3xx |
| Response format | resolver matrix: `/api/` × {none, `*/*`, `application/json`, `text/html`, `application/json;q=0.5, text/html`, tie, malformed}; JSON shape; compatibility paths; plain-text fallback when the template raises |
| Outcome | safe method → Not applicable, no notice; failed non-safe request → Unknown notice; no status-to-outcome path (a 403/404/429 on a POST is still Unknown) |
| Recovery | safe destination on every page; no `history.back`; Try again only for safe requests and re-issues the same safe request; no auto-refresh |
| Disclosure | mutation tests: `abort(400, description="SECRET")`, an exception carrying `SECRET`, path and query containing `SECRET`, a caller `X-Request-Id: SECRET` — absent from HTML, JSON, fallback, response headers and log records; protected-resource missing vs forbidden responses byte-identical apart from the request id |
| Request identity | generated id ignores inbound headers; format `[0-9a-f]{32}`; persisted trace and logs carry the generated id |
| Accuracy | no "logged" text; capability-scoped 503 wording; status link only on unexpected-failure pages, only with a valid configured URL; URL validator accepts `https` URLs with public hostnames, internal hostnames, IP literals, `localhost`, ports and fragments, and rejects non-`https` schemes (`http`, `javascript`, `data`), userinfo, relative values, whitespace and control characters |
| Resilience | every error page renders, signed in and signed out, with the database unreachable and with an aborted transaction, issuing zero SQL statements (statement-count guard) |
| Recording | one record per error; level by event; route pattern / `<unmatched>`; diagnostic record without message text or parameters; JSON log format stays valid with hostile values |
| Accessibility | SOP-TEST-002 axe gate on every error template and state (outcome notice, status link on/off, sign-in panel, safe destination signed in and signed out, 404→418 link); heading order; the 404 link reachable by keyboard with its accessible name |
| Structural guards | templates carry no `<style>`, no accessibility-repair script, no `history.back`; each guard ships with its mutation proof (SOP-TEST-003 §IX.A) |
| Adjacent regressions | `tests/test_error_handlers.py`; student/API context-error tests; status sampler tests; `attendance.js` 401 path; admin roster error path; sign-in, passkey and TOTP failure paths; TLCP trace tests |

## Not checked

- Rendered axe results for the current pages (not rerun for this package).
- Production nginx configuration, `LOG_FORMAT`, the application journal and nginx access logs
  (U1–U3); the database stores are checked (Part 3.5). Grafana inventory (U4).
- Each `fetch(` caller and route-local error return individually (Part J step 3).
- Error responses from Cloudflare and the Access gate (U7).
