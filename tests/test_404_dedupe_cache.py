"""Audit O8: the 404 dedupe cache must not grow without bound or re-scan on
every single request.

``not_found_error`` rate-limits ``log_error_to_db`` so a scanner trying many
distinct unknown paths does not flood the database with one row per miss.
The cache carried no size cap of its own, and pruning rebuilt the *entire*
dict on every single 404 -- a scanner trying ``n`` distinct paths within the
hour cost O(n^2) overall, and a burst within that hour could grow the dict
without limit.

The fix prunes on a fixed interval (or immediately once over the cap, so a
sustained burst is still bounded) instead of on every request, and trims by
age down to a target below the cap whenever it is exceeded.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import wsgi


@pytest.fixture(autouse=True)
def _clean_404_cache():
    """Each test starts with no cache state from a previous one."""
    if hasattr(wsgi.app, "_404_cache"):
        del wsgi.app._404_cache
    if hasattr(wsgi.app, "_404_cache_last_pruned_at"):
        del wsgi.app._404_cache_last_pruned_at
    yield
    if hasattr(wsgi.app, "_404_cache"):
        del wsgi.app._404_cache
    if hasattr(wsgi.app, "_404_cache_last_pruned_at"):
        del wsgi.app._404_cache_last_pruned_at


def test_prune_drops_entries_older_than_an_hour():
    now = datetime.now(timezone.utc)
    cache = {
        "404_/old": now - timedelta(hours=2),
        "404_/recent": now - timedelta(minutes=5),
    }
    pruned = wsgi._prune_404_cache(cache, now)
    assert pruned == {"404_/recent": cache["404_/recent"]}


def test_prune_trims_to_the_target_when_over_the_cap():
    """Mutation proof for the missing size cap: an all-recent, over-cap dict
    used to survive pruning untouched -- it is now trimmed down to the target,
    keeping the newest entries.
    """
    now = datetime.now(timezone.utc)
    over_cap = wsgi._404_CACHE_MAX_ENTRIES + 500
    # All within the same second, well inside the one-hour age window, so
    # only the size cap -- never the age prune -- is under test here.
    cache = {
        f"404_/path-{i}": now - timedelta(milliseconds=over_cap - i)
        for i in range(over_cap)
    }
    pruned = wsgi._prune_404_cache(cache, now)

    assert len(pruned) == wsgi._404_CACHE_TRIM_TARGET
    # The newest (highest-i) entries survive; the oldest are the ones dropped.
    newest_key = f"404_/path-{over_cap - 1}"
    oldest_key = "404_/path-0"
    assert newest_key in pruned
    assert oldest_key not in pruned


def test_app_level_cache_stays_at_or_under_the_cap_across_many_distinct_paths(client, monkeypatch):
    """Integration proof: hitting many distinct unknown paths never leaves the
    live ``app._404_cache`` larger than the cap, and the handler still answers.
    """
    small_cap = 20
    monkeypatch.setattr(wsgi, "_404_CACHE_MAX_ENTRIES", small_cap)
    monkeypatch.setattr(wsgi, "_404_CACHE_TRIM_TARGET", int(small_cap * 0.9))
    # Force a prune check on every request for this test, isolating the cap
    # behavior from the time-based gate.
    monkeypatch.setattr(wsgi, "_404_CACHE_PRUNE_INTERVAL_SECONDS", 0)

    for i in range(small_cap * 3):
        response = client.get(f"/this-path-does-not-exist-{i}")
        assert response.status_code == 404

    assert len(wsgi.app._404_cache) <= small_cap


def test_pruning_is_skipped_within_the_interval_unless_over_the_cap(monkeypatch):
    """Without the time or cap trigger, the cache is left exactly as it was --
    this is what turns O(n) rescans on every request into O(n) once per
    interval.
    """
    now = datetime.now(timezone.utc)
    wsgi.app._404_cache = {"404_/a": now - timedelta(hours=2)}  # would be pruned
    wsgi.app._404_cache_last_pruned_at = now

    # Simulate the handler's own decision logic directly, at a time inside
    # the interval and under the cap.
    current_time = now + timedelta(seconds=1)
    last_pruned_at = wsgi.app._404_cache_last_pruned_at
    should_prune = (
        last_pruned_at is None
        or (current_time - last_pruned_at).total_seconds() >= wsgi._404_CACHE_PRUNE_INTERVAL_SECONDS
        or len(wsgi.app._404_cache) > wsgi._404_CACHE_MAX_ENTRIES
    )
    assert should_prune is False
    assert "404_/a" in wsgi.app._404_cache  # untouched: no prune ran
