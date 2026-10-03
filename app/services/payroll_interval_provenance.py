"""Pure PROD original membership proof (DOM-PROD-001, SPEC-PROD-001 §VI)."""
from app.models import PayrollEvent
from app.services.attendance_service import list_attendance_intervals
from app.utils.canonical_temporal_resolver import ensure_utc


def payroll_interval_memberships(seat_id, class_id, *, ctx, as_of_utc=None):
    intervals = list_attendance_intervals(seat_id, class_id, ctx=ctx, as_of_utc=as_of_utc)
    pairs = {(i.opening_event_id, i.closing_event_id): i for i in intervals if i.closing_event_id is not None}
    result = {key: {"status": "unpaid", "event": None, "pricing": None} for key in pairs}
    events = PayrollEvent.query.filter_by(class_id=class_id, target_seat_id=seat_id,
        payroll_event_type="payroll").order_by(PayrollEvent.recorded_at.asc(), PayrollEvent.id.asc()).all()
    for event in events:
        summary = event.summary_json if isinstance(event.summary_json, dict) else {}
        if type(summary.get("allocation_version")) is not int or summary.get("allocation_version") != 1:
            for key, interval in pairs.items():
                if interval.opened_at < ensure_utc(event.recorded_at):
                    result[key] = {"status": "historical_unavailable", "event": None, "pricing": None}
            continue
        shares = summary.get("pricing", [])
        valid, mentioned = True, []
        try:
            for share in shares:
                sources = share["intervals"]
                if sum(i["credited_seconds"] for i in sources) != share["seconds"]:
                    valid = False
                for source in sources:
                    key = (source["opening_event_id"], source["closing_event_id"])
                    interval = pairs.get(key)
                    if interval is None or source != interval.as_evidence() or key in mentioned:
                        valid = False
                    mentioned.append(key)
        except (KeyError, TypeError, ValueError, AttributeError):
            valid = False
        if not shares or not mentioned:
            valid = False
        duplicates = [key for key in mentioned if key in result and result[key]["status"] == "recorded"]
        if duplicates:
            valid = False
        if not valid:
            for key, interval in pairs.items():
                if key in mentioned or interval.opened_at <= ensure_utc(event.recorded_at):
                    result[key] = {"status": "provenance_unavailable", "event": None, "pricing": None}
            continue
        for key in mentioned:
            if key in result:
                result[key] = {"status": "recorded", "event": event, "pricing": shares}
    return result


def payroll_provenance_history_limitations(seat_id, class_id, *, ctx):
    """Whether scoped original payroll history lacks frozen interval evidence."""
    if ctx.class_id != class_id:
        raise ValueError("Payroll context does not authorize this class.")
    events = PayrollEvent.query.filter_by(class_id=class_id,target_seat_id=seat_id,
        payroll_event_type="payroll").all()
    for event in events:
        summary = event.summary_json if isinstance(event.summary_json, dict) else {}
        if type(summary.get("allocation_version")) is not int or summary.get("allocation_version") != 1 or not summary.get("pricing"):
            return True
        if not isinstance(summary["pricing"], list) or any(
                not isinstance(share, dict) or not share.get("intervals") for share in summary["pricing"]):
            return True
    return False
