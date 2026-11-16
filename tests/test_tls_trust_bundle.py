"""The eMudhra correction removes the affected root, retaining unaffected roots."""
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
    assert 'emSign ECC Root CA - G3' not in common_names
    assert {'emSign Root CA - G1', 'emSign Root CA - C1', 'emSign ECC Root CA - C3'} <= common_names
