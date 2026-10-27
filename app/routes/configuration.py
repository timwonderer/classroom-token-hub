"""Class configuration transfer forms; all mutations belong to FEAT-CLASS-009/010/011."""
from io import BytesIO
from flask import Blueprint, g, render_template, request, session, send_file, flash, redirect, url_for
from flask_wtf import FlaskForm
from app.auth import admin_required
from app.feats import configuration_portability as transfer
from app.services.configuration_artifact import ConfigurationError, MAX_BYTES, digest, StrictJSON
from app.services.configuration_fields import SCHEDULES, SCHEMAS
from app.services.configuration_display import FAMILY_LABELS, FIELD_LABELS, family_labels, preview_sections
from app.services.insurance_configuration import InsuranceContractViolation
from app.services.store_service import StoreServiceError

configuration_bp = Blueprint("configuration", __name__, url_prefix="/admin/configuration")


def _entries(groups):
    entries = {}
    for family, values in groups.items():
        if family == "store":
            entries[family] = [row["name"] for row in values]
        elif family == "insurance":
            entries[family] = [f'{group["name"] + " — " if group["name"] else ""}{row["title"] or "Insurance policy"} (rank {row["tier_level"] or "single"})'
                for group in values for row in group["policies"]]
        elif family == "hall_pass":
            entries[family] = [row["pass_name"] for row in values["pass_type_payload"]]
    return entries


def _selection(groups):
    result = {}
    for family in groups:
        if request.form.get("include_" + family) != "yes":
            continue
        if family in ("store", "insurance", "hall_pass"):
            try:
                result[family] = [int(value) for value in request.form.getlist("entry_" + family)]
            except ValueError:
                raise ConfigurationError("Invalid selection")
        else:
            result[family] = True
    return result


def _schedules(groups, selection):
    choices = {}
    for family in set(selection) & set(SCHEDULES):
        mode = request.form.get("schedule_" + family, "exported")
        choice = {"mode": mode}
        if mode == "custom":
            def fields(prefix):
                result = {}
                for field in SCHEDULES[family]:
                    value = request.form.get(prefix + field) or None
                    if value is not None and SCHEMAS[family][field] == "int":
                        try:
                            value = int(value)
                        except ValueError:
                            raise ConfigurationError("Schedule interval must be a whole number")
                    result[field] = value
                return result
            choice["values"] = ([fields(f"custom_store_{i}_") for i in selection[family]]
                                 if family == "store" else fields("custom_" + family + "_"))
        choices[family] = choice
    return choices


@configuration_bp.route("/", methods=["GET", "POST"])
@admin_required
def settings():
    form = FlaskForm()
    context = g.canonical_context
    nonce = session.get("current_session_nonce")
    stage = "start"
    raw = ""
    groups = transfer.inventory(context)
    destination = groups
    preview = None
    if request.method == "POST":
        if not form.validate_on_submit():
            return render_template("configuration_transfer.html", labels=FAMILY_LABELS, field_labels=FIELD_LABELS, form=form, groups=groups,
                entries=_entries(groups), stage=stage, destination=destination, schedules=SCHEDULES, schemas=SCHEMAS), 400
        try:
            action = request.form.get("action")
            if action == "export":
                inventory_digest = request.form.get("inventory_digest")
                if not inventory_digest:
                    raise ConfigurationError("Review your export selection again")
                payload = transfer.export_configuration(context, nonce, _selection(groups), expected_inventory_digest=inventory_digest)
                return send_file(BytesIO(payload), mimetype="application/octet-stream", as_attachment=True,
                    download_name="class-configuration.cthconfig", max_age=0)
            if action == "upload":
                upload = request.files.get("configuration")
                if not upload:
                    raise ConfigurationError("Choose a configuration file")
                raw = upload.read(MAX_BYTES + 1).decode("utf-8")
                envelope = transfer.inspect_import(context, nonce, raw)
                groups = envelope["groups"]
                stage = "choose"
            elif action == "preview":
                raw = request.form.get("artifact", "")
                envelope = transfer.inspect_import(context, nonce, raw)
                groups = envelope["groups"]
                selection = _selection(groups)
                preview = transfer.preview_import(context, nonce, raw, selection, _schedules(groups, selection))
                stage = "confirm"
            elif action == "confirm":
                result = transfer.confirm_import(context, nonce, request.form.get("artifact", ""), request.form.get("confirmation", ""))
                flash("Configuration imported into this class. Existing activity keeps its original terms.", "success")
                return render_template("configuration_transfer.html", labels=FAMILY_LABELS, field_labels=FIELD_LABELS, form=form, stage="done",
                    result=transfer.import_result_view(context, result), skipped_labels=family_labels(result.get("skipped") or []))
            elif action == "cleanup":
                count = transfer.cleanup_receipts(context, nonce)
                flash(f"Removed {count} expired retry receipts.", "success")
                return redirect(url_for("configuration.settings"))
            elif action != "upload":
                raise ConfigurationError("Invalid action")
        except (ValueError, UnicodeError, InsuranceContractViolation, StoreServiceError) as exc:
            flash(str(exc), "danger")
            stage = "start"
            groups = destination
    return render_template("configuration_transfer.html", labels=FAMILY_LABELS, field_labels=FIELD_LABELS, form=form, groups=groups, entries=_entries(groups),
        stage=stage, raw=raw, destination=destination, schedules=SCHEDULES, schemas=SCHEMAS, preview=preview,
        sections=preview_sections(preview["groups"]) if preview else [],
        skipped_labels=family_labels(preview["skipped"]) if preview else [],
        inventory_digest=digest(StrictJSON.dumps(groups)))
