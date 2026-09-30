# Security Guidelines

> **Not authoritative.** This file is operational guidance for agents. Normative authority lives only under `docs/INVARIANT/`, `docs/DOMAIN/`, `docs/FEATURE-EXECUTION/`, `docs/SPEC/`, and `docs/STANDARD_OPERATING_PROCEDURES/`. Where this file conflicts with one of those, the normative document wins and this file is what gets corrected.

**CRITICAL:** This application handles student PII and financial data. Security is paramount.

---

## The Golden Rules

1. **NEVER commit secrets, API keys, or passwords** to git
2. **ALWAYS encrypt PII** (names, email, phone, etc.)
3. **ALWAYS use CSRF protection** on forms and state-changing requests
4. **ALWAYS hash passwords** with `hash_password()` from `app.hash_utils` (scrypt, salted, unpeppered)
5. **ALWAYS validate and sanitize** user input
6. **NEVER trust client-side validation alone**
7. **ALWAYS use parameterized queries** (SQLAlchemy ORM, never raw SQL)

---

## Security Layers

### 1. Authentication

#### Password Security

**ALWAYS use the project's hash utilities:**

```python
from app.hash_utils import hash_password, verify_password

# Hashing a credential (salt generated and embedded per call)
user.passphrase_hash = hash_password(passphrase)
user.pin_hash = hash_password(pin)

# Verifying a credential — (plaintext, stored_hash) order
is_valid = verify_password(passphrase, user.passphrase_hash or '')
```

`hash_password` / `verify_password` are a **named seam**, not an algorithm. They
wrap `werkzeug.security` so call sites don't bind to a specific KDF.

**Implementation Details:**
- Werkzeug's default: **scrypt** — memory-hard, which bcrypt is not.
- The salt is random per hash and embedded in the returned string. You do not
  manage it.
- **Credentials are NOT peppered.** `PEPPER_KEY` is not an input here — see
  "Username Hashing" below for its actual scope.
- Credentials live on `users` (`passphrase_hash`, `pin_hash`), per INV-ARC-019 §VI.

> **On peppering credentials.** It has been proposed and deliberately not adopted.
> Pepper helps only under one threat model — the attacker gets the credential
> table but *not* the application environment. If they have the running app, they
> have `PEPPER_KEY` too and the benefit largely evaporates. Against that partial
> gain it makes every password depend on a second secret, so rotating
> `PEPPER_KEY` becomes a credential-invalidating event. That is an
> authentication contract, not a hardening tweak. Before adopting it, an
> authoritative identity document must define: the threat it mitigates, which
> key owns the responsibility, what rotation means, whether recovery is required
> afterward, whether old peppers may be retained, and the behavior during
> partial migration. No namespaced `DOM-IDEN-*` or `INV-*` document requires it
> today.

**NEVER:**
- ❌ Store passwords in plaintext
- ❌ Use MD5 or SHA1 for passwords
- ❌ Implement your own password hashing
- ❌ Add a pepper to `hash_password()` without the contract above being written down

#### TOTP Two-Factor Authentication

**Required for:** All admin (teacher) accounts

**Implementation:**

```python
import pyotp

from app.utils.encryption import encrypt_totp, decrypt_totp

# Generate secret for new user; only the encrypted form is stored
secret = pyotp.random_base32()
user.totp_secret_encrypted = encrypt_totp(secret)

# Verify TOTP code (as the admin and sysadmin login routes do)
totp = pyotp.TOTP(decrypt_totp(user.totp_secret_encrypted))
is_valid = totp.verify(user_provided_code, valid_window=1)
```

**Security Requirements:**
- TOTP secrets stored in `users.totp_secret_encrypted` (Fernet, `ENCRYPTION_KEY`)
- `valid_window=1`: one 30-second step either side of now
- Backup recovery mechanism (student-verified codes)

#### Session Management

Do not write session keys by hand. `app/auth.py` owns them:

