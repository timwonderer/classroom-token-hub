"""
Tests for security headers including Content Security Policy (CSP).
"""

def test_DOM_OPS_001__csp_header(client):
    """Verify that Content-Security-Policy header is correctly set with new directives."""
    response = client.get('/')
    assert 'Content-Security-Policy' in response.headers
    csp = response.headers['Content-Security-Policy']

    # Check for new directives by parsing CSP header
    csp_directives = {}
    for part in csp.split(';'):
        if part.strip():
            parts = part.strip().split()
            directive = parts[0]
            sources = parts[1:]
            csp_directives[directive] = sources

    # connect-src should contain cdn.jsdelivr.net
    assert 'connect-src' in csp_directives
    cdn_url = 'https://cdn.jsdelivr.net'
    assert cdn_url in csp_directives['connect-src']

    # script-src should contain static.cloudflareinsights.com
    assert 'script-src' in csp_directives
    insights_url = 'https://static.cloudflareinsights.com'
    assert insights_url in csp_directives['script-src']


def test_root_redirects_off_origin_to_the_marketing_site(client):
    """The application does not serve the marketing site.

    Two tests used to live here covering the `/gh/<path>` route: one asserting
    its CDN-font block was rewritten to the app's own stylesheet, another
    asserting the landing page's absolute sign-in links were rewritten back to
    this origin. Both rewrites existed only because the app served that markup
    under its own CSP. The route is gone, the marketing site is published to
    GitHub Pages alone, and so both rewrites and both tests went with it. What
    remains verifiable here is that `/` leaves this origin rather than falling
    through to a copy the app serves itself.
    """
    response = client.get('/')

    assert response.status_code == 302
    assert response.headers['Location'].startswith(
        client.application.config['MARKETING_SITE_URL']
    )
