"""Requests uses the corrected certifi bundle after the eMudhra removals."""
import ssl

import certifi
import requests


def test_requests_trust_bundle_excludes_compromised_emsign_root():
    context = ssl.create_default_context(cafile=requests.certs.where())
    common_names = {
        value
        for certificate in context.get_ca_certs()
        for rdn in certificate['subject']
        for key, value in rdn
        if key == 'commonName'
    }
    assert requests.certs.where() == certifi.where()
    # certifi 2026.10.23 also removes C1/C3, following NSS 3.131.1:
    # https://firefox-source-docs.mozilla.org/security/nss/releases/nss_3_131_1.html
    removed_roots = {
        'emSign ECC Root CA - G3',
        'emSign Root CA - C1',
        'emSign ECC Root CA - C3',
    }
    assert common_names.isdisjoint(removed_roots)
    assert 'emSign Root CA - G1' in common_names
