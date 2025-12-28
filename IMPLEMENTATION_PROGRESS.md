# Issue Resolution & Escalation Infrastructure - Implementation Progress

## Overview
This document tracks the implementation of the new Issue Resolution & Escalation system for student help and support, replacing the previous simple bug reporting system with a structured, teacher-mediated issue resolution workflow.

## Completed Components

### 1. Database Models ✅
**File**: `app/models.py`

Created 4 new models:
- `IssueCategory` - Predefined categories for transaction and general issues
- `Issue` - Core issue tracking with full audit trail
- `IssueStatusHistory` - Complete status change history
- `IssueResolutionAction` - Record of all resolution actions taken

**Key Features**:
- Non-identifying opaque student references for sysadmin review
- Context snapshots capture ledger state at time of submission
- Teacher reward eligibility flag for bug escalation
- Multi-tenancy scoped by join_code
- Full audit trail with timestamps and attribution

### 2. Database Migration ✅
**Status**: Generated (user will run migration)

Migration creates all new tables with proper indexes for:
- Teacher issue querying by join_code and status
- Student issue tracking
- Opaque reference lookups for sysadmin

### 3. Utility Functions ✅
**Files**:
- `app/utils/issue_categories.py` - Default category initialization
- `app/utils/issue_helpers.py` - Issue creation and management helpers

**Functions**:
- `init_default_categories()` - Seed database with default issue categories
- `create_issue()` - Create issues with automatic context capture
- `generate_opaque_student_reference()` - Non-reversible student IDs
- `create_context_snapshot()` - Capture ledger state and transaction history
- `record_status_change()` - Audit trail for status changes
- `record_resolution_action()` - Track teacher/sysadmin actions
- `update_issue_status()` - Safe status updates with history

### 4. Forms ✅
**File**: `forms.py`

Added 2 new WTForms:
- `StudentIssueSubmissionForm` - For general (non-transaction) issues
- `TransactionIssueSubmissionForm` - For transaction-specific disputes

Both include character limits and validation per spec.

### 5. Student Routes ✅
**File**: `app/routes/student.py`

Implemented 3 routes:
- `GET /student/help-support` - Main help page with Knowledge Base and issue tracker
- `GET/POST /student/help-support/submit-issue` - Submit general issues
- `GET/POST /student/help-support/transaction/<id>/report` - Report transaction issues

**Features**:
- Automatic context snapshot capture
- Opaque reference generation
- Multi-tenancy scoping by join_code
- Character-limited text fields as per spec

### 6. Student Templates ✅
**Files**:
- `templates/student_help_support_new.html` - Main help page with 3 tabs:
  - Knowledge Base (How-To + Troubleshooting)
  - Report an Issue (General vs Transaction)
  - My Issues (Status tracking)
- `templates/student_submit_issue.html` - Issue submission form
  - Character counter for explanation field
  - Shows transaction details if applicable
  - Helpful tips for good reports

### 7. Transaction Help Icons ✅
**File**: `templates/student_dashboard.html`

Added help icons next to each transaction in Recent Activity section, linking directly to transaction issue reporting.

### 8. Teacher Routes ✅
**File**: `app/routes/admin.py`

Implemented 4 routes:
- `GET /admin/issues` - Issue review queue (pending/resolved/escalated tabs)
- `GET /admin/issues/<id>` - View issue details with full context
- `POST /admin/issues/<id>/resolve` - Resolve issues with actions:
  - Reverse transaction (voids the transaction)
  - Manual adjustment (teacher handles offline)
  - Deny issue
- `POST /admin/issues/<id>/escalate` - Escalate to sysadmin with:
  - Escalation reason (required)
  - Diagnostic notes
  - Share class name checkbox
  - **Eligible for reward checkbox** (per user requirement)

**Features**:
- Multi-tenancy scoped by join_code
- Automatic status tracking to 'teacher_review' on first view
- Full audit trail via resolution actions
- Status updates recorded in history

## Pending Components

### 9. Teacher Templates ⏳
**Files Needed**:
- `templates/admin_issues_queue.html` - Queue with pending/resolved/escalated tabs
- `templates/admin_view_issue.html` - Detailed issue view with:
  - Student explanation (read-only)
  - Full context snapshot
  - Transaction details if applicable
  - Resolution action buttons
  - Escalation form

### 10. Sysadmin Routes ⏳
**Pending Implementation**:
- `GET /sysadmin/issues` - Developer issue queue
- `GET /sysadmin/issues/<id>` - View with data minimization:
  - Opaque student reference only
  - No student names unless necessary
  - Class name only if teacher shared
- `POST /sysadmin/issues/<id>/resolve` - Developer resolution

