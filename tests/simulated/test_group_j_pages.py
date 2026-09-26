"""WCAG 2.1 A/AA audit of Group J: the teacher-recovery pages
(``admin_recovery_prepare.html``, ``admin_recovery_status.html``), reachable
only mid-flow through the real ``FEAT-IDEN-103`` teacher-recovery chain
(``begin_attempt`` -> ``select_class_recipients``) -- see
app/feats/teacher_recovery_feat.py.

Unlike Group D, this scenario cannot be satisfied by querying the existing
persistent world: recovery proof requires knowing a claimed student's
*plaintext* username ahead of time, and usernames are stored only as an
unsalted HMAC lookup digest (INV-ARC-019 / .claude/rules/security.md) -- there
is no way to recover the plaintext for an already-claimed seat from the
database, ours or production's. So this file provisions its own small,
dedicated classroom through the same production service functions
SPEC-TEST-001's canonical initializer itself calls (create_teacher,
create_class, _provision_roster_seat, create_student_user_for_seat) --
never hand-assembled ORM rows -- and lets it become a real, permanent
addition to the simulated world, consistent with this directory's "create
via FEAT when nothing matches, contribute it back" convention.

This deliberately does NOT reuse tests/helpers/canonical_identities.py's
shared "teacher_alice" fixture identity the way tests/helpers/
classroom_initializer.initialize() would. FEAT-IDEN-103's begin_attempt
requires proving *every* class a teacher owns in one attempt (`sorted(
usernames_by_class) != owned` in app/feats/teacher_recovery_feat.py) --
a teacher who has accumulated more than one class over several runs of a
test like this one can never pass proof again with pairs for only the
newest class. A first pass at this file reused "teacher_alice" and hit
exactly that wall on its second run (compounded by tests/conftest.py
hardcoding PEPPER_KEY, which made a from-pytest run and a standalone
debug script resolve "teacher_alice" to two different identities in the
same database -- worth remembering: never touch identity-hashed simulated
rows from a script that bypasses tests/conftest.py). This file instead
mints a fresh, randomly-suffixed teacher username every run, so it always
owns exactly the one class it just created and proof always succeeds --
at the cost of one more permanent teacher+class in the world per run,
which this directory's own convention already accepts.

Turnstile is bypassed simply because this environment's TURNSTILE_SECRET_KEY
is unset (app/utils/turnstile.py's own documented testing bypass) -- not
because this file does anything special. The FEAT layer has no Turnstile
check at all (that gate lives only in the admin.recover route), so nothing
here needs to touch it either way.

admin_recovery_prepare.html calls back into /recovery/select-class via its
own inline JS immediately on load, then auto-navigates to
/admin/recovery-status once every required class is selected. With only one
required class here that round trip is fast enough to race axe-core's
injection, so the first select-class fetch is deliberately aborted via a
Playwright route so the page's own error branch renders instead and stays
put -- textContent differs, but it is the same DOM structure, so this is a
faithful state to audit. Selection is then actually driven at the FEAT layer
(the way this file's docstring already describes for Group J/L) so the
second page has real status data to render.
"""

from __future__ import annotations

import pathlib

import pytest

from tests.helpers.axe_wcag import (
    assert_no_violations,
    authenticated_page,
    flask_app,
    sync_playwright,
    wcag_live_server,  # noqa: F401 -- fixture, used via pytest injection
)
from tests.helpers.canonical_classroom import _provision_roster_seat
from tests.helpers.canonical_identities import CLASSROOMS

AXE_SOURCE = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "tests" / "assets" / "axe-core.min.js"
).read_text(encoding="utf-8")


def _run_axe(page) -> list:
    page.add_script_tag(content=AXE_SOURCE)
    result = page.evaluate(
        "async () => await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa']}})"
    )
    return list(result["violations"])


def _provision_recovery_classroom(app):
    """A fresh, uniquely-owned classroom whose 4 students' plaintext usernames
    we know, satisfying FEAT-IDEN-103's MIN_CLAIMED_STUDENTS_PER_CLASS=3 and
    its single-class usernames_required_per_class (needs min(6, claimed_count)
    =4 matched pairs). A brand-new teacher every run guarantees that teacher
    owns exactly this one class -- see the module docstring for why reusing
    the shared "teacher_alice" fixture identity breaks proof on a second run.
    Committed so it persists in the simulated world like any other real
    FEAT-created row here.
    """
    import secrets

    from app.extensions import db
    from app.feats.base import FEATContext
    from app.services.classroom_setup import create_class, create_student_user_for_seat, create_teacher
    from app.utils.username_generation import build_username
    from app.utils.join_code import generate_join_code

    roster = CLASSROOMS["chemistry_p1"]["roster"]
    teacher_username = f"teacher.axe-group-j.{secrets.token_hex(6)}"

    with app.app_context():
        join_code = generate_join_code()
        with FEATContext("FEAT-IDEN-001", idempotency_key=f"axe-sweep:group-j:{teacher_username}"):
            teacher_user = create_teacher(teacher_username)
            economy = create_class(
                teacher_user.id, join_code=join_code,
                display_name="Group J Accessibility Fixture", section="Recovery",
                class_timezone="America/Los_Angeles",
            )
            usernames = []
            for row in roster:
                seat = _provision_roster_seat(economy.class_id, row)
                username = build_username(row["chosen_word"], seat.roster_fingerprint or "")
                create_student_user_for_seat(seat, username=username, pin=row["pin"], passphrase=row["passphrase"])
                usernames.append(username)
        db.session.commit()
        return economy.join_code, usernames


