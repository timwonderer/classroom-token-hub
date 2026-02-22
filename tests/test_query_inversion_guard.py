"""Regression guards for the query inversion invariant.

These tests verify that student-facing queries never use
``teacher_id`` as the sole class boundary or expose data
with ``join_code IS NULL``.
"""

import os


ROUTE_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, "app", "routes"
)

# Patterns that are prohibited on student-facing paths (student.py)
STUDENT_FILE = os.path.join(ROUTE_DIR, "student.py")


def _read_source(filepath):
    with open(filepath) as f:
        return f.read()


def test_student_routes_no_join_code_is_none_filter():
    """Student-facing queries must never use ``join_code IS NULL`` or ``join_code == None``
    as a filter that includes data in student-visible results."""
    source = _read_source(STUDENT_FILE)

    # These patterns indicate a join_code IS NULL fallback on student paths
    prohibited_patterns = [
        "join_code.is_(None)",
        "join_code == None",
        "or_(StoreItem.join_code == None",
        "or_(StoreItem.join_code.is_(None)",
    ]

    violations = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # skip comments
        for pattern in prohibited_patterns:
            if pattern in line:
                violations.append(f"  L{i}: {stripped}")

    assert not violations, (
        "Student-facing routes must not use join_code IS NULL fallbacks.\n"
        "Violations found in student.py:\n" + "\n".join(violations)
    )


def test_student_routes_no_teacher_id_class_scoping():
    """Student-facing queries must not use ``teacher_id`` as the sole class boundary
    for data retrieval (e.g., settings, store items, policies).

    Allowed: teacher_id in ownership/identity-level queries (e.g., StudentTeacher).
    """
    source = _read_source(STUDENT_FILE)

    # High-risk patterns where teacher_id is used as class boundary
    prohibited_patterns = [
        "StoreItem.teacher_id ==",
        "InsurancePolicy.teacher_id",
    ]

    # Allowlist these exact patterns (ownership checks, not class scoping)
    allowlist = [
        "StudentTeacher",
        "# teacher_id",  # comments
        "teacher_id=teacher_id,  # audit",
        "Transaction.teacher_id",  # Transaction creation (audit field)
    ]

    violations = []
    for i, line in enumerate(source.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for pattern in prohibited_patterns:
            if pattern in line:
                if any(allowed in line for allowed in allowlist):
                    continue
                violations.append(f"  L{i}: {stripped}")

    assert not violations, (
        "Student-facing routes should not use teacher_id as class boundary.\n"
        "Violations found in student.py:\n" + "\n".join(violations)
    )
