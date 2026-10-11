"""
Cloudflare Turnstile verification utility.

This module provides server-side verification for Cloudflare Turnstile tokens.
"""

import urllib.request
import urllib.parse
import json
from flask import current_app


def verify_turnstile_token(token, remote_ip=None):
    """
    Verify a Cloudflare Turnstile token with the Siteverify API.

    Args:
        token (str): The Turnstile token from the client (cf-turnstile-response)
        remote_ip (str, optional): The user's IP address for additional verification

    Returns:
        bool: True if the token is valid, False otherwise

    Notes:
        - Tokens expire after 5 minutes (300 seconds)
        - Each token can only be validated once
        - Server-side validation is mandatory for security in production
        - Bypasses verification in testing environments
        - Bypasses verification when TURNSTILE_SECRET_KEY is not configured
          and ENV is exactly 'development' (local development without a
          registered key)
        - Any other ENV with no TURNSTILE_SECRET_KEY configured — including
          production and any other value such as 'staging' — fails closed
          (returns False); production startup also refuses to run without it
    """
    secret_key = current_app.config.get('TURNSTILE_SECRET_KEY')

    # Bypass verification in testing environments
    if current_app.config.get('TESTING') or current_app.config.get('ENV') == 'testing':
        current_app.logger.info("Turnstile verification bypassed: Testing environment")
        return True

    if not secret_key:
        # FLASK_ENV is a free-form string with no enum validation (see
        # create_app()), so "fail closed unless ENV != production" would
        # silently bypass the bot check on any other externally-reachable
        # value someone deploys with — 'staging' included — not only on
        # actual local development (CodeRabbit review on PR #1536). The
        # bypass is now an explicit allow-list of exactly 'development';
        # production is already covered above by the startup gate, but
        # checking it again here costs nothing and documents the intent.
        if current_app.config.get('ENV') == 'development':
            current_app.logger.info("Turnstile verification bypassed: TURNSTILE_SECRET_KEY not configured")
            return True
        current_app.logger.error(
            "Turnstile verification failed closed: TURNSTILE_SECRET_KEY is not configured"
        )
        return False

    if not token:
        current_app.logger.warning("Turnstile verification failed: No token provided")
        return False

    # Cloudflare Turnstile siteverify endpoint
    url = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'

    # Prepare the request data
    data = {
        'secret': secret_key,
        'response': token,
    }

    # Add remote IP if provided (optional but recommended)
    if remote_ip:
        data['remoteip'] = remote_ip

    try:
        # Encode the data
        encoded_data = urllib.parse.urlencode(data).encode('utf-8')

        # Make the request
        req = urllib.request.Request(url, data=encoded_data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')

        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))

        # Check if verification was successful
        if result.get('success'):
            current_app.logger.info(f"Turnstile verification successful: {result}")
            return True
        else:
            error_codes = result.get('error-codes', [])
            current_app.logger.warning(f"Turnstile verification failed: {error_codes}")
            return False

    except urllib.error.URLError as e:
        current_app.logger.error(f"Turnstile verification network error: {e}")
        return False
    except json.JSONDecodeError as e:
        current_app.logger.error(f"Turnstile verification JSON decode error: {e}")
        return False
    except Exception as e:
        current_app.logger.error(f"Turnstile verification unexpected error: {e}")
        return False
