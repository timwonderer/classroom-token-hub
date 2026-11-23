"""Non-overlapping response totals, honest coverage and UTC boundaries."""
from copy import deepcopy
from datetime import timedelta

import pytest

from status_service.request_errors import error_summary
from tests.test_status_store import NOW, database, sample
from tests.test_status_page import page


def errors(at=NOW, four=3, five=1):
    result = sample(at)
    result['components'][0].update(http_2xx_count=20-four-five, http_4xx_count=four,
                                   http_5xx_count=five)
    return result


def test_overlapping_minutes_and_retries_do_not_multiply_counts(database):
    store, data = database
    for minute in range(6):
        at = NOW + timedelta(minutes=minute)
        store.append_snapshot(errors(at), at)
        store.append_snapshot(errors(at), at + timedelta(seconds=10))
    totals = data['telemetry_days'][NOW.date().isoformat()]['request_errors']
    assert (totals['windows'], totals['requests'], totals['4xx'], totals['5xx']) == (2, 40, 6, 2)
    assert totals['last_4xx'] == (NOW + timedelta(minutes=5)).isoformat()


def test_older_delivery_cannot_rewind_last_error(database):
    store, data = database
    later = NOW + timedelta(minutes=5)
    store.append_snapshot(errors(later), later)
    store.append_snapshot(errors(), later)
    totals = data['telemetry_days'][NOW.date().isoformat()]['request_errors']
    assert totals['windows'] == 2
    assert totals['last_5xx'] == later.isoformat()


def test_midnight_window_belongs_to_previous_day_and_has_30_day_ttl(database):
    store, data = database
    midnight = NOW.replace(hour=0)
    store.append_snapshot(errors(midnight), midnight)
    day = data['telemetry_days']['2026-09-20']
    assert day['request_errors']['last_4xx'] == midnight.isoformat()
    assert day['expires_at'] == midnight + timedelta(days=29)
    result = error_summary(store.error_history(now=midnight))
    assert result['observed'] == 1 and result['total'] == 4
    assert result['scheduled'] == 29 * 288


@pytest.mark.parametrize('kind', ['missing', 'stale', 'unavailable', 'unaligned'])
def test_unusable_or_unaligned_sample_does_not_fabricate_totals(database, kind):
    store, data = database
    value = errors()
    if kind == 'missing': value['source_latest_at'] = None
    if kind == 'stale': value['source_latest_at'] = (NOW - timedelta(minutes=4)).isoformat()
    if kind == 'unavailable':
        from status.measurements import unavailable_component
        value['components'][0] = unavailable_component('service')
    if kind == 'unaligned': value['sampled_at'] = (NOW + timedelta(seconds=1)).isoformat()
    store.append_snapshot(value, NOW + timedelta(seconds=2))
    assert 'telemetry_days' not in data
    assert len(data['telemetry_snapshots']) == 1


def test_history_dates_exclude_older_days_and_legacy_percentages(database):
    store, data = database
    data['telemetry_days'] = {NOW.date().isoformat(): {'components': {'service': {'normal': 100, 'measured': 100}}}}
    history = store.error_history(now=NOW)
    assert history[0]['date'] == (NOW - timedelta(days=29)).date().isoformat()
    assert history[-1]['date'] == NOW.date().isoformat()
    assert len(history) == 30
    result = error_summary(history)
    assert result['observed'] == 0 and result['gap_days'] == 30


def test_zero_error_observation_is_distinct_from_missing_coverage(database):
    store, _ = database
    store.append_snapshot(sample(count=0), NOW)
    result = error_summary(store.error_history(now=NOW))
    assert result['observed'] == 1 and result['total'] == result['requests'] == 0
    assert result['coverage'] > 0 and result['gap_days'] == 30
    assert all(category['last'] is None for category in result['categories'])


@pytest.mark.parametrize('field,value', [('windows', True), ('4xx', -1), ('5xx', 999),
    ('last_4xx', None), ('last_4xx', '2027-01-01T00:00:00Z'), ('windows', 289)])
def test_corrupt_rollups_are_unavailable(database, field, value):
    store, data = database
    store.append_snapshot(errors(), NOW)
    data['telemetry_days'][NOW.date().isoformat()]['request_errors'][field] = value
    assert error_summary(store.error_history(now=NOW))['observed'] == 0


def test_public_chart_counts_and_window_timestamp_have_text_equivalents(page):
    client, store, _ = page
    store.error_history = lambda **kwargs: [{'date': NOW.date().isoformat(), 'scheduled_windows': 144,
        'errors': {'windows': 1, 'requests': 20, '4xx': 3, '5xx': 1,
                   'last_4xx': NOW.isoformat(), 'last_5xx': NOW.isoformat()}}]
    html = client.get('/').get_data(as_text=True)
    assert '4xx — Request errors' in html and '5xx — Server errors' in html
    assert '<strong>3</strong>' in html and '<strong>1</strong>' in html
    assert 'stroke-dasharray="75.0 100"' in html
    assert 'Last recorded in the five-minute window ending' in html
    assert '20 requests observed' in html and '1 of 144' in html
    assert 'not reliability' in html and 'do not establish fault' in html
    assert '90-day' not in html and 'no problems measured' not in html
    assert 'aria-hidden="true" focusable="false"' in html


@pytest.mark.parametrize('corruption', ['missing_count', 'bad_time', 'null', 'list', 'empty'])
def test_corrupt_history_never_blocks_source_or_current_ingestion(database, corruption):
    store, data = database
    store.append_snapshot(errors(), NOW)
    day = data['telemetry_days'][NOW.date().isoformat()]
    if corruption == 'missing_count': del day['request_errors']['requests']
    elif corruption == 'bad_time': day['request_errors']['last_4xx'] = 'not-a-time'
    elif corruption == 'null': day['request_errors'] = None
    elif corruption == 'list': day['request_errors'] = []
    elif corruption == 'empty': day['request_errors'] = {}
    original = deepcopy(day)
    for minute in (5, 10):
        at = NOW + timedelta(minutes=minute)
        value = errors(at)
        store.append_snapshot(value, at)
        store.append_snapshot(value, at + timedelta(seconds=10))
        assert store.current_snapshot()['snapshot'] == value
        assert store.current_snapshot()['last_activity']['service']['sampled_at'] == at.isoformat()
        assert data['telemetry_days'][NOW.date().isoformat()] == original
        assert error_summary(store.error_history(now=at))['observed'] == 0
    assert len(data['telemetry_snapshots']) == 3
