"""Template context helpers that are safe to import in tests."""

from flask import session


def get_payroll_status_context(*, maintenance_enabled: bool) -> dict:
    """Return admin payroll setup state for template context."""
    if maintenance_enabled or 'admin_id' not in session:
        return {"has_payroll_settings": False}

    from app.models import PayrollSettings

    return {"has_payroll_settings": PayrollSettings.query.first() is not None}
