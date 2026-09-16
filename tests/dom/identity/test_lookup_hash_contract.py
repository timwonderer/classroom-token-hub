"""Lookup purposes and class scopes must not share digest representations."""
import hashlib
import hmac

import pytest

from app import db
from app.hash_utils import (
    hash_claim_name, hash_roster_fingerprint, hash_username, hash_username_lookup,
    normalize_lookup_text,
)
from app.models import Seat
from app.feats.base import FEATContext
from app.feats.identity_feat import resolve_seat_claim
from tests.helpers.classroom_initializer import initialize_as_teacher


def test_lookup_normalization_and_separation(monkeypatch):
    monkeypatch.setenv('PEPPER_KEY', 'lookup-contract-test-key')
    assert normalize_lookup_text('  Ａda  ', kind='name') == 'ada'
    assert normalize_lookup_text('  Ａda  ', kind='username') == 'Ada'
    assert hash_username_lookup('Ada') == '21af7edc594186a60ce6854736407faee2c1cb23dfb3884334ff24d387df2a5e'
    assert hash_username_lookup(' Ada ') == hash_username_lookup('Ａda')
    assert hash_username_lookup('Ada') != hash_username_lookup('ada')
    assert hash_username_lookup('a b') != hash_username_lookup('a  b')
    name = lambda scope, field: hash_claim_name(' Ada ', class_id=scope, field=field)
    hashes = [hash_username_lookup('ada'), hash_username('ada', b'salt'),
              name('class-a', 'first'), name('class-a', 'last'), name('class-b', 'first'),
              hash_roster_fingerprint(class_id='class-a', first_name='Ada', last_name='Ada')]
    assert len(set(hashes)) == len(hashes)
    assert name('class-a', 'first') == hash_claim_name('ＡＤＡ', class_id='class-a', field='first')
    assert hash_username_lookup('ada') != hmac.new(b'lookup-contract-test-key', b'ada', hashlib.sha256).hexdigest()
    for scope in ['', None]:
        with pytest.raises(ValueError):
            hash_claim_name('Ada', class_id=scope, field='first')
    with pytest.raises(ValueError):
        hash_claim_name('Ada', class_id='class-a', field='unknown')


def test_fingerprint_has_unambiguous_fields():
    make = lambda first, last: hash_roster_fingerprint(class_id='class-a', first_name=first, last_name=last)
    assert make('a|b', 'c') != make('a', 'b|c')
    assert make('a', 'b') != hash_roster_fingerprint(class_id='class-b', first_name='a', last_name='b')
    assert make('Ａ', ' B ') == make('a', 'b')


def test_import_and_claim_share_normalization_and_reject_wrong_digest_scope(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    response = client.post('/admin/upload-students', json={'students': [
        {'first_name': 'Ａda', 'last_name': 'LoVELace'}]})
    assert response.status_code == 200
    claim = resolve_seat_claim(join_code=classroom.join_code, first_name=' ada ', last_name='LOVELACE')
    assert claim.success
    seat = db.session.get(Seat, claim.seat_id)
    with FEATContext('FEAT-TEST-SETUP', idempotency_key='lookup:wrong-scope'):
        seat.claim_first_name_hash = hash_claim_name('Ada', class_id='another-class', field='first')
    assert not resolve_seat_claim(join_code=classroom.join_code, first_name='Ada', last_name='Lovelace').success


def test_unicode_equivalent_batch_names_require_disambiguation(client, app):
    classroom = initialize_as_teacher('chemistry_p1', client, app)
    before = Seat.query.filter_by(class_id=classroom.class_id).count()
    response = client.post('/admin/upload-students', json={'students': [
        {'first_name': 'Ａda', 'last_name': 'Lovelace'},
        {'first_name': 'ada', 'last_name': 'lovelace'}]})
    assert response.status_code == 400
    assert Seat.query.filter_by(class_id=classroom.class_id).count() == before