```python
from app.auth import (
    establish_student_session, establish_teacher_session, establish_sysadmin_session,
)

establish_student_session(user, class_id=class_id)  # user_id, class_id, role='student'
establish_teacher_session(user)                     # user_id, role='admin'
establish_sysadmin_session(user)                    # user_id, role='sysadmin'

# Clear session on logout
session.clear()
```

The canonical keys are `user_id`, `role` (`'student'` | `'admin'` | `'sysadmin'`) and, for
students, `class_id`. Handlers read identity through `resolve_canonical_context()` /
`g.canonical_context`, never from these keys directly.

**Session lifetimes** are per role, not `permanent_session_lifetime`:
`SESSION_TIMEOUT_MINUTES = 10` (students and teachers) and
`SYSTEM_ADMIN_SESSION_TIMEOUT_MINUTES = 60` in `app/auth.py`, applied to the cookie by
`RoleScopedSessionInterface` in `app/session_lifetime.py`. `PERMANENT_SESSION_LIFETIME`
is deliberately left at Flask's default and does not bound authenticated cookies.

**Security Requirements** (set in `create_app()` in `app/__init__.py`):
- Signed-cookie sessions (`RoleScopedSessionInterface` subclasses Flask's `SecureCookieSessionInterface`); there is no server-side session store
- `SESSION_COOKIE_SECURE` is true in production
- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = 'Lax'`

---

### 2. Data Protection

#### PII Encryption

**What qualifies as PII:**
- Student first names
- Student last names/initials
- Email addresses
- Phone numbers
- Addresses
- Any other personally identifiable information

**PII encryption is a column type, not a function you call:**

```python
from app.utils.encryption import PIIEncryptedType

class IdentityProfile(db.Model):
    first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    last_name  = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
    notes      = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=True)

# Read and write normally — encryption/decryption happens in the type decorator.
profile.first_name = "Ada"
display_name = profile.first_name
```

**Implementation Details:**
- Uses Fernet symmetric encryption (AES-128-CBC + HMAC), via `cryptography`.
- Key from the `ENCRYPTION_KEY` environment variable.
- Stored as `LargeBinary`, not a string.
- **TOTP secrets share this same key** — `encrypt_totp()` / `decrypt_totp()` in
  `app/utils/encryption.py` call `_get_fernet()`, which also reads `ENCRYPTION_KEY`.
  Rotating that key therefore touches both PII columns *and* every TOTP secret.
- The `Fernet` instance is constructed **once at class-definition time**, so there is
  currently no multi-key/rotation support. See the rotation notes below.

> **There is no `encrypt_value()` or `decrypt_value()` in this repo.** That was
> another never-implemented API described by earlier revisions of this document.
> Only the three PII columns above and the TOTP helpers use `ENCRYPTION_KEY`.

**NEVER:**
- ❌ Store PII in plaintext
- ❌ Log PII in application logs
- ❌ Send PII in URLs (use POST body)
- ❌ Include PII in error messages

#### Username Hashing

**`PEPPER_KEY` keys HMAC digests only.** It is NOT involved in credential hashing. Its
users are the lookup digests below (`_lookup_digest()` in `app/hash_utils.py`), the salted
`hash_hmac()` (claim credentials, name parts), and the teacher-recovery digests in
`app/feats/teacher_recovery_feat.py`.

Usernames are never stored in plaintext. There is no `users.username` column — the
username exists only as HMAC-SHA256 digests keyed by `PEPPER_KEY`:

- `users.username_lookup_hash` — `hash_username_lookup()`. A **query key**: it must be
  reproducible from the typed username, so it is deliberately unsalted.
- `users.username_hash` — `hash_username(username, salt)`, a salted digest.

Both are produced together by `build_hashed_username_fields()` in
`app/utils/auth_username.py`:

```python
from app.hash_utils import hash_username_lookup
from app.utils.auth_username import build_hashed_username_fields

# Write (activate_student_credentials() in app/feats/identity_feat.py)
_, user.username_hash, user.username_lookup_hash = build_hashed_username_fields(username)

