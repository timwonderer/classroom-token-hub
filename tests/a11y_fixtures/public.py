"""Fixture states for signed-out templates: error pages and auth entry pages."""

from __future__ import annotations

from tests.a11y_fixtures import register

register("error_400.html", "default", lambda: {"error_message": "The request could not be understood."})
register("error_400.html", "without-message", lambda: {"error_message": None})
register("error_401.html", "default", lambda: {})
register("error_403.html", "default", lambda: {})
register("error_404.html", "default", lambda: {"request_url": "https://cth.example/missing-page"})
register("error_429.html", "default", lambda: {"limit_description": "5 per 1 hour"})
register("error_500.html", "default", lambda: {})
register("error_500.html", "with-error-id", lambda: {"error_id": "ERR-A11Y-0001"})
register("error_503.html", "default", lambda: {})

import base64
from datetime import datetime, timezone

import pytz
from flask import flash

from app.forms import (
    AdminSignupForm,
    AdminTOTPConfirmForm,
    StudentCreateUsernameForm,
    StudentPinPassphraseForm,
    StudentVerifySavedUsernameForm,
)
from app.forms import AdminResetCredentialsForm
from app.services.identity.builders import build_totp_setup_view

# A fixed 1x1 PNG, so the QR slot renders an image without generating a secret.
_PIXEL_PNG_B64 = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c6360606060000000050001a5f645400000000049454e44ae426082"
)).decode("ascii")
_TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # the RFC example secret, not a credential
_EXPIRES = datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc)
_PAGE_TOKEN = "a11y-fixture-page-token"
_MISMATCH = "That doesn't match your username. Check the copy you saved and try again."


def _admin_signup(error: bool):
    def build():
        if error:
            flash("Username is not available. Please choose another.", "error")
        return {"form": AdminSignupForm(), "turnstile_site_key": None}
    return build


def _admin_totp(error: bool):
    def build():
        if error:
            flash("Security verification failed. Please complete the check and try again.", "error")
        form = AdminTOTPConfirmForm()
        form.username.data = "teacher-example"
        return {
            "form": form,
            "totp_view": build_totp_setup_view(_TOTP_SECRET, _PIXEL_PNG_B64, []),
            "turnstile_site_key": None,
        }
    return build


register("admin_signup.html", "default", _admin_signup(False), path="/admin/signup")
register("admin_signup.html", "error", _admin_signup(True), path="/admin/signup")
register("admin_signup_totp.html", "default", _admin_totp(False), path="/admin/signup")
register("admin_signup_totp.html", "error", _admin_totp(True), path="/admin/signup")
register("admin_create_class.html", "default", lambda: {"timezone_choices": pytz.common_timezones}, path="/admin/create-class")
register("admin_create_class.html", "error", lambda: (
    flash("Class name and your display name are required.", "error")
    or {"timezone_choices": pytz.common_timezones}
), path="/admin/create-class")
register("admin_recovery_prepare.html", "default", lambda: {"class_refs": ["class-ref-1", "class-ref-2"]}, path="/admin/recover")
register("admin_recovery_status.html", "waiting", lambda: {"status": {
    "expires_at": _EXPIRES,
    "classes": [
        {"class_ref": "class-ref-1", "number": 1, "label": "Chemistry Period 1", "received": False, "selected": True},
        {"class_ref": "class-ref-2", "number": 2, "label": "Period 3", "received": True, "selected": True},
    ],
}}, path="/admin/recovery-status")
register("admin_recovery_saved.html", "default", lambda: {
    "resume_pin": "482916", "codes_saved": 0,
    "recovery_request": type("RecoveryRequestView", (), {"expires_at": _EXPIRES})(),
}, path="/admin/reset-credentials")
register("admin_reset_credentials.html", "default", lambda: {
    "form": AdminResetCredentialsForm(), "show_qr": True, "qr_b64": _PIXEL_PNG_B64,
    "totp_secret": _TOTP_SECRET, "new_username": "teacher-example",
}, path="/admin/reset-credentials")

register("student_create_username.html", "default", lambda: {
    "theme_prompt": "Pick a word that describes your favorite animal.",
    "form": StudentCreateUsernameForm(),
}, path="/student/create-username")
register("student_verify_username.html", "default", lambda: {
    "verify_form": StudentVerifySavedUsernameForm(), "error_message": None,
    "retention_page_token": _PAGE_TOKEN,
}, path="/student/verify-username")
register("student_verify_username.html", "mismatch", lambda: {
    "verify_form": StudentVerifySavedUsernameForm(), "error_message": _MISMATCH,
    "retention_page_token": _PAGE_TOKEN,
}, path="/student/verify-username")
register("student_pin_setup.html", "unverified", lambda: {
    "username": "example-student", "username_verified": False, "error_message": None,
    "form": StudentPinPassphraseForm(), "verify_form": StudentVerifySavedUsernameForm(),
    "retention_page_token": _PAGE_TOKEN,
}, path="/student/setup-pin-passphrase")
register("student_pin_setup.html", "verified", lambda: {
    "username": None, "username_verified": True, "error_message": None,
    "form": StudentPinPassphraseForm(), "verify_form": StudentVerifySavedUsernameForm(),
    "retention_page_token": _PAGE_TOKEN,
}, path="/student/setup-pin-passphrase")
