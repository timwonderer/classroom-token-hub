# Timestamp Handling (General)

## Goal
Ensure timestamps display correctly across the app regardless of server or user timezone.

## Root Cause of Common Drift
- Timezone-aware datetimes stored in SQLite lose tzinfo.
- Stored values are later interpreted as local time.
- UI treats them as UTC and converts again, creating hour offsets.

## Standard Approach
1) **Store timestamps as naive UTC** in the database.
2) **Render as UTC ISO strings** with a trailing `Z` (or via `format_utc_iso`).
3) **Convert on the client** to the viewer’s local time using `timezone-utils.js`.

## Implementation Guidelines
- **Write UTC-naive values**:
  - Use `datetime.utcnow()` when setting timestamps.
- **Render UTC ISO strings**:
  - Prefer `format_utc_iso(dt)` in templates.
  - If needed, use `dt.isoformat()` and add `Z` explicitly.
- **Client conversion**:
  - Use the `.local-timestamp` class and `data-timestamp` attribute.
  - `static/js/timezone-utils.js` handles conversion on page load.
  - `format_utc_iso` is available as a Jinja global.
  - Supported `data-format` values: `date`, `time`, `compact-date`, `MMM D` (month/day short).

## Script Coverage
`static/js/timezone-utils.js` is included in base layouts:
- `templates/layout_admin.html`
- `templates/layout_student.html`
- `templates/layout_system_admin.html`
- `templates/mobile/layout_admin.html`
- `templates/mobile/layout_student.html`

## Where This Is Applied (Examples)
- Issue creation and audit timestamps:
  - `app/utils/issue_helpers.py` (`submitted_at`, `created_at`, `updated_at`, status history, resolution actions)
- Issue workflow timestamps:
  - `app/routes/admin.py` (`teacher_reviewed_at`, `teacher_resolved_at`, `closed_at`, `escalated_at`)
  - `app/routes/system_admin.py` (`sysadmin_resolved_at`)
- Consistent rendering:
  - `templates/admin_view_issue.html` uses `format_utc_iso(...)`

## Backfill Note
Records created before this standard may still be off. If needed, run a one-time backfill to shift stored values from local time to UTC.