# Read (find_canonical_user_by_auth_username() in app/auth.py)
user = User.query.filter_by(
    username_lookup_hash=hash_username_lookup(normalized)
).first()
```

Seat claim matching uses class-scoped digests over **names**, stored on the seat per
INV-ARC-019 §VII ("Name-lookup hashes used during roster claim belong on the seat").
The class_id is part of the digest, so the same name hashes differently in every class:

```python
from app.hash_utils import hash_claim_name, hash_roster_fingerprint

# resolve_seat_claim() in app/feats/identity_feat.py
# → Seat.claim_first_name_hash / Seat.claim_last_name_hash
claim_first_hash = hash_claim_name(first_name, class_id=class_row.class_id, field="first")
claim_last_hash = hash_claim_name(last_name, class_id=class_row.class_id, field="last")
```

`hash_roster_fingerprint(class_id=..., first_name=..., last_name=...)` fills
`Seat.roster_fingerprint` the same way. Normalization (NFKC, trim, names lowercased) is
`normalize_lookup_text()`, per SPEC-SEC-001 §V.2 — do not pre-lowercase.

**Use Cases:**
- Username uniqueness and login lookup
- Roster claim matching (seat-owned: `Seat.claim_first_name_hash`, `Seat.claim_last_name_hash`, `Seat.roster_fingerprint`)

**Consequence to understand before touching `PEPPER_KEY`:** because the digest is the
only representation of the username, a new pepper cannot reproduce any existing
lookup hash. Rotation is not a transparent re-key; it needs an approved per-field
re-establishment strategy. See
`docs/STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md`
§V.2–§V.2a.

---

### 3. CSRF Protection

**REQUIRED on ALL forms and state-changing requests**

#### In Templates

```html
<form method="POST" action="/admin/create-student">
    {{ form.csrf_token }}  <!-- REQUIRED -->

    <!-- Rest of form -->
    <input type="text" name="username">
    <button type="submit">Create Student</button>
</form>
```

#### In Routes

```python
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired

class CreateStudentForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    submit = SubmitField('Create Student')

@admin_bp.route('/create-student', methods=['GET', 'POST'])
def create_student():
    form = CreateStudentForm()

    if form.validate_on_submit():  # Automatically validates CSRF
        # Process form
        username = form.username.data
        # ...

    return render_template('create_student.html', form=form)
```

#### For AJAX Requests

```javascript
// Include CSRF token in AJAX headers
fetch('/api/endpoint', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrf_token]').value
    },
    body: JSON.stringify({ data: 'value' })
})
```

**Configuration:**

```python
# In create_app() (app/__init__.py). Set only when present: a present-but-None
# WTF_CSRF_SECRET_KEY shadows the SECRET_KEY fallback and raises
# "CSRF is not configured."
csrf_secret_key = os.getenv("CSRF_SECRET_KEY", "").strip() or None
if csrf_secret_key:
    app.config["WTF_CSRF_SECRET_KEY"] = csrf_secret_key
```

**NEVER:**
- ❌ Disable CSRF protection
- ❌ Use GET requests for state-changing operations
- ❌ Skip CSRF validation

---

### 4. Input Validation

#### Server-Side Validation (REQUIRED)

```python
from wtforms.validators import DataRequired, Length, Email, ValidationError
from app.hash_utils import hash_username_lookup
from app.models import User

class StudentForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=20)
    ])

    email = StringField('Email', validators=[
        Email(message='Invalid email address')
    ])

    # Custom validator
    def validate_username(self, field):
        lookup = hash_username_lookup(field.data)
        if User.query.filter_by(username_lookup_hash=lookup).first():
            raise ValidationError('Username already exists')
```

#### Sanitization

```python
import bleach
from markupsafe import Markup

# Sanitize HTML input
def sanitize_html(unsafe_html):
    allowed_tags = ['p', 'br', 'strong', 'em']
    clean_html = bleach.clean(unsafe_html, tags=allowed_tags, strip=True)
    return Markup(clean_html)

