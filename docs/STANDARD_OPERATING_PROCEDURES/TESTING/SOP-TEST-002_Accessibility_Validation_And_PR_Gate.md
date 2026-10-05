# SOP-TEST-002: Accessibility Validation and PR Gate

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-TEST-002     | 1.1     | 2026-10-05     | SOP-TEST-002 v1.0 | Standard Operating Procedure |

## I. Purpose

This SOP defines how accessibility validation is executed, remediated, and reported for template and template-supporting UI changes.

## II. Dependencies

- `docs/INVARIANT/ARCHITECTURE/INV-ARC-017_GENERAL_TESTING_INVARIANTS.md`
- `docs/INVARIANT/ARCHITECTURE/INV-ARC-020_ACCESSIBILITY_REQUIREMENTS_AND_TEMPLATE_CONTRACT.md`
- `docs/STANDARD_OPERATING_PROCEDURES/TESTING/SOP-TEST-001_Validation_Execution_And_Reporting.md`

## III. Scope

This SOP applies whenever `INV-ARC-020` says a change is in scope for accessibility validation, including:

- route templates
- shared layouts, shells, and partials
- template-supporting CSS
- template-driven JavaScript interactions
- PRs that claim accessibility improvement, cleanup, or WCAG alignment

## IV. Required Validation Commands

For an in-scope template or UI change, run:

```bash
pytest -q tests/test_accessibility.py
AXE_REQUIRE_BROWSER=1 pytest -q tests/test_axe_app_pages.py tests/test_axe_fixture_pages.py tests/test_axe_compliance.py
```

`tests/test_accessibility.py` is a static check that skips every template extending a layout; it cannot
judge contrast, focus or ARIA semantics. The axe-core run is the one that audits rendered pages. With
`AXE_REQUIRE_BROWSER=1` a missing browser is a failure, not a skip.

The Accessibility Gate runs both on every pull request that changes a template, template CSS or
template-driven JavaScript, and fails the PR when a changed template has no accessibility render path
(§X). Mark the check required in branch protection so it blocks merging.

If a command is blocked, the PR must say so explicitly and explain why.

## V. Remediation Rules

When accessibility findings are discovered:

1. Fix the user-facing issue, not just the test symptom.
2. Prefer semantic HTML, valid labeling, and correct state announcement over ARIA-only patches.
3. Treat contrast, focus visibility, keyboard reachability, and name/role/value integrity as release-facing defects for in-scope surfaces.
4. If a finding is intentionally deferred, document it as remaining risk in the PR report.
5. If the change alters a shared shell, partial, or reusable styling primitive, validate the highest-blast-radius surfaces affected by that shared change.

## VI. Required PR Report Fields

Every in-scope PR must report:

1. Accessibility scope
2. Exact commands run
3. Result of each command
4. Accessibility issues found
5. Accessibility fixes applied
6. Remaining known accessibility issues, if any
7. Confirmation that `CHANGELOG.md` was updated with accessibility issues/fixes

## VII. Gate Condition

A PR that changes templates, shared layouts/components, template-supporting CSS, or template-driven interactive JavaScript is not merge-ready unless it contains the accessibility validation report required by this SOP.

Permitted outcomes:

- `pass`
- `pass with follow-up risk`
- `blocked`
- `not applicable`

`not applicable` is allowed only when the PR does not touch any surface covered by `INV-ARC-020`.

## VIII. Gate Failures

The gate fails when any of the following are true:

1. Missing accessibility report section
2. In-scope PR marked `not applicable`
3. Required commands omitted without explanation
4. Known issues found but not reported
5. PR text implies full accessibility validation when the run was partial
6. Accessibility issues or fixes were material to the PR but omitted from `CHANGELOG.md`

## IX. PR Report Shape

```text
Accessibility Scope: <scope or N/A>
pytest -q tests/test_accessibility.py -> <result>
venv/bin/pytest -q tests/test_axe_compliance.py -> <result>
AXE_REQUIRE_BROWSER=1 pytest -q tests/test_axe_app_pages.py tests/test_axe_fixture_pages.py -> <result>
Issues Found: <summary or None>
Fixes Applied: <summary or None>
Remaining Issues / Risk: <summary or None>
CHANGELOG Updated: Yes/No
```

