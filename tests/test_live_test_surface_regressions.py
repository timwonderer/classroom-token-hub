"""Regressions for the display, wording and configuration findings of the
2026-09-19 live test.

Companion to ``test_live_test_defect_regressions.py``, which covers the
functional defects. The findings here changed what a surface *said* rather than
what the system did — but four of them said something false, and on a financial
or operational surface that is a defect rather than a polish item.

Findings covered:

* **3** — an empty roster reported "all seats claimed".
* **4** — the dashboard stated a payroll date for a class with no schedule.
* **5** — v1 vocabulary and an unsingularised rate unit on payroll settings.
* **8** — the app could not link to its own status page.
* **11** — internal domain names leaked into student-facing error copy.
* **16** — the service worker's auth bypass named a prefix that does not exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.routes.api import _PURCHASE_ERROR_COPY, _student_purchase_error
from app.services.payroll.builders import build_payroll_settings_display

# Imported at module scope deliberately. `wsgi.py` registers `@app.before_request`
# in its module body, and Flask refuses that once the app has served a request —
# so importing it lazily inside a test fails whenever an earlier test in the run
# has already made one. Collection happens before any request, so here it is safe.
import wsgi


# ---------------------------------------------------------------------------
# Finding 3 — an empty roster is a third state, not "all claimed"
# ---------------------------------------------------------------------------


class TestEmptyRosterIsNotAllClaimed:
    """"Every unclaimed seat is claimed" is vacuously true of no seats at all."""

    def _view(self, students, unclaimed):
        from app.services.roster_view_model import ClassRosterView
        view = ClassRosterView.__new__(ClassRosterView)
        object.__setattr__(view, "students", students)
        object.__setattr__(view, "unclaimed_seats", unclaimed)
        return view

    def test_empty_roster_is_not_all_claimed(self):
        view = self._view([], [])
        assert view.has_any_seats is False
        # The defect: vacuous truth reported the one state it was not in.
        assert view.all_seats_claimed is False

    def test_every_seat_claimed_is_all_claimed(self):
        view = self._view([object()], [])
        assert view.all_seats_claimed is True

    def test_some_seats_unclaimed_is_not_all_claimed(self):
        view = self._view([object()], [object()])
        assert view.all_seats_claimed is False

    def test_the_three_states_produce_three_distinct_labels(self):
        """A label per state; collapsing any two reintroduces the defect."""
        empty = self._view([], []).unclaimed_panel_label
        all_claimed = self._view([object()], []).unclaimed_panel_label
        some_open = self._view([object()], [object()]).unclaimed_panel_label

        assert len({empty, all_claimed, some_open}) == 3
        assert "no students" in empty.lower()
        assert "all seats claimed" in all_claimed.lower()


# ---------------------------------------------------------------------------
# Finding 5 — the rate unit is singular, because a rate is per one of them
# ---------------------------------------------------------------------------


class TestPayrollRateUnitIsSingular:
    def _settings(self, *, mode="advanced", time_unit="minutes", rate="1.50"):
        from decimal import Decimal
        from types import SimpleNamespace
        return SimpleNamespace(
            settings_mode=mode,
            time_unit=time_unit,
            pay_rate=Decimal(rate),
        )

    @pytest.mark.parametrize(
        "stored,expected",
        [("minutes", "minute"), ("hours", "hour"), ("seconds", "second"), ("days", "day")],
    )
    def test_stored_plural_renders_singular(self, stored, expected):
        display = build_payroll_settings_display(self._settings(time_unit=stored))
        assert display["display_rate_unit"] == expected
        # The defect rendered "$1.50/minutes".
        assert display["display_rate_with_unit"].endswith(f"/{expected}")

    def test_simple_mode_is_quoted_per_hour(self):
        display = build_payroll_settings_display(self._settings(mode="simple"))
        assert display["display_rate_with_unit"].endswith("/hour")

    def test_an_unknown_unit_is_passed_through_rather_than_mangled(self):
        """Truncating an unrecognised unit would be worse than leaving it."""
        display = build_payroll_settings_display(self._settings(time_unit="fortnights"))
        assert display["display_rate_unit"] == "fortnights"


class TestPayrollRateSurvivesADisplaySaveRoundTrip:
    """`pay_rate` is stored per minute; the Advanced form speaks the teacher's unit.

    Raised in review of this PR. The display rendered the raw per-minute number
    against the chosen unit — so a class configured at $1.50/hour showed "$0.03",
    and because that same value pre-populates the input (`admin_payroll.html`
    line ~457), saving the page again stored $0.03/hour. **The rate divided by 60
    on every re-save.** Pre-existing, but adding a unit suffix to the display made
    it explicit, and the round-trip is the property that actually matters.
    """

    @pytest.mark.parametrize(
        "unit,entered",
        [("hours", "1.50"), ("minutes", "0.25"), ("seconds", "0.01"), ("days", "120.00")],
    )
    def test_saving_what_the_form_displays_does_not_change_the_rate(self, unit, entered):
        from decimal import Decimal
        from app.services.payroll.builders import (
            rate_per_minute_to_unit,
            rate_unit_to_per_minute,
        )

        stored = rate_unit_to_per_minute(Decimal(entered), unit)
        redisplayed = rate_per_minute_to_unit(stored, unit)
        assert redisplayed == Decimal(entered)

        # And a second round trip, because the defect compounded per save.
        assert rate_per_minute_to_unit(rate_unit_to_per_minute(redisplayed, unit), unit) == Decimal(entered)

    def test_an_hourly_setting_displays_the_hourly_amount(self):
        from decimal import Decimal
        from types import SimpleNamespace

        # $1.50/hour is stored as $0.025/minute.
        settings = SimpleNamespace(
            settings_mode="advanced", time_unit="hours", pay_rate=Decimal("0.025")
        )
        display = build_payroll_settings_display(settings)
        assert display["display_per_unit_rate_value"] == "1.50"
        assert display["display_rate_with_unit"] == "$1.50/hour"

    def test_the_save_path_and_the_display_path_share_one_table(self):
        """They were independent, which is how they came to disagree."""
        import inspect
        from app.routes import admin
        source = inspect.getsource(admin.payroll_settings)
        assert "rate_unit_to_per_minute" in source, (
            "the route should convert through the shared helper, not a local table"
        )
        assert "unit_to_minute_multiplier" not in source


# ---------------------------------------------------------------------------
# Finding 8 — the app can link to its own status page
# ---------------------------------------------------------------------------


class TestStatusPageUrlAllowlist:
    def _validated(self, monkeypatch, value):
        monkeypatch.setenv("STATUS_PAGE_URL", value)
        return wsgi.get_validated_status_page_url()

    def test_the_projects_own_status_page_is_allowed(self, monkeypatch):
        url = "https://status.classroomtokenhub.com/"
        # The defect rejected this, so the footer link was silently omitted.
        assert self._validated(monkeypatch, url) == url

    def test_uptimerobot_is_still_allowed(self, monkeypatch):
        url = "https://stats.uptimerobot.com/abc123"
        assert self._validated(monkeypatch, url) == url

    def test_the_bare_origin_is_allowed(self, monkeypatch):
        """Raised in review: the deployment SOP writes it without a trailing slash.

        Requiring the slash unconditionally kept rejecting the very URL this
        finding existed to accept.
        """
        url = "https://status.classroomtokenhub.com"
        assert self._validated(monkeypatch, url) == url

    @pytest.mark.parametrize("hostile", [
        "https://status.classroomtokenhub.com.evil.example/",
        "http://status.classroomtokenhub.com/",
        "https://evil.example/status",
        "javascript:alert(1)",
    ])
    def test_an_arbitrary_destination_is_still_rejected(self, monkeypatch, hostile):
        """Widening the allowlist must not become "any URL".

        The lookalike host is the case the trailing slash in each prefix exists
        to stop: without it, `…classroomtokenhub.com.evil.example` matches.
        """
        assert self._validated(monkeypatch, hostile) is None


# ---------------------------------------------------------------------------
# Finding 11 — students are told what happened, not which domain refused
# ---------------------------------------------------------------------------


class TestStudentFacingPurchaseErrors:
    _INTERNAL_WORDS = ("ledger", "feat", "policy_uuid", "correlation", "unknown", "_")

    def test_insufficient_funds_says_so_in_plain_words(self):
        message = _student_purchase_error("INSUFFICIENT_FUNDS")
        assert "enough" in message.lower()
        assert "ledger" not in message.lower()

    def test_no_mapped_message_names_an_internal_domain_or_code(self):
        for code, message in _PURCHASE_ERROR_COPY.items():
            lowered = message.lower()
            for word in self._INTERNAL_WORDS:
                assert word not in lowered, f"{code} copy leaks {word!r}: {message}"

    def test_an_unmapped_code_falls_back_rather_than_leaking_the_code(self):
        """A new FEAT error code must degrade to something harmless.

        Echoing the code was the old behaviour's fallback, and a student can do
        nothing with `POLICY_SCOPE_MISMATCH`.
        """
        message = _student_purchase_error("SOME_NEW_CODE_NOBODY_MAPPED")
        assert "SOME_NEW_CODE_NOBODY_MAPPED" not in message
        assert message

    def test_every_error_code_the_feat_can_return_is_mapped(self):
        """The map must keep pace with the FEAT, or students get the fallback."""
        source = Path("app/feats/store_purchase_feat.py").read_text(encoding="utf-8")
        emitted = set(re.findall(r'error_code="([A-Z_]+)"', source))
        unmapped = emitted - set(_PURCHASE_ERROR_COPY)
        assert not unmapped, f"unmapped purchase error codes: {sorted(unmapped)}"


# ---------------------------------------------------------------------------
# Finding 16 — the service worker's bypass names real blueprint prefixes
# ---------------------------------------------------------------------------


def _sw_auth_routes(source: str) -> list[str]:
    """Extract the authRoutes array from service-worker source.

    A pure function over the text so the guard below can be fed a synthetic
    violation, per SOP-TEST-003 §IX.A. Matching the array rather than merely
    searching for each prefix anywhere in the file matters: the wrong prefix
    `/system-admin` contains `/system`, and a substring search would have been
    satisfied by a comment.
    """
    match = re.search(r"const\s+authRoutes\s*=\s*\[([^\]]*)\]", source)
    if not match:
        return []
    quoted = re.findall(r"'([^']*)'|\"([^\"]*)\"", match.group(1))
    return [single or double for single, double in quoted if single or double]


def _missing_auth_prefixes(source: str, prefixes: set[str]) -> set[str]:
    """Prefixes that should be bypassed by the service worker but are not."""
    declared = set(_sw_auth_routes(source))
    return {p for p in prefixes if p not in declared}


class TestServiceWorkerBypassCoversAuthenticatedBlueprints:
    """The list is duplicated between Python and JavaScript with nothing tying
    them together, which is how it came to name a prefix that never existed."""

    #: Blueprints whose responses are per-user or per-class and must never be
    #: served from the shared service-worker cache. `main` and `recovery` are
    #: excluded deliberately: both serve unauthenticated surfaces.
    AUTHENTICATED_PREFIXES = {"/admin", "/student", "/sysadmin", "/api"}

    def test_every_authenticated_prefix_is_bypassed(self, app):
        source = Path("static/sw.js").read_text(encoding="utf-8")
        missing = _missing_auth_prefixes(source, self.AUTHENTICATED_PREFIXES)
        assert not missing, f"service worker caches authenticated routes: {sorted(missing)}"

    def test_the_declared_prefixes_are_real_blueprint_prefixes(self, app):
        """Guards the actual defect: a plausible-looking prefix nothing serves."""
        registered = {
            (bp.url_prefix or "/").rstrip("/") or "/"
            for bp in app.blueprints.values()
        }
        source = Path("static/sw.js").read_text(encoding="utf-8")
        for declared in _sw_auth_routes(source):
            assert declared in registered, (
                f"service worker names {declared!r}, which is not a registered "
                f"blueprint prefix; registered are {sorted(registered)}"
            )

    def test_the_guard_reports_an_injected_violation(self):
        """Mutation proof — SOP-TEST-003 §IX.A.

        The spelling injected here is the exact one that shipped, so this
        asserts the detector catches the real mistake rather than an
        implausible one.
        """
        mutated = "const authRoutes = ['/admin', '/student', '/system-admin', '/api'];"
        missing = _missing_auth_prefixes(
            mutated, TestServiceWorkerBypassCoversAuthenticatedBlueprints.AUTHENTICATED_PREFIXES
        )
        assert missing == {"/sysadmin"}

    def test_the_guard_is_not_satisfied_by_a_mention_in_a_comment(self):
        """A near miss the detector must also survive."""
        mutated = (
            "// '/sysadmin' is handled elsewhere\n"
            "const authRoutes = ['/admin', '/student', '/api'];"
        )
        missing = _missing_auth_prefixes(
            mutated, TestServiceWorkerBypassCoversAuthenticatedBlueprints.AUTHENTICATED_PREFIXES
        )
        assert "/sysadmin" in missing
