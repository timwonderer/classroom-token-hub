# CTH Feature Specification
## OBSERVER ACCOUNT SYSTEM

Status: Proposed  
Scope: Hall Pass System Only  
Version: v1.1

---

# I. Purpose

The Observer Account system allows school administrators or authorized staff to temporarily view hall pass activity across participating classrooms.

Observer accounts provide read-only access to hall pass logs for the current day, subject to teacher authorization.

Observer accounts cannot access any classroom economy features, including balances, payroll, store transactions, or ledger records.

The feature is designed to support building-level hallway monitoring without compromising classroom autonomy or financial privacy.

---

# II. Core Design Principles

### 1. Classroom Sovereignty

Each classroom (join code universe) is governed by the teacher.

Observers cannot access classroom data without explicit teacher authorization.

### 2. Operational Scope Only

Observers may only access real-world operational data:

Allowed:
- Active hall passes
- Today's hall pass log

Disallowed:
- Student balances
- Payroll
- Store purchases
- Ledger history
- Insurance
- Rent

Observers have no visibility into the classroom economy system.

### 3. Temporary Access

All observer permissions are ephemeral.

Authorization duration: 7 days  
Request validity: 7 days  
Observer account inactivity deletion: 6 months

No observer access persists indefinitely.

### 4. Teacher-Controlled Authorization

Observer access must be approved by the teacher associated with the class.

Teachers may:
- approve requests
- deny requests
- revoke active authorization

---

# III. Observer Identity Model

Observer accounts are low-durability identities.

The system does not collect or verify:
- real names
- institutional roles
- school affiliations

Observers self-identify using a display name.

Example:

Assistant Principal Rivera
Dean of Students
Security Office

The system relies on teacher recognition for authorization decisions.

---

# IV. Observer Account Creation

Observers register using an invite code.

Authentication method:

username → TOTP

Observers authenticate using a Time-based One-Time Password system rather than a traditional password.

Required:

- invite code
- username
- TOTP setup
- display name

Observer accounts contain no classroom ownership privileges.

---

# V. Authorization Workflow

### Step 1 — Request Submission

Observer submits:

- teacher_public_id
- join_code
- observer_display_name
- optional observer label for internal use

This creates a pending observer request.

### Step 2 — Teacher Notification

Teacher receives in-app notification.

Example message:

Observer: Assistant Principal Rivera  
Requesting access to Hall Pass Log (today only)  
Duration: 7 days

Teacher options:

- Approve
- Deny

### Step 3 — Authorization Grant

If approved:

Authorization begins immediately and expires after 7 days.

### Step 4 — Expiration

After 7 days the authorization automatically expires.

Observer must submit a new request to regain access.

---

# VI. Observer Watchlist

Observers maintain a local watchlist of previously requested classes.

Stored data includes:

- teacher_public_id
- join_code
- observer_label
- last_requested_at
- last_authorized_at
- authorization_expiry

Observers may:

- rename labels
- re-request authorization

Watchlist entries remain reusable for 30 days after the last request.

After 30 days the observer must re-enter the teacher ID and join code.

---

# VII. Observer Hall Pass Access

Observers may view:

### Active Hall Passes

Students currently outside class.

Displayed fields:

- student display name
- destination
- time issued
- issuing teacher

### Today's Hall Pass Log

All hall passes issued during the current day.

Server-side query restriction enforces same-day access.

Observers cannot query historical hall pass data.

---

# VIII. Teacher Control Panel

Teachers may view current observer access.

Example UI:

Observers with Access

Assistant Principal Rivera — expires in 5 days

Dean Thompson — expires in 2 days

Teachers may revoke access at any time.

Revocation immediately removes observer permissions.

---

# IX. Security Model

Observer accounts are designed to minimize system risk.

If compromised, an observer account can only:

- view hall pass logs
- view active passes

Observers cannot:

- modify data
- access economic systems
- view historical records

Authorization is constrained by:

- teacher approval
- 7 day expiration
- class scope

---

# X. Account Recovery

Observer accounts do not support recovery.

If credentials are lost:

1. Create a new observer account
2. Request authorization again

Observer accounts store no critical system state.

---

# XI. Account Expiration

Observer accounts are automatically deleted after 6 months of inactivity.

Activity includes:

- login
- authorization request
- hall pass viewing

Expired accounts are removed via scheduled cleanup job.

---

# XII. Data Retention

Observer-related records are temporary.

Expired records may be removed including:

- pending requests older than 7 days
- expired authorizations
- stale watchlist entries

The system minimizes long-term storage of observer-related data.

---

# XIII. Non-Goals

Observer accounts will never provide access to:

- classroom economy features
- financial records
- student balances
- administrative overrides

CTH is not intended to become district administrative software.

Observer accounts exist only to support hallway monitoring.

