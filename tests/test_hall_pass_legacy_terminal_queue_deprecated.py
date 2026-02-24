"""Deprecation tests for legacy hall pass terminal and queue surfaces."""


def test_terminal_page_is_gone(client):
    response = client.get('/hall-pass/terminal')
    assert response.status_code == 410
    data = response.get_json()
    assert data['status'] == 'error'


def test_queue_page_is_gone(client):
    response = client.get('/hall-pass/queue')
    assert response.status_code == 410
    data = response.get_json()
    assert data['status'] == 'error'


def test_terminal_lookup_endpoint_is_gone(client):
    response = client.get('/api/hall-pass/lookup/ABC123')
    assert response.status_code == 410
    data = response.get_json()
    assert data['status'] == 'error'


def test_terminal_checkout_endpoint_is_gone(client):
    response = client.post('/api/hall-pass/terminal/use', json={'pass_number': 'ABC123'})
    assert response.status_code == 410
    data = response.get_json()
    assert data['status'] == 'error'


def test_terminal_checkin_endpoint_is_gone(client):
    response = client.post('/api/hall-pass/terminal/return', json={'pass_number': 'ABC123'})
    assert response.status_code == 410
    data = response.get_json()
    assert data['status'] == 'error'


def test_queue_endpoint_is_gone(client):
    response = client.get('/api/hall-pass/queue?teacher_id=1')
    assert response.status_code == 410
    data = response.get_json()
    assert data['status'] == 'error'
