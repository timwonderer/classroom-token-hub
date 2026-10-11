# CodeQL security-extended backlog: fixes and per-alert classification (2026-10-11)

**Status:** Companion to `docs/ops/audits/INCIDENT_2026-10-11_SEC-SAST-GAP-001.md` §5 follow-up 1
("triage the alert backlog the security-extended switch surfaced"). That follow-up's
morning triage (`codeql-extended-suite-triage-2026-10-11.md`, outside the repo) grouped
all 98 open alerts by query ID and trust boundary and concluded nothing open is reachable
by an unauthenticated public attacker. This document goes one level further: for every
alert, it fixes the finding, or states the specific evidence for why it is a false
positive or not exploitable, or says it is real but deferred. No alert is dismissed
without a reason tied to that alert's own code.

## 1. Fixed

### 1.1 `py/polynomial-redos` — 7 alerts (#273–#279)

`scripts/verify_chain.py:16`, `scripts/validate-migrations.py:44`,
`scripts/analyze_migrations.py:24,26,28`: all five share one shape,
`re.search(r'^name\s*=\s*(.+)$', content, re.MULTILINE)`. The trailing `\s*` and the
capturing `.+` both match ordinary whitespace, so a line with many spaces/tabs after `=`
and no terminating content gives the engine several ways to split the same characters
between the two groups. `validate-migrations.py` runs in CI
(`.github/workflows/check-migrations.yml`) against every migration file a PR adds;
`verify_chain.py` and `analyze_migrations.py` are not wired into any workflow (confirmed:
no `.yml` file references either), so for those two this was local-only exposure, but the
fix is identical and free, so all three were fixed rather than split into "fix" and
"defer". Replaced with `_extract_assignment_value()`: find `name\s*=` (nothing after it to
backtrack against), then slice the rest of the line in plain Python. Verified
byte-identical `analyze_migrations.py`/`verify_chain.py`/`validate-migrations.py` output
against all 173 real migration files before and after.

