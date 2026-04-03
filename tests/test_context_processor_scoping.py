from types import SimpleNamespace


def test_payroll_status_skips_query_without_admin_session(app, monkeypatch):
    from app import template_context

    class _Query:
        def first(self):
            raise AssertionError("PayrollSettings.query.first() should not run without an admin session")

    monkeypatch.setattr("app.models.PayrollSettings.query", _Query(), raising=False)

    with app.test_request_context("/student/login"):
        assert template_context.get_payroll_status_context(maintenance_enabled=False) == {"has_payroll_settings": False}


def test_get_logged_in_student_cached_per_request(app, monkeypatch):
    from app import auth

    calls = {"count": 0}
    student = SimpleNamespace(id=123, is_active=True)

    def fake_get(model, student_id):
        calls["count"] += 1
        return student

    monkeypatch.setattr(auth.db.session, "get", fake_get)
    monkeypatch.setattr(auth, "is_student_account_active", lambda candidate: True)

    with app.test_request_context("/student/dashboard"):
        from flask import session

        session["student_id"] = student.id

        first = auth.get_logged_in_student()
        second = auth.get_logged_in_student()

        assert first is student
        assert second is student
        assert calls["count"] == 1


def test_get_current_class_context_cached_and_resets_invalid_join_code(app, monkeypatch):
    from app.routes import student as student_routes

    student = SimpleNamespace(id=77)
    seat_a = SimpleNamespace(id=1, join_code="JOINA", teacher_id=12, block="A")
    seat_b = SimpleNamespace(id=2, join_code="JOINB", teacher_id=12, block="B")
    calls = {"count": 0}

    class _Query:
        def filter_by(self, **kwargs):
            assert kwargs == {"student_id": student.id, "is_claimed": True}
            return self

        def all(self):
            calls["count"] += 1
            return [seat_a, seat_b]

    monkeypatch.setattr(student_routes, "get_logged_in_student", lambda: student)
    monkeypatch.setattr("app.models.TeacherBlock.query", _Query(), raising=False)

    with app.test_request_context("/student/dashboard"):
        from flask import session

        session["current_join_code"] = "MISSING"

        first = student_routes.get_current_class_context()
        second = student_routes.get_current_class_context()

        assert first == {"join_code": "JOINA", "teacher_id": 12, "block": "A", "seat_id": 1}
        assert second == first
        assert second is not first
        assert session["current_join_code"] == "JOINA"
        assert calls["count"] == 1
