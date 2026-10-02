"""Structural guard: economic_engine is read only through the one resolver.

Owner ruling 2026-09-30 (DOM-CLASS-003 §VII, FEAT-CLASS-005 1.1). The detector
lives in ``tests/guards/economic_engine_reads.py``; the mutation proofs feed it
the spellings a regression would really use (SOP-TEST-003 §IX.A), including the
three competing readers this ruling removed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.guards.economic_engine_reads import RESOLVER_MODULE, find_violations

REPO = Path(__file__).resolve().parents[1]


def _app_sources():
    for path in sorted((REPO / "app").rglob("*.py")):
        yield str(path.relative_to(REPO)), path.read_text(encoding="utf-8")


def test_no_module_outside_the_resolver_reads_economic_engine():
    violations = [
        violation
        for path, source in _app_sources()
        for violation in find_violations(path, source)
    ]
    assert not violations, "\n".join(str(v) for v in violations)


def test_the_resolver_is_where_the_reads_are():
    source = (REPO / RESOLVER_MODULE).read_text(encoding="utf-8")
    assert "EconomicEngine.query" in source
    assert find_violations("app/elsewhere.py", source)


@pytest.mark.parametrize("snippet", [
    # "Newest created_at" — the pre-ruling admin and policy-mode readers.
    "from app.models import EconomicEngine\n"
    "engine = EconomicEngine.query.filter_by(class_id=c).order_by(EconomicEngine.created_at.desc()).first()\n",
    "from app.models import EconomicEngine as EE\nengine = EE.query.first()\n",
    "from app import models\nengine = models.EconomicEngine.query.first()\n",
    # The class-feature link timeline — the pre-ruling get_effective_economic_engine.
    "engine = db.session.get(EconomicEngine, class_feature.economic_version_id)\n",
    "engine = class_feature.economic_version\n",
    # An accrual-style private timeline.
    "import sqlalchemy as sa\nrows = db.session.execute(sa.select(EconomicEngine).where(EconomicEngine.class_id == c))\n",
    "rate = db.session.query(EconomicEngine.interest_rate).filter(EconomicEngine.class_id == c).scalar()\n",
    "from sqlalchemy import text\n"
    "rows = db.session.execute(text('SELECT interest_rate FROM economic_engine WHERE class_id = :c'))\n",
])
def test_mutation_proof__each_competing_reader_is_reported(snippet):
    assert find_violations("app/services/example.py", snippet), snippet


def test_mutation_proof__writes_prose_and_the_resolver_are_not_reported():
    write = (
        "from app.models import EconomicEngine\n"
        "db.session.add(EconomicEngine(class_id=c, economy_policy_mode='tight'))\n"
    )
    assert find_violations("app/feats/example.py", write) == []
    prose = '"""Readers never select from economic_engine directly."""\n'
    assert find_violations("app/feats/example.py", prose) == []
    read = "from app.models import EconomicEngine\nEconomicEngine.query.first()\n"
    assert find_violations(RESOLVER_MODULE, read) == []


def test_the_competing_readers_are_gone():
    """One definition of effective economic state: the readers the ruling
    removed are not reintroduced beside the resolver."""
    from app.models import ClassFeature
    from app.services import class_configuration_query_service as resolver

    for name in ("get_effective_economic_engine", "get_initial_economic_engine", "get_economic_engine_history"):
        assert not hasattr(resolver, name), name
    assert not hasattr(ClassFeature, "economic_version")