# Escape user input in templates (Jinja2 does this automatically)
{{ user_input }}  # Auto-escaped
{{ user_input | safe }}  # ONLY if you sanitized it first
```

#### SQL Injection Prevention

**ALWAYS use SQLAlchemy ORM:**

```python
# ✅ CORRECT - Parameterized query via ORM
seat = Seat.query.filter_by(public_id=user_input, class_id=class_id).one_or_none()

# ✅ CORRECT - Parameterized query if raw SQL needed
db.session.execute(
    text("SELECT id FROM seats WHERE public_id = :public_id AND class_id = :class_id"),
    {"public_id": user_input, "class_id": class_id}
)

# ❌ NEVER DO THIS - Direct string interpolation
db.session.execute(f"SELECT id FROM seats WHERE public_id = '{user_input}'")
```

---

### 5. Authorization & Access Control

#### Role-Based Access Control

Use the decorators in `app/auth.py`; do not write new ones. Each resolves identity with
`resolve_canonical_context()`, checks `actor_role`, stores the result in
`g.canonical_context`, and enforces the role's idle timeout:

| Decorator | Role | Context | On failure |
|-----------|------|---------|------------|
| `login_required` | `student` | `CanonicalContext` (class required) | redirect to `student.login` (JSON 401 under `/api/`) |
| `admin_required` | `teacher` | `CanonicalContext`, or `BoundaryContext` on class-less endpoints only | redirect to `admin.login` (JSON 401 for background requests) |
| `system_admin_required` | `sysadmin` | `BoundaryContext` (never class context) | redirect to `sysadmin.login` |

The extinct session keys `admin_id`, `student_id` and `sysadmin_id` are read by nothing.

```python
from flask import g
from app.auth import admin_required

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    class_id = g.canonical_context.class_id  # teacher's active class
    ...
```

#### Data Access Control

```python
# ✅ CORRECT - Identity comes from canonical context, never from the request
@student_bp.route('/balance')
@login_required
def view_balance():
    ctx = resolve_canonical_context()
    checking = get_available_balance(ctx.seat_id, ctx.class_id, "checking")

    # Student can only see their own balance
    return render_template('balance.html', checking=checking)

# ❌ WRONG - User could access other users' data
@student_bp.route('/balance/<int:seat_id>')
@login_required
def view_balance(seat_id):
    # No verification that the logged-in student owns seat_id, and no class scope
    seat = db.session.get(Seat, seat_id)
    return render_template('balance.html', seat=seat)
```

---

### 6. Environment Variables & Secrets

#### Required Environment Variables

```bash
# .env file (NEVER commit this file)

# Encryption Keys
SECRET_KEY=<64-character-random-string>
ENCRYPTION_KEY=<32-byte-base64-key>
PEPPER_KEY=<random-string-for-keyed-lookup-HMACs>   # NOT used for passwords
CSRF_SECRET_KEY=<random-string-for-csrf>

# Database
DATABASE_URL=postgresql://user:password@host:port/dbname

# External Services
TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret>

```

#### Generating Secure Keys

```bash
# SECRET_KEY (64 characters)
python -c "import secrets; print(secrets.token_hex(32))"

# ENCRYPTION_KEY (32 bytes, base64)
openssl rand -base64 32

# PEPPER_KEY (random string)
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Accessing Environment Variables

```python
import os
from dotenv import load_dotenv

# Load .env file in development
load_dotenv()

# Access variables
SECRET_KEY = os.getenv('SECRET_KEY')
DATABASE_URL = os.getenv('DATABASE_URL')

# ALWAYS provide defaults for non-sensitive configs
DEBUG = os.getenv('FLASK_ENV') == 'development'
```

**NEVER:**
- ❌ Hardcode secrets in code
- ❌ Commit .env files to git
- ❌ Use the same keys for dev and production
- ❌ Share keys in chat/email

---

### 7. Rate Limiting

**Purpose:** Prevent brute force attacks and DoS

The limiter is created once in `app/extensions.py` (keyed by `get_real_ip_for_limiter`,
Redis storage from `REDIS_URL`, default `500 per day` / `200 per hour`) and disabled in
development unless `DEV_ENABLE_RATELIMIT` is set. Import it; do not construct another.

