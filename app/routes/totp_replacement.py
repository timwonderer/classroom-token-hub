"""The HTTP half of self-service TOTP replacement, shared by both roles (FEAT-IDEN-106).

``/admin/totp/replace/*`` and ``/sysadmin/totp/replace/*`` are thin wrappers over these
functions, so teacher and sysadmin principals run one implementation (DOM-IDEN-003 §VII.A).
Nothing here touches the database: every mutation is a FEAT in
``app.feats.credential_operations_feat``. The wrappers own authentication, CSRF (the global
``CSRFProtect``) and rate limits.

The browser supplies only the step-up token, the challenge it was issued and the new code.
The pending seed is held on the server operation and is shown once, in the response to
``start``; it is never in a cookie, URL or log.
"""
from __future__ import annotations

import base64
import io

import qrcode
from flask import current_app, flash, jsonify, request, session, url_for

from app.feats import credential_operations_feat as feat
from app.services import credential_lifecycle as lifecycle
from app.services import passkey_service
from app.utils.passwordless_client import get_public_api_key
from app.utils.user_ids import passkey_external_id

SUCCESS_MESSAGE = "Authenticator replaced. Sign in again with your new authenticator."

_PROOF_REFUSED = (403, "That passkey was not accepted.")
_REFUSALS = {
    "challenge_invalid": _PROOF_REFUSED,
    "step_up_replayed": _PROOF_REFUSED,
    "step_up_unavailable": (503, "Authenticator replacement is unavailable right now. Nothing was changed; try again later."),
    "operation_already_open": (409, "Another credential change is already in progress. Cancel it or wait for it to expire."),
    "binding_mismatch": (409, "That replacement is no longer the one in progress. Reload the page."),
    "operation_not_found": (404, "There is no authenticator replacement in progress."),
    "wrong_purpose": (409, "A different credential change is in progress. Finish or cancel it first."),
    "session_not_current": (401, "Your sign-in is no longer current. Sign in again."),
    "recovery_active": (409, "Account recovery is in progress. Finish or cancel it first."),
    "operation_expired": (409, "That replacement timed out. Start again."),
    "stale_generation": (409, "Your credentials changed. Start again."),
    "operation_not_open": (409, "That replacement is not in a state that can continue. Start again."),
    "no_candidate_held": (409, "That replacement has no new authenticator yet. Start again."),
    "ineligible_principal": (403, "This account cannot replace its authenticator."),
    "totp_not_activated": (409, "This account has no authenticator to replace."),
}


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _guarded(action):
    """Run ``action`` and translate every refusal into the shared JSON answers."""
    try:
        return action()
    except lifecycle.CredentialOperationRefused as exc:
        current_app.logger.warning("Authenticator replacement refused: %s", exc.category)
        status, message = _REFUSALS.get(exc.category, (400, exc.public_message))
        code = exc.category
        if code.startswith("step_up_") and code not in _REFUSALS:
            # Which evidence check failed is logged, not told to the browser.
            status, message = _PROOF_REFUSED
            code = "proof_rejected"
        return jsonify({"error": message, "code": code}), status
    except passkey_service.PasskeyServiceUnavailable:
        current_app.logger.error("Passkey provider did not confirm the request")
        return jsonify({"error": "The passkey service is unavailable. Try again shortly.", "code": "provider_unavailable"}), 503
    except passkey_service.PasskeyError as exc:
        current_app.logger.warning("Authenticator replacement refused: %s", exc)
        return jsonify({"error": _PROOF_REFUSED[1], "code": "proof_rejected"}), _PROOF_REFUSED[0]
    except ValueError as exc:
        current_app.logger.error("Passwordless.dev configuration error: %s", exc)
        return jsonify({"error": "Passkey service not configured", "code": "not_configured"}), 503
    except Exception:
        current_app.logger.exception("Unexpected failure in an authenticator replacement")
        return jsonify({"error": "That replacement could not be completed.", "code": "failed"}), 500


def _qr_data_uri(uri: str) -> str:
    buffer = io.BytesIO()
    qrcode.make(uri).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def challenge(*, user_id: str, alias: str):
    """Store the single-use challenge for the principal's step-up ceremony; return it with what the browser needs."""
    def action():
        api_key = get_public_api_key()
        value = feat.issue_totp_replacement_challenge(
            user_id=user_id, session_nonce=session.get("current_session_nonce"),
        )
        return jsonify({
            "challenge": value, "apiKey": api_key, "alias": alias, "userId": passkey_external_id(user_id),
        }), 200
    return _guarded(action)


def start(*, user_id: str, account_name: str):
    """Consume the step-up evidence, stage the pending seed, and show its setup material once."""
    def action():
        data = _body()
        token, answered = data.get("token"), data.get("challenge")
        secret, uri, binding = feat.begin_totp_replacement(
            user_id=user_id, session_nonce=session.get("current_session_nonce"),
            token=token if isinstance(token, str) else "", challenge=answered if isinstance(answered, str) else "",
            account_name=account_name,
        )
        return jsonify({"secret": secret, "qr": _qr_data_uri(uri), "binding": binding}), 200
    return _guarded(action)


def confirm(*, user_id: str, login_endpoint: str):
    """Activate the new authenticator when its code proves the pending seed; success ends the sign-in."""
    def action():
        code = _body().get("code")
        accepted = feat.confirm_totp_replacement(
            user_id=user_id, session_nonce=session.get("current_session_nonce"),
            code=code if isinstance(code, str) else "",
        )
        if not accepted:
            return jsonify({"error": "That authenticator code was not accepted.", "code": "code_rejected"}), 400
        session.clear()
        flash(SUCCESS_MESSAGE, "success")
        return jsonify({
            "success": True, "message": SUCCESS_MESSAGE, "redirect": url_for(login_endpoint),
        }), 200
    return _guarded(action)


def cancel(*, user_id: str):
    """Cancel the open replacement; the existing authenticator is untouched."""
    def action():
        # An omitted key or JSON null is the unbound cancel; any other value is refused by the FEAT.
        feat.abandon_totp_replacement(
            user_id=user_id, session_nonce=session.get("current_session_nonce"),
            binding=_body().get("binding"),
        )
        return jsonify({"success": True}), 200
    return _guarded(action)
