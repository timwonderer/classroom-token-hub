"""Which database the test harness may DROP (tests/conftest.py's template-clone reset).

Pure, so tests/test_conftest_drop_guard.py can prove each refusal fires without a database.
"""
import re

import sqlalchemy as sa

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_RESERVED_DATABASES = {"postgres", "template0", "template1"}


def droppable_test_database_refusal(test_db_url, name, pid):
    """Why `name` must not be dropped as a test scratch database, or None if it may be.

    `name` must be exactly the configured test database or this process's template.
    """
    try:
        url = sa.engine.make_url(test_db_url)
    except Exception:
        return "test database URL does not parse"
    if not url.drivername.startswith("postgresql"):
        return f"not a PostgreSQL URL ({url.drivername})"
    if url.host not in _LOCAL_HOSTS:
        return f"host {url.host!r} is not local"
    test_db = url.database or ""
    if not re.search(r"(^|_)test(_|$)", test_db):
        return f"configured database {test_db!r} is not named as a test database"
    if name in _RESERVED_DATABASES:
        return f"{name!r} is a reserved database"
    if name not in (test_db, f"{test_db}_tmpl_{pid}"):
        return f"{name!r} is neither the configured test database nor this process's template"
    return None