@pytest.mark.skipif(sync_playwright is None, reason="Playwright Python package is unavailable")
def test_no_axe_violations_across_group_j_pages(app, wcag_live_server):
    """WCAG 2.1 A/AA audit of admin_recovery_prepare.html (reached by
    actually submitting the real, unauthenticated /admin/recover form as a
    browser would) and admin_recovery_status.html (reached after driving the
    FEAT-IDEN-103 select_class_recipients step for the required class).
    """
    join_code, usernames = _provision_recovery_classroom(app)
    assert len(usernames) == 4

    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - browser installation varies
            pytest.skip(f"Chromium is unavailable: {exc}")

        with browser:
            failures: dict[str, list] = {}

            page = authenticated_page(browser, wcag_live_server, None)

            # Hold admin_recovery_prepare.html on its error branch (same DOM,
            # stable text) instead of racing its own auto-redirect.
            page.route("**/recovery/select-class", lambda route: route.abort())

            page.goto(f"{wcag_live_server}/admin/recover", wait_until="networkidle")
            page.evaluate("() => { addRow(); addRow(); addRow(); }")
            join_inputs = page.locator('input[name="join_code[]"]')
            username_inputs = page.locator('input[name="student_username[]"]')
            for i, username in enumerate(usernames):
                join_inputs.nth(i).fill(join_code)
                username_inputs.nth(i).fill(username)
            with page.expect_navigation():
                page.click('button[type="submit"]')
            page.wait_for_selector("#preparationStatus")
            assert page.url.endswith("/admin/recover"), (
                f"begin_attempt did not accept the freshly-provisioned pairs: "
                f"landed on {page.url!r} instead of admin_recovery_prepare.html"
            )
            assert page.locator("h1", has_text="Preparing account recovery").count() == 1, page.content()
            # A route.abort() surfaces to the page's fetch() as a generic
            # browser network error ("Failed to fetch"), not the friendlier
            # "Recovery could not be prepared" string the page's own code
            # only throws for a non-ok HTTP response -- just wait for the
            # loading text to change at all.
            page.wait_for_function(
                "document.getElementById('preparationStatus').textContent !== "
                "'Selecting recovery helpers in each class…'"
            )

            violations = _run_axe(page)
            if violations:
                failures["/admin/recover (POST -> admin_recovery_prepare.html)"] = violations

            page.unroute("**/recovery/select-class")

            # Extract this attempt's request_id/nonce from the real signed
            # session cookie Playwright is holding, then drive the actual
            # FEAT-IDEN-103 selection step directly -- the JS above already
            # proved the HTTP path calls the same function; this just
            # finishes the chain deterministically instead of racing it.
            cookies = page.context.cookies()
            session_cookie = next(c for c in cookies if c["name"] == "session")
            serializer = flask_app.session_interface.get_signing_serializer(flask_app)
            session_dict = serializer.loads(session_cookie["value"])
            request_id = session_dict["recovery_request_id"]
            attempt_nonce = session_dict["teacher_recovery_attempt_nonce"]

            from app.extensions import db
            from app.feats.teacher_recovery_feat import select_class_recipients
            from app.models import ClassEconomy

            with app.app_context():
                economy = ClassEconomy.query.filter_by(join_code=join_code).one()
                ok = select_class_recipients(
                    request_id=request_id, attempt_nonce=attempt_nonce, class_id=economy.class_id,
                    correlation_id="axe-sweep:group-j", idempotency_key="axe-sweep:group-j:select-class",
                )
                db.session.commit()
            assert ok, "select_class_recipients rejected the same attempt admin_recovery_prepare.html just started"

            page.goto(f"{wcag_live_server}/admin/recovery-status", wait_until="networkidle")
            assert page.url.endswith("/admin/recovery-status"), (
                f"attempt_status() rejected the attempt after selection succeeded: "
                f"redirected to {page.url!r}"
            )
            assert page.locator("#recoveryHeading").count() == 1, page.content()
            assert page.locator(".class-code-form").count() == 1, page.content()

            violations = _run_axe(page)
            if violations:
                failures["/admin/recovery-status"] = violations

            page.context.close()

            assert_no_violations(failures)
