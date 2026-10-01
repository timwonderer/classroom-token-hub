"""
Shared Flask extension instances.

Centralized to avoid circular imports. Extensions are initialized
here but configured in create_app().
"""

import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from apscheduler.schedulers.background import BackgroundScheduler
# TODO: [DEPENDABOT PR #648] Flask-Limiter 4.x introduces breaking changes:
# - 'default_limits' renamed to 'default_limits_per_method'
# - Decorator syntax may have changed for exempt routes
# - See https://flask-limiter.readthedocs.io/en/stable/changelog.html
# Review before upgrading from 3.5.0 to 4.1.1
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Initialize extensions (without binding to an app yet)
db = SQLAlchemy()
migrate = Migrate(compare_type=True)
csrf = CSRFProtect()
scheduler = BackgroundScheduler()

# Initialize rate limiter
# Uses Cloudflare-aware IP detection for accurate rate limiting
def get_real_ip_for_limiter():
    """Get real IP for rate limiting, handling Cloudflare proxy."""
    try:
        from flask import request
        # Check Cloudflare header first
        real_ip = request.headers.get('CF-Connecting-IP')
        if real_ip:
            return real_ip
        # Fallback to X-Forwarded-For
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        # Final fallback to remote_addr
        return request.remote_addr
    except RuntimeError:
        return get_remote_address()


def student_status_seat_limit_key():
    """Key the student status poll by seat, not by network address.

    Students in a school leave through a small pool of shared public
    addresses, so an address-keyed budget is spent by whoever else sits behind
    the same address. The poll is authenticated, class-scoped activity: its
    budget belongs to ``(class_id, seat_id)``.

    Reads only the ``g.canonical_context`` that ``login_required`` validated
    and attached; it never resolves context again (DOM-IDEN-006 §IX) and reads
    neither the session nor the database. It is therefore only meaningful on a
    limit decorator placed *below* ``@login_required``. Anything else falls
    back to the address key, and the key is never empty: Flask-Limiter skips a
    limit whose key is empty.
    """
    from flask import g

    context = getattr(g, "canonical_context", None)
    class_id = getattr(context, "class_id", None)
    seat_id = getattr(context, "seat_id", None)
    if class_id and seat_id:
        return f"seat:{class_id}:{seat_id}"
    return f"ip:{get_real_ip_for_limiter() or 'unknown'}"

# Use memory storage in CI/testing environments, Redis in production
# This prevents Redis connection errors in GitHub Actions
if os.environ.get('RATELIMIT_STORAGE_URI'):
    # Explicitly configured storage URI takes precedence
    storage_uri = os.environ.get('RATELIMIT_STORAGE_URI')
elif os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
    # Use memory storage in CI environments
    storage_uri = 'memory://'
elif os.environ.get('REDIS_URL'):
    # Use Redis URL if provided
    storage_uri = os.environ.get('REDIS_URL')
else:
    # Default to local Redis in production/development
    storage_uri = 'redis://localhost:6379'

limiter = Limiter(
    key_func=get_real_ip_for_limiter,
    default_limits=["500 per day", "200 per hour"],
    storage_uri=storage_uri,
    strategy="fixed-window"
)
