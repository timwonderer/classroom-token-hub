# Hugo + Hextra developer-doc site (local proof)

Hugo + Hextra was selected on October 24, 2026, as the migration candidate for the
Docusaurus developer site; it replaces Docusaurus only after the gates under "Before
production" pass. This directory builds that site from `docs/` on its own. It does not
switch the production build: it changes no application code, canonical document, user
guide, Pages workflow or deployment configuration.

[The comparison](COMPARISON.md) and [evidence/](evidence/) record why Hugo was chosen
over the Zensical prototype. They are history: the Zensical harness that produced them
has been removed, and the proof no longer depends on Zensical code or on the ab56
worktree.

## Authority and scope

- `INV-CORE-000` §III.7 and `INV-ARC-020`: accessible rendered content and controls.
- `SPEC-DES-001` §§IX/XIII: canonical text wordmark, fonts, tokens and brand surfaces.
- `SOP-DOC-000` §X: publication boundaries; §XI: link integrity.
- No application domain mutation or FEAT contract changes are involved.

## Reproduce on macOS

From the repository root, with Python 3.10+ and these standalone proof dependencies
(not the application's full `requirements.txt`):

```bash
python3 -m venv /tmp/cth-docs-proof-venv
/tmp/cth-docs-proof-venv/bin/pip install PyYAML==6.0.3 Jinja2==3.1.6 pytest==9.1.1 playwright==1.62.0
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/bootstrap.py
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/build.py
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/check.py
/tmp/cth-docs-proof-venv/bin/python -m pytest --noconftest -q docs-generator-proof/test_proof.py
/tmp/cth-docs-proof-venv/bin/python -m playwright install chromium
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/browser_check.py
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/preview.py
```

`check.py` exits nonzero while any rule fails; failures are never suppressed. A
successful Hugo command alone is not a passing gate. Browser checks also fail on
reported accessibility, overflow, interaction or JavaScript errors. On current `main`
the check reports seven source-heading failures (multiple `h1`s or skipped levels) in
canonical documents; they are source defects, not generator defects.

Preview: <http://127.0.0.1:8766/docs/> (loopback only; Ctrl-C stops it). This is not a
deployment.

## What the build does

`bootstrap.py` verifies the three hashes in `tools.lock.json`, extracts Hugo without
installing a system package, and pins Hextra/FlexSearch. It is a macOS bootstrap, not
a Linux GitHub Actions implementation. No Node build or theme CSS compilation is
required; Hugo still ships browser JavaScript.

`build.py` owns the publication policy. Only the allowlisted roots in `GROUPS`, the two
durable `TRACKING` files and the one listed illustration publish; `user-guides`,
`ops`, `archive`, the rest of `TRACKING`, and anything new outside the allowlist stay
private. Engineering notes (`docs-site/blog`) are not authorized for publication and
are not staged. Each document keeps its canonical headings and source-relative links,
gets its GitHub edit link and last-commit date, and the generated catalog and category
pages label every document with its own `h1`.

Brand: fonts and tokens come from `docs-site/src`; `github-pages/style.css` is copied
byte-for-byte; the hero renders the required `templates/macros/docs_hero.html` macro;
the footer is generated from `github-pages/learnmore.html` with relative public links
made absolute and the year filled at build time. Hextra's favicons and web manifest
(its own logo and name) are excluded; the tab icon is the application's
`static/images/icon-192.png`. A focused test rejects stylesheet, footer or branding
drift.

Hugo needs a small document layout and Markdown render hooks to retain source
headings and source-relative links. Native Hextra search considers 200 page candidates
with two sections per page: the default 20 missed a frequently cited contract.
Reassess that limit as the corpus grows. Seventeen lines of UI JavaScript make hidden
mobile navigation inert and wide tables keyboard-scrollable.

`check.py` validates the built artifact: it contains exactly the staged pages, every
internal link, anchor and CSS asset resolves, every page has one `h1` and no heading
skips or duplicate IDs, every search entry points at a published page, every document
is in the search index, and every document carries its canonical edit link.

Logs, the built site and fresh JSON reports live in `.cache/`, which is disposable;
never author or amend contracts there. Screenshots go to
`output/playwright/docs-generator-proof/`. No current vulnerability audit or human
assistive-technology review was performed.

## Before production

Add the Linux/CI build path and a dependency-maintenance policy, remove the
`noindex` robots tag in `layouts/_partials/custom/head-end.html`, add this site's
stylesheet to the `scripts/lint_design_tokens.py` surfaces (SPEC-DES-001 §XIV) in place
of Docusaurus, compare against a fresh Docusaurus artifact for URL compatibility, and
complete broader rendered and assistive-technology review.
