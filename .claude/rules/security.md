# Security Guidelines

**CRITICAL:** This application handles student PII and financial data. Security is paramount.

---

## The Golden Rules

1. **NEVER commit secrets, API keys, or passwords** to git
2. **ALWAYS encrypt PII** (names, email, phone, etc.)
3. **ALWAYS use CSRF protection** on forms and state-changing requests
4. **ALWAYS hash passwords** with salt AND pepper
5. **ALWAYS validate and sanitize** user input
6. **NEVER trust client-side validation alone**
7. **ALWAYS use parameterized queries** (SQLAlchemy ORM, never raw SQL)

---

## Security Layers

### 1. Authentication

#### Password Security

**ALWAYS use the project's hash utilities:**

```python
from hash_utils import hash_password, verify_password

# Hashing a password (automatically adds salt AND pepper)
password_hash = hash_password("user_password")

# Verifying a password
is_valid = verify_password("user_password", stored_hash)
```

**Implementation Details:**
- Uses bcrypt for salting
- Uses PEPPER_KEY from environment for additional security
- Minimum 12 rounds of bcrypt

**NEVER:**
- ❌ Store passwords in plaintext
- ❌ Use basic hashing without salt
- ❌ Use MD5 or SHA1 for passwords
- ❌ Implement your own password hashing

#### TOTP Two-Factor Authentication

**Required for:** All admin (teacher) accounts

**Implementation:**

```python
import pyotp

# Generate secret for new user
secret = pyotp.random_base32()
user.totp_secret = secret

# Verify TOTP code
totp = pyotp.TOTP(user.totp_secret)
is_valid = totp.verify(user_provided_code, valid_window=1)
```

**Security Requirements:**
- TOTP secrets stored in database (encrypted at rest)
- Valid window of 30 seconds
- Backup recovery mechanism (student-verified codes)

#### Session Management

```python
from flask import session

# Set session variables
session['user_id'] = user.id
session['user_type'] = 'student'  # or 'admin' or 'sysadmin'

# Always set session lifetime
session.permanent = True
app.permanent_session_lifetime = timedelta(hours=2)

# Clear session on logout
session.clear()
```

**Security Requirements:**
- Use `SESSION_TYPE = 'filesystem'` or Redis for production
- Set `SESSION_COOKIE_SECURE = True` for HTTPS
- Set `SESSION_COOKIE_HTTPONLY = True`
- Set `SESSION_COOKIE_SAMESITE = 'Lax'`

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

**ALWAYS use the project's encryption utilities:**

```python
from hash_utils import encrypt_value, decrypt_value

# Encrypting PII
encrypted_name = encrypt_value(student_first_name)
student.first_name = encrypted_name

# Decrypting PII for display
decrypted_name = decrypt_value(student.first_name)
```

**Implementation Details:**
- Uses Fernet symmetric encryption (AES-128)
- Key from ENCRYPTION_KEY environment variable
- Encrypted data stored as strings in database

**NEVER:**
- ❌ Store PII in plaintext
- ❌ Log PII in application logs
- ❌ Send PII in URLs (use POST body)
- ❌ Include PII in error messages

#### Username Hashing

**For secure username matching without revealing usernames:**

```python
from hash_utils import hash_hmac

# Create consistent username hash
username_hash = hash_hmac(username.encode(), b'')
student.username_hash = username_hash

# Lookup by hash
student = Student.query.filter_by(username_hash=username_hash).first()
```

**Use Cases:**
- Duplicate username prevention
- Join code claiming
- Student roster matching

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
# In app/__init__.py or config
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_SECRET_KEY'] = os.getenv('CSRF_SECRET_KEY')
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
        if Student.query.filter_by(username=field.data).first():
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
student = Student.query.filter_by(username=user_input).first()

# ✅ CORRECT - Parameterized query if raw SQL needed
db.session.execute(
    text("SELECT * FROM student WHERE username = :username"),
    {"username": user_input}
)

# ❌ NEVER DO THIS - Direct string interpolation
db.session.execute(f"SELECT * FROM student WHERE username = '{user_input}'")
```

---

### 5. Authorization & Access Control

#### Role-Based Access Control

```python
from flask import session, redirect, url_for
from functools import wraps

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'student_id' not in session:
            return redirect(url_for('auth.student_login'))
        return f(*args, **kwargs)
    return decorated_function

def sysadmin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'sysadmin_id' not in session:
            return redirect(url_for('system_admin.login'))
        return f(*args, **kwargs)
    return decorated_function

# Usage
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    # Only accessible to logged-in admins
    pass
```

#### Data Access Control

```python
# ✅ CORRECT - Ensure user can only access their own data
@student_bp.route('/balance')
@student_required
def view_balance():
    student_id = session.get('student_id')
    student = Student.query.get(student_id)

    # Student can only see their own balance
    return render_template('balance.html', student=student)

