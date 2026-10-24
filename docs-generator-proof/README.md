# Local developer-doc generator proof

Hugo + Hextra was selected on October 24, 2026. This directory preserves the
selected proof and comparison evidence; it does not switch the production build.
It changes no application code, canonical document, user guide, Pages workflow or
deployment configuration. It resides in the `ab56` docs worktree on
`codex/docs-hugo-proof`, alongside the preserved, uncommitted Zensical migration.

The comparison harness still requires the separately maintained Zensical prototype
inputs described below. Those inputs and the corpus corrections are uncommitted
migration work, not bundled into this proof commit. A fresh checkout of this
branch alone cannot reproduce the recorded comparison without those inputs.

Read [the comparison](COMPARISON.md) for corrected-worktree results and remaining migration gates.

## Authority and scope

- `INV-CORE-000` §III.7 and `INV-ARC-020`: accessible rendered content and controls.
- `SPEC-DES-001` §§IX/XIII: canonical text wordmark, fonts, tokens and brand surfaces.
- `SOP-DOC-000` §X: publication boundaries; §XI: link integrity.
- No application domain mutation or FEAT contract changes are involved.

This worktree includes the existing generator-independent SOP amendment and
source-heading corrections. Those changes were preserved byte-for-byte. Before
production migration, reconcile this worktree with current main; this local proof
does not approve or deploy either generator.

## Reproduce on macOS

Use Python 3.13 and an isolated environment. The comparison uses the existing
Zensical prototype's hash-locked dependencies. The original prototype is read-only.
Set its path to your local checkout before running these commands from the repo root:

```bash
PROTOTYPE=/Users/timothychang/.codex/worktrees/ab56/classroom-economy
python3.13 -m venv /tmp/cth-docs-proof-venv
/tmp/cth-docs-proof-venv/bin/pip install --require-hashes \
  -r "$PROTOTYPE/docs-site/requirements.txt" \
  -r "$PROTOTYPE/docs-site/requirements-validation.txt"
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/bootstrap.py
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/build.py --prototype "$PROTOTYPE"
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/compare.py
/tmp/cth-docs-proof-venv/bin/python -m pytest --noconftest -q \
  docs-generator-proof/test_proof.py \
  docs-generator-proof/.cache/zensical/docs-site/tests/test_build.py
/tmp/cth-docs-proof-venv/bin/python -m playwright install chromium
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/browser_check.py
/tmp/cth-docs-proof-venv/bin/python docs-generator-proof/preview.py
```

The artifact comparison intentionally exits nonzero while any contract fails;
failures are never suppressed. The ab56 corpus currently passes this gate. A successful Hugo
command alone is not a passing contract gate. Browser checks also fail on
reported accessibility, overflow, interaction or JavaScript errors.

Preview addresses (loopback only):

- Hugo + Hextra: <http://127.0.0.1:8766/docs/>
- Zensical: <http://127.0.0.1:8767/docs/>

Stop the preview process with Ctrl-C. This is not a deployment.

## Inputs and evidence

`bootstrap.py` verifies the three hashes in `tools.lock.json`, extracts Hugo
without installing a system package, and pins Hextra/FlexSearch. It is deliberately
a macOS proof bootstrap, not a Linux GitHub Actions implementation. No Node build
or theme CSS compilation is required. Hugo still ships browser JavaScript, and
the shared staging runner uses Python, PyYAML and Jinja2.

`build.py` snapshots current `docs/`, runs the original Zensical preparation
code against that snapshot, and gives both generators the same staged corpus.
Only allowlisted documents and illustrations enter the generated artifacts.
Hugo fonts/tokens come from the current docs site. The build copies
`github-pages/style.css` byte-for-byte and renders the required
`templates/macros/docs_hero.html` macro without separate hero sizing rules.
The footer is generated from `github-pages/learnmore.html`, the existing public
footer test's reference, with public relative links made absolute and the year
filled at build time. A focused check rejects stylesheet or footer drift.
Generated content under `.cache/`
is disposable; never author or amend contracts there.

Hugo needs a small document layout and Markdown render hooks to retain source
headings and source-relative links. Native Hextra search is configured to consider
200 page candidates with two sections per page: the default 20 missed a frequently
cited contract. Reassess that limit as the corpus grows. Seventeen lines of UI
JavaScript make hidden mobile navigation inert and wide tables keyboard-scrollable.

Logs, artifacts and fresh JSON reports live in `.cache/`. The `evidence/` directory
preserves this comparison's measured results and corpus hashes. Screenshots live
under `output/playwright/docs-generator-proof/`. No current vulnerability audit or
human assistive-technology review was performed.
