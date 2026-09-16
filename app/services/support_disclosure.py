"""Teacher-authorized disclosure of frozen Support records (DOM-SUP-001)."""
from copy import deepcopy

PERMISSION_FIELDS = {
    'balances': 'share_balances',
    'transaction': 'share_transaction',
    'recent_transactions': 'share_recent_transactions',
    'student_report': 'share_student_report',
}
TECHNICAL_FIELDS = ('timestamp', 'page_url', 'ip_address', 'user_agent')


def permissions_from_form(form):
    """Only individually selected checkboxes grant permission; no blanket flag."""
    return {category: form.get(field) == 'on' for category, field in PERMISSION_FIELDS.items()}


def disclosed_snapshot(issue):
    """Project frozen data, never query live class state or forward unknown fields."""
    source = issue.context_snapshot or {}
    permissions = issue.support_permissions or {}
    result = {key: deepcopy(source[key]) for key in TECHNICAL_FIELDS if key in source}
    allowed = {
        'balances': ('checking', 'savings', 'total'),
        'transaction': ('id', 'amount', 'account_type', 'description', 'type', 'timestamp', 'is_void'),
        'recent_transactions': ('id', 'amount', 'description', 'timestamp'),
    }
    for category, fields in allowed.items():
        if permissions.get(category) is not True or category not in source:
            continue
        value = source[category]
        if category == 'recent_transactions':
            result[category] = [{k: deepcopy(row[k]) for k in fields if k in row} for row in value]
        else:
            result[category] = {k: deepcopy(value[k]) for k in fields if k in value}
    return result


def disclosed_report(issue):
    """Student text requires teacher permission; direct teacher text is explicit submission."""
    if (issue.support_permissions or {}).get('student_report') is not True:
        return None, None
    return issue.student_explanation, issue.student_expected_outcome
