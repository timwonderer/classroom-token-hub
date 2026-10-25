"""The test harness may DROP only its own local test database or its own template (tests/conftest.py)."""
import pytest

from tests.helpers.db_drop_guard import droppable_test_database_refusal

URL = "postgresql://postgres:pw@localhost:5432/classroom_economy_v2_test"
PID = 4242


@pytest.mark.parametrize("name", ["classroom_economy_v2_test", "classroom_economy_v2_test_tmpl_4242"])
def test_drop_guard_allows_the_configured_test_database_and_this_process_template(name):
    assert droppable_test_database_refusal(URL, name, PID) is None


@pytest.mark.parametrize(
    "url, name, reason",
    [
        # Production's database name, configured by mistake.
        ("postgresql://postgres:pw@localhost:5432/classroom_economy", "classroom_economy", "not named as a test"),
        # "test" in the password or host is not a test database (the app's own guard accepts these).
        ("postgresql://postgres:test@localhost:5432/classroom_economy", "classroom_economy", "not named as a test"),
        ("postgresql://u:pw@db.internal:5432/classroom_economy_v2_test", "classroom_economy_v2_test", "not local"),
        ("postgresql://u:pw@test-db.example.com:5432/x_test", "x_test", "not local"),
        ("sqlite:///classroom_test.db", "classroom_test", "not a PostgreSQL URL"),
        # A substring is not the word: "contest" contains "test".
        ("postgresql://u:pw@localhost/contest_db", "contest_db", "not named as a test"),
        (URL, "postgres", "reserved"),
        (URL, "template1", "reserved"),
        # Another database on the same server, even one named like a test database.
        (URL, "other_suite_test", "neither the configured test database"),
        # Another process's template.
        (URL, "classroom_economy_v2_test_tmpl_9999", "neither the configured test database"),
        ("not a url", "x_test", "does not parse"),
    ],
)
def test_drop_guard_refuses(url, name, reason):
    refusal = droppable_test_database_refusal(url, name, PID)
    assert refusal is not None and reason in refusal