# ❌ WRONG - User could access other users' data
@student_bp.route('/balance/<student_id>')
@student_required
def view_balance(student_id):
    # No verification that logged-in student matches student_id
    student = Student.query.get(student_id)
    return render_template('balance.html', student=student)
```

---

### 6. Environment Variables & Secrets

#### Required Environment Variables

```bash
# .env file (NEVER commit this file)

# Encryption Keys
SECRET_KEY=<64-character-random-string>
ENCRYPTION_KEY=<32-byte-base64-key>
PEPPER_KEY=<random-string-for-password-hashing>
CSRF_SECRET_KEY=<random-string-for-csrf>

# Database
DATABASE_URL=postgresql://user:password@host:port/dbname

# External Services
TURNSTILE_SITE_KEY=<cloudflare-turnstile-site-key>
TURNSTILE_SECRET_KEY=<cloudflare-turnstile-secret>

# Optional
MAINTENANCE_MODE=false
MAINTENANCE_BYPASS_TOKEN=<random-string>
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

```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri="redis://localhost:6379"
)

# Apply to login routes
@auth_bp.route('/student/login', methods=['POST'])
@limiter.limit("5 per minute")  # Max 5 attempts per minute
def student_login():
    # Login logic
    pass

@auth_bp.route('/admin/login', methods=['POST'])
@limiter.limit("5 per minute")
def admin_login():
    # Login logic
    pass
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

**Server-Side Verification:**

```python
import requests

def verify_turnstile(token):
    """Verify Cloudflare Turnstile token."""
    secret_key = os.getenv('TURNSTILE_SECRET_KEY')

    # Skip verification if no key configured (testing)
    if not secret_key:
        return True

    response = requests.post(
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
        data={
            'secret': secret_key,
            'response': token
        }
    )

    result = response.json()
    return result.get('success', False)

# In route
@auth_bp.route('/login', methods=['POST'])
def login():
    turnstile_token = request.form.get('cf-turnstile-response')

    if not verify_turnstile(turnstile_token):
        flash('Bot verification failed', 'error')
        return redirect(url_for('auth.login'))

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
students = Student.query.filter_by(username=user_input).all()

# ✅ If raw SQL needed, use parameterized queries
db.session.execute(
    text("SELECT * FROM student WHERE username = :username"),
    {"username": user_input}
)

# ❌ NEVER use string formatting
db.session.execute(f"SELECT * FROM student WHERE username = '{user_input}'")
```

### 3. Insecure Direct Object References

**Problem:** User can access other users' data by changing IDs in URLs

```python
# ❌ VULNERABLE
@student_bp.route('/profile/<student_id>')
def profile(student_id):
    student = Student.query.get(student_id)
    return render_template('profile.html', student=student)

# ✅ SECURE - Verify ownership
@student_bp.route('/profile')
@student_required
def profile():
    student_id = session.get('student_id')
    student = Student.query.get(student_id)
    return render_template('profile.html', student=student)
```

### 4. Sensitive Data Exposure

**Prevention:**

```python
# ❌ WRONG - Logging PII
logger.info(f"Student {student.first_name} logged in")

# ✅ CORRECT - Log without PII
logger.info(f"Student ID {student.id} logged in")

# ❌ WRONG - Including PII in error messages
flash(f"Error: User {student.first_name} not found", 'error')

# ✅ CORRECT - Generic error message
flash("Student not found", 'error')
```

### 5. Broken Authentication

**Prevention:**

```python
# ✅ CORRECT - Secure password storage
password_hash = hash_password(password)

# ✅ CORRECT - Session timeout
app.permanent_session_lifetime = timedelta(hours=2)

# ✅ CORRECT - Clear session on logout
@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
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

- [ ] Passwords hashed with salt and pepper
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

**Configure in production:**

```python
@app.after_request
def set_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    return response
```

---

## Incident Response

### If a Security Issue is Discovered

1. **Assess severity** (P0 = data breach, P1 = potential exploit, P2 = hardening)
2. **Document the issue** in `docs/security/`
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
from hash_utils import encrypt_value, decrypt_value, hash_password, verify_password, hash_hmac

# Encrypt PII
encrypted = encrypt_value(plaintext)

# Decrypt PII
plaintext = decrypt_value(encrypted)

# Hash password
password_hash = hash_password(password)

# Verify password
is_valid = verify_password(password, stored_hash)

# Hash username
username_hash = hash_hmac(username.encode(), b'')
```

### Decorators

```python
@admin_required  # Requires admin login
@student_required  # Requires student login
@sysadmin_required  # Requires sysadmin login
@limiter.limit("5 per minute")  # Rate limiting
```

---

**Last Updated:** 2025-12-13
**Security Framework:** Flask-WTF, bcrypt, Fernet, pyotp
**Bot Protection:** Cloudflare Turnstile
**Rate Limiting:** Flask-Limiter with Redis
