# Login Page Notice

A short notice, such as upcoming maintenance, shown above the sign-in form on the
student (`/student/login`) and teacher (`/admin/login`) login pages. It needs no
deploy and no restart, and it hides itself when it expires.

## Post a notice

1. GitHub → **Actions** → **Login page notice** → **Run workflow** (branch `main`).
2. Set **action** to `post`.
3. **message**: plain-language text, up to 1000 characters. Say what is affected
   and what to do, for example: *Classroom Token Hub will be down for maintenance
   Saturday, Oct 10, 8–10 PM Pacific. Balances and purchases are not affected.*
4. **expires_at**: when the notice should disappear, as `YYYY-MM-DD HH:MM`, for
   example `2026-10-10 22:00`. Usually the end of the maintenance window.
5. **timezone**: the zone `expires_at` is written in (default `America/Los_Angeles`).

The run fails before touching production if the message is empty, the time is
malformed, or it is already in the past. Posting again replaces the current notice.

## Clear a notice early

Run the same workflow with **action** set to `clear`.

## How it works

- `.github/workflows/login-notice.yml` (production environment) connects over
  Tailscale like the release workflow and writes
  `~/classroom-economy/instance/login_notice.json` atomically:
  `{"message": "...", "expires_at": "<UTC ISO 8601>", "posted_at": "..."}`.
- `instance/` is gitignored and untouched by a release (`git reset --hard`,
  `git clean -fd docs/`), so a notice survives deploys.
- `app/utils/login_notice.py` reads the file only when a login page renders
  (`templates/macros/login_notice.html`). A missing, malformed or expired file
  shows nothing; it never breaks sign-in. `LOGIN_NOTICE_PATH` overrides the path.
- The text is rendered escaped, as plain text.
