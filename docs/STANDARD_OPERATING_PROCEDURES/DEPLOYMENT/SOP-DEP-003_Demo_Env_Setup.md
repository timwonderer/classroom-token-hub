# Public Demo Environment (Teacher + Student)

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|------------------|---------|----------------|------------|-----------------|
| SOP-DEP-003      | 1.0     | 2026-03-01     | N/A        | Normative                 |

> [!WARNING]
> Deprecated for V1 stabilization. The application routes that created and launched demo student sessions have been removed, so this SOP is retained only as historical reference and should not be used for current deployment work.

This guide describes the former demo-session flow that powered the landing page iframes and buttons in `docs/index.html`. Those route-based demo session entrypoints are no longer available in V1.

## Historical Reference
- Demo student lifecycle support code still exists in cleanup and model layers, but the route entrypoints `app/routes/api.py:create_demo_student` and `app/routes/student.py:demo_login` have been removed.
- Timeouts: `SESSION_TIMEOUT_MINUTES` (10 minutes) enforced in `app/auth.py` (`login_required`)
- Automatic cleanup: scheduler job `cleanup_expired_demo_sessions_job` in `app/scheduled_tasks.py` and logout hook in `student.logout` (documented in `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-004_Demo_Sessions.md`)
- Schema: `demo_students` table (see `docs/ARCHITECTURE/OPERATIONS/ARC-OPS-007_Database_Schema.md`)

## Prerequisites
- A separate deployment for the demo (do **not** point at production data). Follow `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-006_Deployment_Guide.md` for the base setup.
- Environment configured with production-like settings plus Turnstile keys (or leave unset to bypass during testing).
- APScheduler running so `cleanup_expired_demo_sessions_job` executes every 5 minutes (see `app/scheduled_tasks.py`).

## Steps: Stand up the demo deployment
1) **Deploy a fresh instance**  

   - Use a separate Postgres database. Run `flask db upgrade` to ensure the `demo_students` table exists.  
   - Create a system admin with `flask create-sysadmin` and log in to create a dedicated teacher (e.g., `demo_teacher`).

2) **Seed safe sample data**  

   - Option A: Upload a CSV using `student_upload_template.csv`.  
   - Option B: Run `python scripts/seed_dummy_students.py` for quick placeholder students (no real PII).  
   - Add a few store items and attendance/payroll settings via the admin UI to make the teacher dashboard feel real.

3) **Create a live demo student session (for the iframe)**  

   - Log in as the demo teacher in the demo deployment (session cookie required).  
   - Call the built-in endpoint (returns `redirect_url` like `/student/demo-login/<session_id>`):
     ```bash
     curl -X POST https://demo.classroomtokenhub.com/api/admin/create-demo-student \
       -H "Content-Type: application/json" \
       -b "session=<YOUR_ADMIN_SESSION_COOKIE>" \
       -d '{"period":1,"starting_balance":150,"pay_rate":10}'
     ```

   - Use the returned `redirect_url` for the **Student Demo** iframe/button. The session will auto-expire in 10 minutes and clean itself up (via `cleanup_demo_student_data`).

4) **Point the landing page to the demo URLs**  

   - Update `docs/index.html` demo links/iframes to the live demo host (e.g., `https://demo.classroomtokenhub.com/student/demo-login/<session_id>` for student, `https://demo.classroomtokenhub.com/admin` for teacher).  
   - The iframe sandbox is already set in `docs/index.html` (`sandbox="allow-same-origin allow-scripts allow-forms"`).

5) **Optional hardening so users cannot alter data**  

   - Run the demo against a database snapshot that refreshes nightly.  
   - Restrict the demo teacher to a dedicated tenant with dummy students only.  
   - Monitor demo cleanup in logs; if a session sticks, follow `docs/STANDARD_OPERATING_PROCEDURES/DEPLOYMENT/SOP-DEP-004_Demo_Sessions.md` to clean it manually.

## Verification checklist
- Student demo iframe loads and navigates; sessions expire after ~10 minutes and disappear from admin UI.  
- Teacher demo login works and surfaces only dummy data.  
- `cleanup_expired_demo_sessions_job` is running (check logs for “Cleaned up expired demo session”).  
- No PII from production is present in the demo database.