## X. Accessibility Render Paths

Every changed user-facing template must be covered by at least one canonical accessibility render path,
and the gate fails closed when it is not. "This template has no convenient route" is not a reason for
absent axe coverage. A canonical render path is one of:

1. **A real-route scenario** in `tests/test_axe_app_pages.py` (or `tests/simulated/`): the application
   serves the page to an authenticated or public browser session and axe audits it.
2. **A registered fixture state** in `tests/a11y_fixtures/`: the template is rendered from a
   deterministic presentation fixture and axe audits the result.

A template reached only through `extends`, `include` or `import` is covered when a rendered template
reaches it. A template that already has a real-route scenario needs no duplicate fixture.

### X.1 What fixture coverage proves

For a registered state it proves the template renders, from valid presentation input, through the real
Jinja environment, inheritance, includes, context processors, response headers, project CSS and
template-driven JavaScript, to a DOM that passes axe-core (WCAG 2 A/AA) in that state.

### X.2 What it does not prove

- That the production route assembles that view model, or reaches that state. A fixture is the final
  presentation contract (`INV-ARC-022`: templates are pure consumers of supplied presentation data).
- Authentication, authorization, navigation, or anything produced by running the application.
- Behaviour of scripts that depend on server responses beyond what the page does on load.

These remain the job of the real-route sweep, which stays in place and is preferred wherever a page is
reachable with a freshly provisioned classroom. A fixture state supplements it, typically for error pages,
populated and error states, multi-step flows and pages that need seeded domain rows.

### X.3 Registering a template and state

Add `register(template, state, context, path=..., actor=..., query=..., interact=...)` to the matching
module under `tests/a11y_fixtures/` (`public`, `admin`, `student`, `sysadmin`).

- `context` returns the presentation input the route passes: prefer the real view-model builders
  (`app.services.identity.builders`, the layout helpers in `tests/a11y_fixtures/_layout.py`) and the
  real forms. If no formal view model exists, build the smallest test-only object that matches what the
  template reads. Do not move production business logic into a fixture.
- Fixtures are fixed, fictional, free of PII, deterministic and free of persistence. Rendering runs under
  a guard that fails on any SQL statement.
- `actor` binds a fixed stand-in `g.canonical_context` for layouts that read it ("teacher"/"student").
  It is display plumbing; nothing in a fixture authorizes anything.
- `query` and `interact` open a state that is chosen client-side (`?tab=`) or hidden until a user acts
  (click an inactive Bootstrap tab, because axe cannot see a hidden pane).

### X.4 When more than one state is required

Model a state only when the presentation contract supports it and it materially changes the accessibility
surface: empty versus populated, an error message or field errors, disabled or locked controls, an
expanded versus collapsed region, each hidden tab pane, each status that selects different markup. Do not
create every combination mechanically.

### X.5 Reporting

Failures name the surface:

```text
AXE FAIL
template: templates/error_503.html
state: default
violation: color-contrast ...
```

```text
ACCESSIBILITY COVERAGE FAIL
template: templates/admin/example.html
reason: no route scenario or registered render fixture
```

A fixture that cannot render fails the gate. A PR report must not describe fixture coverage as proof of
route behaviour (`INV-ARC-017`: a partial run is not broader validation).

### X.6 Exemptions

`tests/axe_coverage_exemptions.json` maps a template to a written reason. It may hold an entry only where
fixture rendering is genuinely inappropriate for that template, with the reason stated individually, never
a generic category. Inconvenience of reaching a route, error pages, difficult setup, and the absence of a
route are not reasons. The guard fails an entry that names a template which no longer exists or which is
now covered. The list is empty at v1.1.

## XI. Change Notes

**Version 1.1 (2026-10-05):** Required the axe-core run on every template-affecting pull request. Added
the accessibility render-path requirement, fixture coverage and the coverage guard (§X).