`scripts/localize_font_links.py:85,87` (#276, #277): not wired into any CI workflow
(one-off/reference script, per its own docstring). `STALE_COMMENT_RE`
(`^[ \t]*<!--[^\n]*(kw1|kw2|...)[^\n]*-->[ \t]*\n`) has the same overlapping-quantifier
shape CodeQL's query is built to catch (`[^\n]*` on both sides of an alternation). Fixed
anyway since it was cheap: replaced with `strip_stale_comments()`, three independent
string checks (`startswith`, `endswith`, `in`) per line, with no adjacent quantifiers at
all. `scripts/localize_font_links.py:87`'s *other* flagged line, `re.sub(r"[ \t]+\n",
"\n", result)`, has no such ambiguity (one quantifier, no overlap) — see §2.5.

### 1.2 `py/log-injection` — 8 alerts (#294, #296–#302), plus one instance CodeQL missed

`wsgi.py`'s 404/403/401/400/429/503 handlers and the "Skipping DB error log" warning, and
`app/__init__.py:630`'s Cloudflare-IP-mismatch warning, interpolated `request.url` or
`request.path` straight into a log line. Added `sanitize_for_log()`
(`app/utils/helpers.py`), which escapes CR, LF and other non-printable characters to
`\xNN`, and applied it at all 8 sites.

Checked directly rather than assumed: Werkzeug's `request.url` keeps percent-encoding, so
`%0D%0A` in the request line reaches it as literal text, not a decoded CR/LF — the 7
`wsgi.py` sites using `.url` are less exposed than the alert's generic "depends on a
user-provided value" wording implies. `request.path`, used in the "Skipping DB error log"
line and read by `app/__init__.py`'s `RequestIdFilter`, *does* decode it to a real CR/LF.
That matters because `RequestIdFilter.filter()` falls back to raw `request.path` for
**every** log record's `endpoint=` field whenever `request.url_rule` is unset (every
unmatched route, i.e. every 404) — not one of the 8 flagged call sites, but a wider
surface CodeQL's taint analysis never followed into (a `logging.Filter` mutating a
`LogRecord` attribute, not a direct `logger.warning(f"...")` call). Fixed the same way.
Full reasoning and reproduction: `tests/test_no_log_injection.py`.

### 1.3 `py/code-injection` — 1 alert (#272)

`scripts/dev-utilities/diagnose_migrations.py:40`: `eval(down_rev_str)` where
`down_rev_str` is parsed from a migration file's `down_revision = (...)` line. Not wired
into any CI workflow (its own docstring: "Run this on your Digital Ocean server"), but the
content still originates from a file under `migrations/versions/`, which a PR shapes.
Replaced with `ast.literal_eval()`, which only ever constructs Python literals and gives
the identical result for every revision tuple this repo actually writes.

### 1.4 `py/command-line-injection` — 4 of 10 alerts (#281, #282, #284, #285)

`scripts/add-github-actions-to-firewall.py` and `scripts/create-github-actions-firewall.py`
(not wired into any CI workflow — run manually when rotating GitHub's published IP ranges
into the DigitalOcean firewall) used `subprocess.run(cmd, shell=True)` with `cmd` an
f-string/multi-line shell snippet built from an operator-supplied CLI arg and, per IP, a
string from GitHub's own `/meta` API response — one of them protected only by a
single-quoted shell literal wrapping embedded JSON. Converted every call in both files to
an argv list with no `shell=True`; an argv list needs no shell quoting and has nothing left
for a shell to reinterpret, regardless of what either value contains. See §2.4 for the
other 6 alerts in this group, which were already argv-list calls and needed no change.

## 2. False positive or already mitigated — left open, not dismissed without further review

Per the coordinator's note on this PR's scope: a dismissal needs evidence tied to that
specific alert. Everything below states that evidence. None of it has actually been
marked "dismissed" in GitHub yet — that requires `security_events`-scoped API access this
session doesn't have from the sandbox (same gap noted in the morning triage); it needs a
follow-up action from a session with that access (or the repository owner, directly in the
Security tab) using this document as the per-alert record.

### 2.1 `py/jinja2/autoescape-false` — 2 alerts (#292, #293)

`scripts/check_axe_template_coverage.py:110` and `tests/test_axe_template_coverage_guard.py:75`
both construct a Jinja2 `Environment(loader=FileSystemLoader(...))` with no `autoescape=`
argument (Jinja2's own default is `False`). Checked the call site, not just the
constructor: both uses are `env.parse(...)` feeding `jinja2.meta.find_referenced_templates()`
— static analysis of `{% extends %}`/`{% include %}` references to build a template
dependency graph. Neither ever calls `.render()` or produces HTML served to a browser, so
`autoescape` has no effect either way: the rule's whole threat model (unescaped output
reaching a page) cannot apply to an `Environment` that is only ever parsed, never rendered.

### 2.2 `py/partial-ssrf` — 1 alert (#291)

`app/routes/system_admin.py:915`, the Grafana dashboard proxy. Re-confirmed the three
independent mitigations already in the route: gated by `@system_admin_required` (the
highest-trust role in the app); `grafana_url`'s host comes only from the `GRAFANA_URL`
environment variable, never from the request, so no request can redirect the proxy to an
arbitrary external host; the request-controlled `path` is stripped of `\r`/`\n` and
rejected unless it starts with one of ten allowlisted prefixes (`d/`, `api/`, `static/`,
...) before it is ever concatenated into `target_url`. "Partial" in the rule name is
accurate — `path` is tainted — but the taint never reaches the host portion of the URL,
which is the part an SSRF needs to control.

### 2.3 `py/sql-injection` — 1 alert (#280)

`infra/db-backup/cth_db_backup.py:185`: `cur.execute(f'SELECT count(*) FROM public."{t}"')`
inside `table_counts()`. `t` is not request- or file-derived; it comes from a prior
`cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ...")` in the
same function — i.e., table names that exist in this database's own catalog today, which
only this project's own migrations create. There is no path by which an external actor
supplies a value that reaches `t`. Also not wired into any CI workflow (an ops-run backup
script).

### 2.4 `py/command-line-injection` — 6 of 10 alerts (#283, #286–#290)

`scripts/ci_evidence_runner.py:129` (CI-reachable, `constitutional-ci.yml`),
`scripts/policy_guardrails.py:74,93` (CI-reachable, `policy-guardrails.yml`, including with
`--git-diff-base`/`--git-diff-head` pointed at PR content), `infra/db-backup/cth_db_backup.py:360`,
`scripts/adversarial/reset_db.py:32`, `scripts/adversarial/snapshot_db.py:33` (none of the
last three wired into any workflow). Checked every one of these five call sites directly:
every single one builds `cmd` as a Python list (e.g. `["pg_dump", "--format=custom", ...]`)
and calls `subprocess.run(cmd, ...)`/`subprocess.Popen(cmd, ...)` with no `shell=True`
anywhere in any of the five files. An argv list goes straight to `execve` with no shell in
between, so there is no shell-metacharacter interpretation for any value in the list to
exploit, regardless of where that value came from — the one property that actually matters
for this rule, and the one the four alerts in §1.4 lacked.