```python
from app.extensions import limiter

# e.g. app/routes/system_admin.py
@sysadmin_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    ...
```

**Best Practices:**
- Limit login attempts
- Limit password reset requests
- Limit TOTP verification attempts
- Limit API calls

---

### 8. Bot Protection

#### Cloudflare Turnstile

**On Login Forms:**

```html
<!-- In template -->
<form method="POST">
    {{ form.csrf_token }}

    <!-- Turnstile widget -->
    <div class="cf-turnstile"
         data-sitekey="{{ turnstile_site_key }}"
         data-theme="light">
    </div>

    <button type="submit">Login</button>
</form>

<!-- Include Turnstile script -->
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
```

**Server-Side Verification:** use `verify_turnstile_token()` from
`app/utils/turnstile.py`. It bypasses verification when `TURNSTILE_SECRET_KEY` is unset or
in testing, and otherwise calls the Siteverify API.

```python
from app.utils.turnstile import verify_turnstile_token
from app.utils.ip_handler import get_real_ip

turnstile_token = request.form.get('cf-turnstile-response')
if not verify_turnstile_token(turnstile_token, get_real_ip()):
    flash('Bot verification failed', 'error')
    return redirect(request.url)

# Proceed with login
```

---

## Common Security Vulnerabilities

### 1. Cross-Site Scripting (XSS)

**Prevention:**

```python
# ✅ CORRECT - Jinja2 auto-escapes by default
{{ user_input }}

# ✅ CORRECT - Explicitly escape
{{ user_input | e }}

# ⚠️ DANGER - Only use |safe if you sanitized first
{{ sanitized_html | safe }}

# ❌ NEVER - Disabling auto-escape
{% autoescape false %}
    {{ user_input }}
{% endautoescape %}
```

### 2. SQL Injection

**Prevention:**

```python
# ✅ ALWAYS use ORM
seats = Seat.query.filter_by(class_id=class_id, role=user_input).all()

# ✅ If raw SQL needed, use parameterized queries
db.session.execute(
    text("SELECT id FROM seats WHERE class_id = :class_id AND role = :role"),
    {"class_id": class_id, "role": user_input}
)

# ❌ NEVER use string formatting
db.session.execute(f"SELECT id FROM seats WHERE role = '{user_input}'")
```

### 3. Insecure Direct Object References

**Problem:** User can access other users' data by changing IDs in URLs

```python
# ❌ VULNERABLE
@student_bp.route('/profile/<int:seat_id>')
def profile(seat_id):
    seat = db.session.get(Seat, seat_id)
    return render_template('profile.html', seat=seat)

# ✅ SECURE - Seat comes from canonical context
@student_bp.route('/profile')
@login_required
def profile():
    ctx = resolve_canonical_context()
    seat = Seat.query.filter_by(id=ctx.seat_id, class_id=ctx.class_id).one()
    return render_template('profile.html', seat=seat)
```

### 4. Sensitive Data Exposure

**Prevention:**

```python
# ❌ WRONG - Logging PII (IdentityProfile names are PII)
logger.info(f"Student {profile.first_name} logged in")

# ✅ CORRECT - Log without PII
logger.info(f"Seat {seat.id} in class {class_id} logged in")

# ❌ WRONG - Including PII in error messages
flash(f"Error: User {profile.first_name} not found", 'error')

# ✅ CORRECT - Generic error message
flash("Student not found", 'error')
```

### 5. Broken Authentication

**Prevention:**

```python
# ✅ CORRECT - Secure password storage
password_hash = hash_password(password)

# ✅ CORRECT - Session timeout: per-role, enforced by the auth decorators and
# RoleScopedSessionInterface (see Session Management above); do not add another

# ✅ CORRECT - Clear session on logout
@student_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('student.login'))
```

---

## Security Checklist

### For Every Feature

