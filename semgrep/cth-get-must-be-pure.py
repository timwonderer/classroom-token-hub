"""Semgrep test cases for cth-get-must-be-pure.yaml. Not imported or executed."""
from app.extensions import db
from app.feats.base import FEATContext


@bp.route("/dashboard")
def default_methods_commits():
    row = load()
    # ruleid: cth-get-must-be-pure
    db.session.commit()
    return row


@bp.route("/expire", methods=["GET"])
@login_required
def explicit_get_adds():
    # ruleid: cth-get-must-be-pure
    db.session.add(Goal(expired=True))
    return "ok"


@bp.get("/settle")
def shorthand_get_flushes():
    # ruleid: cth-get-must-be-pure
    db.session.flush()


@login_required
@bp.route("/repair")
def decorator_order_does_not_matter():
    # ruleid: cth-get-must-be-pure
    with FEATContext("FEAT-X", idempotency_key="k"):
        repair()


@bp.route("/grafana", methods=["GET"], defaults={"path": ""})
def get_route_with_defaults_commits(path):
    # ruleid: cth-get-must-be-pure
    db.session.commit()


@bp.route("/insurance", endpoint="insurance")
def default_get_with_endpoint_adds():
    # ruleid: cth-get-must-be-pure
    db.session.add(Policy())


@bp.route("/status", strict_slashes=False, methods=("get", "head"))
def get_and_head_tuple_flushes():
    # ruleid: cth-get-must-be-pure
    db.session.flush()


@bp.route("/form", methods=["GET", "POST"], endpoint="form")
def mixed_route_with_endpoint_may_commit_on_post():
    # ok: cth-get-must-be-pure
    db.session.commit()


@bp.route("/pay", methods=["POST"])
def post_route_may_commit():
    # ok: cth-get-must-be-pure
    db.session.commit()


@bp.post("/claim")
def shorthand_post_may_write():
    # ok: cth-get-must-be-pure
    db.session.add(Claim())


@bp.route("/view")
def get_route_that_only_reads():
    # ok: cth-get-must-be-pure
    return db.session.query(Seat).all()


def helper_outside_any_route():
    # ok: cth-get-must-be-pure
    db.session.commit()


# ruleid: cth-feat-context-on-get-route
@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("60 per minute", methods=["POST"])
@requires_feat_context("FEAT-IDEN-001")
def mixed_route_wrapped_in_feat():
    return render()


# ruleid: cth-feat-context-on-get-route
@bp.route("/page")
@requires_feat_context("FEAT-X")
def default_get_wrapped_in_feat():
    return render()


# ok: cth-feat-context-on-get-route
@bp.route("/submit", methods=["POST"])
@requires_feat_context("FEAT-X")
def post_only_wrapped_in_feat():
    return do()


# ok: cth-feat-context-on-get-route
@bp.route("/form", methods=["GET", "POST"])
def mixed_route_entering_feat_on_post_only():
    if request.method == "POST":
        with FEATContext("FEAT-X", idempotency_key="k"):
            do()
    return render()


# ruleid: cth-feat-context-on-get-route
@bp.route("/insurance", endpoint="insurance")
@requires_feat_context("FEAT-X")
def default_get_with_endpoint_wrapped_in_feat():
    return render()


# ok: cth-feat-context-on-get-route
@bp.route("/submit", methods=["POST"], endpoint="submit")
@requires_feat_context("FEAT-X")
def post_only_with_endpoint_wrapped_in_feat():
    return do()