### 2.5 `py/polynomial-redos` — the one line in §1.1's file not changed for safety reasons

`scripts/localize_font_links.py`'s *other* regex at that line, `re.sub(r"[ \t]+\n", "\n",
result)`, has a single quantifier directly followed by a literal with no character-class
overlap between them — no two quantified groups to trade characters between, so no
polynomial blowup is possible regardless of input. Left unchanged (not a code change, just
noted here since it shares a line number with a fixed alert).

### 2.6 `py/stack-trace-exposure` — 1 alert (#171)

`app/routes/admin.py:6369`, inside `void_transaction()`:
`return _void_error(str(e))` where `e` is a caught `TransactionNotReversible`. Checked
every raise site of that exception class (`app/feats/transaction_void_feat.py`): there is
exactly one, and it always raises with a hardcoded, deliberately user-safe string
("This entry is part of a reversal and can't be reversed."). `str(e)` on this specific
exception class can never surface a stack trace, a file path, or any other library/DB
internal — it is a curated message by construction, not a caught low-level error
propagating upward.

### 2.7 `py/path-injection` — 57 alerts, broken into sub-groups below

Classified by file/pattern rather than alert number, since within one file the trust
boundary and the actual sink are identical; "group by query ID and trust boundary" is the
morning triage's own methodology, used here at finer grain (per file, not per whole query).

- **Environment-variable-sourced paths, not request/PR input (false positive):**
  `wsgi.py:149,153` (`LOG_FILE`, default `"app.log"`), `tests/helpers/axe_wcag.py:69,70,71,72,263,264,265,266`
  (`AXE_RENDERED_TEMPLATES_FILE`/`AXE_FIXTURE_TEMPLATES_FILE`),
  `tests/test_username_retention_check_browser.py:248` (`CTH_UI_EVIDENCE_DIR`). All three
  read the path from `os.environ.get(...)`, which only a CI workflow's own `env:` block or
  an operator's shell sets — never a value a request or a PR's diff content can reach.
  (`tests/helpers/axe_wcag.py` and the browser test *are* CI-reachable files, but the
  specific tainted value CodeQL traces, the environment variable, is not.)

- **CI-reachable, but the path only ever names a file git itself already checked out, read
  for linting, never written or deleted (false positive):** `scripts/lint_migrations.py:179,210,214,293,298`.
  `--files`/`--changed-files` are populated by `check-migrations.yml` from
  `git diff --name-only`; a path git reports as changed is, by construction, a path inside
  the checkout — git has no way to report a changed file outside the repository tree, so
  there is no traversal surface here even though the PR's own diff nominally "chooses" the
  filenames.

- **Not wired into any CI workflow, path comes from an operator-supplied CLI argument or a
  JSON file read with that same argument (false positive / local-only):**
  `infra/db-backup/cth_db_backup.py:415,429,540,549,555`, `scripts/firewall_complete.py:41,44`,
  `scripts/pulsetic_firewall.py:51,54`, and every file under `scripts/adversarial/`
  (`build_evidence_bundle.py:28,38,40,52,66,68,68,71,75,104,121,134`,
  `inject_impossible_state.py:30,120`, `render_constitutional_scorecard.py:10,12,16,19,28,78`,
  `reset_db.py:18`, `snapshot_db.py:27,42`, `verify_cross_class_isolation.py:20,25,27,86`,
  `verify_lineage_lawfulness.py:30,99`, `verify_runtime_session_attacks.py:23,29,218`).
  Confirmed by grepping every `.github/workflows/*.yml` for each filename: none appear.
  These are the repository owner's own local tooling, run by hand against their own
  database/environment; the "attacker" CodeQL's generic path-injection source list assumes
  is, in every one of these files, the person already holding full production access.

## 3. Real, but deferred — not fixed in this PR, not dismissed

### 3.1 `actions/unpinned-tag` — 10 alerts (#205–#214)

`actionlint.yml`, `deploy-status.yml` (×2), `docs-links.yml`, `login-notice.yml` (×2),
`release-v2.yml` (×2), `tailscale-ssh-smoke-test.yml` (×2) reference third-party GitHub
Actions by mutable version tag (`actions/checkout@v7`, `tailscale/github-action@v4`,
`webfactory/ssh-agent@v0.10.0`, etc.) rather than an immutable commit SHA. This is a real,
correctly-flagged supply-chain finding — a tag can be retargeted by the action's own
maintainer or a compromised account, silently changing what every consumer runs, which a
SHA pin prevents. Not fixed here: several of these workflows carry production credentials
(`GCP_WORKLOAD_IDENTITY_PROVIDER`, `TS_OAUTH_CLIENT_ID`/`TS_OAUTH_SECRET`, `DO_DEPLOY_KEY`),
so pinning ten actions to the correct current SHA is worth its own narrow, carefully
verified PR rather than bundling it into a security-classification PR — a wrong SHA here
risks breaking a production deploy path, which is a different risk profile than the fixes
above.

## 4. Summary

| Rule | Open | Fixed | False positive / mitigated (documented) | Real, deferred |
|---|---|---|---|---|
| py/path-injection | 57 | 0 | 57 | 0 |
| py/command-line-injection | 10 | 4 | 6 | 0 |
| actions/unpinned-tag | 10 | 0 | 0 | 10 |
| py/log-injection | 8 | 8 (+1 unflagged instance) | 0 | 0 |
| py/polynomial-redos | 7 | 7 | 0 | 0 |
| py/jinja2/autoescape-false | 2 | 0 | 2 | 0 |
| py/partial-ssrf | 1 | 0 | 1 | 0 |
| py/sql-injection | 1 | 0 | 1 | 0 |
| py/code-injection | 1 | 1 | 0 | 0 |
| py/stack-trace-exposure | 1 | 0 | 1 | 0 |
| **Total** | **98** | **20** | **68** | **10** |

Nothing in this document reduces the 98-alert count on GitHub's own Security tab by
itself — that requires either the repository owner or a session with `security_events`
API access to action §2's dismissals using the per-alert reasoning above, and to open the
deferred `actions/unpinned-tag` follow-up (§3.1).

## 5. PR #1541 follow-up alerts (#304–#318)

These 15 PR-head alerts are separate from the 98-alert baseline counted above.

- **Command-line alerts #304–#307:** argv lists removed shell interpretation, but
  that alone does not rule out argument injection. The firewall utilities now reject
  non-UUID firewall IDs and non-positive integer droplet IDs before invoking doctl.
  Both IDs are parsed into typed values and serialized into canonical arguments,
  so raw CLI strings never reach a subprocess.
  GitHub API ranges are parsed and normalized with `ipaddress.ip_network()` before
  becoming rule values; the firewall ID returned by doctl is also UUID-validated.
  Both command helpers return a failure tuple on spawn errors, preserving the
  missing-doctl diagnostic instead of raising `FileNotFoundError`.
- **Log alerts #308–#318:** all four Cloudflare warning arguments and all seven
  wsgi log arguments already call `sanitize_for_log()`. Its character-by-character
  transformation escapes every non-printable character, including CR/LF, C0/C1,
  Unicode line separators and terminal escapes. The original custom loop was not
  recognized by CodeQL; these alerts did not demonstrate a bypass. Explicit CR/LF replacements now expose the same escaping
  boundary to static analysis while preserving the sanitizer's output. Focused tests
  execute the flagged log calls with raw controls and check the formatted output.
  No Security-tab dismissal is performed by this repair.

Validation: `.venv/bin/python -m pytest --noconftest
 tests/test_github_actions_firewall.py tests/test_log_warning_sanitization.py -q`
passed 27 tests. The prior PR head fails 20 firewall regression checks; replacing
log sanitization with a raw string fails all three log checks. These isolated tests
exercise real script functions and extracted logger calls; they do not exercise
Flask request setup, PostgreSQL, or the DigitalOcean API. Python 3.10 syntax and
alert-table totals were also checked.

The first follow-up scan cleared #308–#318 but re-reported command inputs as
#320–#322 and retained #305; UUID regex guards were not recognized as taint
boundaries. It also flagged #319 on the droplet regex. The utilities now parse
UUIDs and integers and serialize them back to canonical arguments; no ID regex
remains. Rescan evidence is required before claiming these new alerts cleared.
