"""The HTTP half of passkey enrollment, replacement and revocation, shared by both roles.

``/admin/passkey/*`` and ``/sysadmin/passkey/*`` are thin wrappers over these
functions, so the two principals run one implementation (DOM-IDEN-003 §VII.A "single
Identity-owned implementation"). Nothing here touches the database: every mutation is
a FEAT in ``app.feats.passkey_lifecycle_feat`` (FEAT-IDEN-102/107). The wrappers own
authentication, CSRF (the global ``CSRFProtect``) and rate limits.

Every refusal answers with a coarse ``code`` and a fixed message; none names a
credential, a label or a principal.
"""
from __future__ import annotations

from flask import current_app, flash, jsonify, request, session, url_for

from app.feats import passkey_lifecycle_feat as feat
from app.services import credential_lifecycle as lifecycle
from app.services import passkey_service
from app.utils.passwordless_client import get_public_api_key

SUCCESS_MESSAGES = {
    "activated": "Passkey added. Sign in again to continue.",
    "replaced": "Passkey replaced. Sign in again to continue.",
    "revoked": "Passkey removed. Sign in again to continue.",
}

_REFUSALS = {
    "proof_rejected": (403, "That authenticator code was not accepted."),
    "proof_kind_mismatch": (403, "That authenticator code was not accepted."),
    "operation_already_open": (409, "Another credential change is already in progress. Cancel it or wait for it to expire."),
    "only_passkey": (409, "This is your only passkey. Replace it instead of deleting it."),
    "credential_not_found": (404, "Passkey not found."),
    "operation_not_found": (404, "There is no passkey change in progress."),
    "session_not_current": (401, "Your sign-in is no longer current. Sign in again."),
    "recovery_active": (409, "Account recovery is in progress. Finish or cancel it first."),
    "operation_expired": (409, "That passkey change timed out. Start again."),
    "stale_generation": (409, "Your credentials changed. Start again."),
    "operation_not_open": (409, "That passkey change is not in a state that can continue. Start again."),
    "retirement_committed": (409, "That change is already being finished and cannot be cancelled."),
    "binding_mismatch": (409, "That passkey registration belongs to an earlier attempt. Start again."),
    "registration_interrupted": (409, "That registration was interrupted. Cancel it and start again."),
    "registration_rejected": (400, "That passkey could not be registered. Start again."),
}


def _body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _refusal(exc: lifecycle.CredentialOperationRefused):
    status, message = _REFUSALS.get(exc.category, (400, exc.public_message))
    return jsonify({"error": message, "code": exc.category}), status


def _guarded(action):
    """Run ``action`` and translate every refusal into the shared JSON answers."""
    try:
        return action()
    except lifecycle.CredentialOperationRefused as exc:
        current_app.logger.warning("Passkey change refused: %s", exc.category)
        return _refusal(exc)
    except passkey_service.PasskeyAliasConflict as exc:
        current_app.logger.warning("Passkey registration refused: %s", exc)
        return jsonify({"error": exc.public_message, "code": "alias_conflict"}), 409
    except passkey_service.PasskeyServiceUnavailable as exc:
        current_app.logger.error("Passkey provider did not confirm the request")
        return jsonify({"error": exc.public_message, "code": "provider_unavailable"}), 503
    except passkey_service.PasskeyError as exc:
        current_app.logger.warning("Passkey registration refused: %s", exc)
        return jsonify({"error": exc.public_message, "code": "registration_rejected"}), 400
    except ValueError as exc:
        current_app.logger.error("Passwordless.dev configuration error: %s", exc)
        return jsonify({"error": "Passkey service not configured", "code": "not_configured"}), 503
    except Exception:
        current_app.logger.exception("Unexpected failure in a passkey change")
        return jsonify({"error": "That passkey change could not be completed.", "code": "failed"}), 500


def _signed_out_success(result, login_endpoint: str):
    """A completed credential change voids the sign-in: say so, and send the user to sign in.

    A replayed result (the change already completed; the retained receipt answered) is the
    same bounded success, and touches nothing.
    """
    outcome, replayed = result
    if not replayed:
        session.clear()
    flash(SUCCESS_MESSAGES[outcome], "success")
    return jsonify({
        "success": True,
        "message": SUCCESS_MESSAGES[outcome],
        "redirect": url_for(login_endpoint),
    }), 200


def register_start(*, user_id: str, alias: str, display_name: str):
    """Begin an enrollment, or a replacement when ``replace_passkey_id`` is given."""
    def action():
        data = _body()
        code = data.get("totp_code")
        proof = lifecycle.TotpCode(code if isinstance(code, str) else "")
        replace = data.get("replace_passkey_id")
        if replace is not None and (isinstance(replace, bool) or not isinstance(replace, int)):
            raise lifecycle.CredentialOperationRefused("credential_not_found")
        # Read before any operation row exists: a missing public key must leave nothing pending.
        api_key = get_public_api_key()
        token, binding = feat.start_registration(
            user_id=user_id, session_nonce=session.get("current_session_nonce"), proof=proof,
            alias=alias, display_name=display_name, replace_passkey_id=replace,
        )
        return jsonify({"token": token, "binding": binding, "apiKey": api_key}), 200
    return _guarded(action)


def register_finish(*, user_id: str, login_endpoint: str):
    """Finish the registration the browser completed; success ends the sign-in."""
    def action():
        data = _body()
        token = data.get("token")
        name = data.get("authenticatorName")
        result = feat.finish_registration(
            user_id=user_id, session_nonce=session.get("current_session_nonce"),
            token=token if isinstance(token, str) else "",
            binding=data.get("binding"),
            authenticator_name=name if isinstance(name, str) else "",
        )
        return _signed_out_success(result, login_endpoint)
    return _guarded(action)


def revoke(*, user_id: str, passkey_id: int, login_endpoint: str):
    """Revoke one passkey after fresh TOTP; success ends the sign-in."""
    def action():
        code = _body().get("totp_code")
        result = feat.revoke_passkey(
            user_id=user_id, session_nonce=session.get("current_session_nonce"),
            totp_code=code if isinstance(code, str) else "", passkey_id=passkey_id,
        )
        return _signed_out_success(result, login_endpoint)
    return _guarded(action)


def resume(*, user_id: str, login_endpoint: str):
    """Finish the principal's committed retirement; success ends the sign-in."""
    def action():
        name = _body().get("authenticatorName")
        result = feat.resume_retirement(
            user_id=user_id, binding=_body().get("binding"),
            authenticator_name=name if isinstance(name, str) else None,
        )
        return _signed_out_success(result, login_endpoint)
    return _guarded(action)


def cancel(*, user_id: str):
    """Cancel the principal's passkey change while it can still be cancelled."""
    def action():
        # An omitted key or JSON null is the unbound cancel. Any other value, however malformed,
        # is passed through so the FEAT refuses it as ``binding_mismatch``.
        binding = _body().get("binding")
        feat.cancel_registration(
            user_id=user_id, session_nonce=session.get("current_session_nonce"), binding=binding,
        )
        return jsonify({"success": True}), 200
    return _guarded(action)