- [ ] CSRF protection on all forms
- [ ] Input validation (server-side)
- [ ] Output encoding (prevent XSS)
- [ ] Authorization checks (user can access this data?)
- [ ] Rate limiting (if needed)
- [ ] PII encrypted (if storing sensitive data)
- [ ] No secrets in code
- [ ] Error messages don't reveal sensitive info

### For Authentication Features

- [ ] Credentials hashed with `hash_password()` (scrypt, salted, NOT peppered)
- [ ] TOTP 2FA implemented
- [ ] Session timeout configured
- [ ] Logout clears session
- [ ] Login attempts rate limited
- [ ] Password reset is secure

### For Database Operations

- [ ] Using SQLAlchemy ORM (not raw SQL)
- [ ] Multi-tenancy scoping enforced
- [ ] No SQL injection vulnerabilities
- [ ] Foreign key constraints in place

### For Deployment

- [ ] HTTPS enabled
- [ ] Environment variables properly set
- [ ] Database credentials secured
- [ ] Debug mode disabled
- [ ] Error logging enabled (without PII)
- [ ] Security headers configured

---

## Security Headers

**Already configured.** The `set_security_headers` `after_request` hook in
`app/__init__.py` sets HSTS, `X-Frame-Options: SAMEORIGIN`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`,
cache headers, and a `Content-Security-Policy` assembled from its `csp_directives` list.
Change headers there; do not add a second hook.

---

## Incident Response

### If a Security Issue is Discovered

1. **Assess severity** (P0 = data breach, P1 = potential exploit, P2 = hardening)
2. **Document the issue** following `SOP-SEC-001` §V.4 (incident response); external reports arrive through the private reporting route in `SECURITY.md`
3. **Create a private fix** (don't disclose publicly yet)
4. **Test the fix thoroughly**
5. **Deploy to production immediately** (if P0/P1)
6. **Notify affected users** (if data breach)
7. **Conduct post-mortem** (how to prevent in future)
8. **Update security guidelines** (this document)

---

## Quick Reference

### Encryption Functions

```python
from app.hash_utils import (
    hash_password, verify_password,
    hash_username_lookup, hash_hmac, get_random_salt,
)
from app.utils.encryption import PIIEncryptedType, encrypt_totp, decrypt_totp

# Hash a credential (scrypt via werkzeug; salt embedded, NOT peppered)
user.passphrase_hash = hash_password(passphrase)

# Verify a credential — (plaintext, stored_hash)
is_valid = verify_password(passphrase, user.passphrase_hash or '')

# Username / claim-name lookup digest (HMAC-SHA256 keyed by PEPPER_KEY, unsalted)
lookup = hash_username_lookup(username)

# Salted HMAC, where a reproducible query key is NOT needed
digest = hash_hmac(value.encode(), get_random_salt())

# PII: declare the column type; do not call an encrypt function
first_name = db.Column(PIIEncryptedType(key_env_var='ENCRYPTION_KEY'), nullable=False)
```

| Key | Protects | Rotatable in place? |
|-----|----------|---------------------|
| `SECRET_KEY` | Session cookies, CSRF tokens | Yes, via `SECRET_KEY_FALLBACKS` |
| `ENCRYPTION_KEY` | PII columns **and** TOTP secrets | Only with re-encryption; no multi-key support today |
| `PEPPER_KEY` | Keyed HMAC digests: username, claim-name, roster-fingerprint, `hash_hmac`, teacher-recovery (NOT credentials) | **No.** Needs an approved per-field re-establishment strategy (SOP-SEC-001 §V.2a) |

Passwords depend on **none** of these three — scrypt salts are self-contained.

### Decorators

```python
@admin_required         # teacher login (app/auth.py)
@login_required         # student login (app/auth.py)
@system_admin_required  # sysadmin login (app/auth.py)
@limiter.limit("10 per minute")  # rate limiting (app/extensions.py limiter)
```

---

**Last Updated:** 2026-09-28
**Security Framework:** Flask-WTF, werkzeug scrypt, Fernet, pyotp
**Bot Protection:** Cloudflare Turnstile
**Rate Limiting:** Flask-Limiter with Redis