### 11. Sysadmin Templates ⏳
**Files Needed**:
- `templates/sysadmin_issues_queue.html`
- `templates/sysadmin_view_issue.html` - With data minimization UI

### 12. Tests ⏳
**Test Coverage Needed**:
- Issue creation and context capture
- Student submission (general + transaction)
- Teacher resolution actions (reverse, manual, deny)
- Teacher escalation workflow
- Multi-tenancy scoping
- Opaque reference generation
- Status transitions
- Audit trail recording

### 13. Documentation ⏳
**Files to Update**:
- `CHANGELOG.md` - Document new issue resolution system
- `docs/user-guides/teacher_manual.md` - Add issue review section
- `docs/user-guides/student_guide.md` - Update help & support section
- `docs/technical-reference/architecture.md` - Document issue resolution flow
- `docs/security/` - Document data minimization approach

## Design Principles Implemented

✅ **No Direct Communication**: Students never contact sysadmins directly
✅ **Teacher-Mediated**: All escalations go through teachers
✅ **Evidence-Based**: Issues tied to concrete transactions/records when possible
✅ **Audit Trail**: Complete history of status changes and actions
✅ **Data Minimization**: Opaque references for sysadmin review
✅ **Character Limits**: Prevents essay-length submissions
✅ **Status Badges Only**: Students see status, not messages
✅ **Multi-Tenancy Safe**: All queries scoped by join_code
✅ **Non-Communicative**: No free-form messaging
✅ **Reward Eligibility**: Teacher flags potential bug rewards

## Next Steps

1. **Create Teacher Templates** - Priority 1
   - Implement issue queue view
   - Implement detailed issue view with resolution UI
   - Add escalation form with reward checkbox

2. **Implement Sysadmin Interface** - Priority 2
   - Create routes with data minimization
   - Create templates showing only opaque references
   - Implement resolution workflow

3. **Write Tests** - Priority 3
   - Unit tests for helpers
   - Integration tests for full workflow
   - Multi-tenancy scoping tests

4. **Update Documentation** - Priority 4
   - User-facing guides
   - Technical documentation
   - Security documentation

5. **Run Migration** - Before deployment
6. **Commit and Push** - Final step

## Database Schema Summary

```
issue_categories
├─ id (PK)
├─ name (unique)
├─ category_type (transaction/general)
└─ display_order

issues
├─ id (PK)
├─ student_id (FK → students)
├─ student_first_name (cached)
├─ student_last_initial (cached)
├─ opaque_student_reference (non-reversible)
├─ teacher_id (FK → admins)
├─ join_code (multi-tenancy)
├─ category_id (FK → issue_categories)
├─ issue_type (transaction/general)
├─ student_explanation (immutable)
├─ student_expected_outcome
├─ related_transaction_id (FK → transaction)
├─ context_snapshot (JSON)
├─ status (submitted/teacher_review/teacher_resolved/elevated/developer_review/developer_resolved)
├─ escalation_reason
├─ teacher_diagnostic_note
├─ share_class_name_with_sysadmin (bool)
├─ eligible_for_reward (bool) ← User requested feature
└─ [timestamps and resolution fields]

issue_status_history
├─ id (PK)
├─ issue_id (FK → issues)
├─ previous_status
├─ new_status
├─ changed_by_type (student/teacher/sysadmin/system)
├─ changed_by_id
└─ changed_at

issue_resolution_actions
├─ id (PK)
├─ issue_id (FK → issues)
├─ action_type (reverse_transaction/correct_amount/deny_issue/etc)
├─ performed_by_type (teacher/sysadmin)
├─ performed_by_id
├─ related_transaction_id (FK → transaction)
└─ [before/after values for audit]
```

## Issue Categories (Default)

### Transaction Categories:
1. Incorrect Amount
2. Duplicate Transaction
3. Wrong Account
4. Timing Issue
5. Incorrect Charge/Fee
6. Missing Payment

### General Categories:
1. Clock In/Out Not Working
2. Balance Incorrect
3. Feature Not Working
4. Cannot Purchase Item
5. Missing Job/Assignment
6. Other Issue

## Status Flow

```
Student Submits
    ↓
submitted → teacher_review → teacher_resolved (closed)
                ↓
            elevated → developer_review → developer_resolved → teacher notified
```

## Key Security Features

1. **Opaque References**: Sysadmins see non-reversible hashes instead of student IDs
2. **Optional Class Disclosure**: Teacher must opt-in to share class name
3. **Immutable Submissions**: Student explanation locked after submission
4. **Separate Notes**: Student, teacher, and sysadmin notes kept separate
5. **Full Audit Trail**: Every action and status change logged with attribution

---

**Last Updated**: 2025-12-28
**Implementation Status**: ~70% Complete
