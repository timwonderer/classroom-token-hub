---
title: Troubleshooting
category: self-hosting
description: Real failures seen while installing a self-hosted Classroom Token Hub, what causes them and how to fix them.
roles: [operator]
keywords: [self-hosting, troubleshooting, errors, installer, Redis, certificate]
---

# Troubleshooting

Start with what you can observe. You don't have to identify the broken
software before you can begin troubleshooting.

| What you see | First check | What the result tells you |
| --- | --- | --- |
| You can't connect to the server terminal. | Check the server is running, then the SSH firewall rule in your provider dashboard. | A web-app restart won't fix a blocked SSH connection. See [SSH access](#locked-out-of-ssh-or-the-web-console-wont-connect). |
| The browser shows a Cloudflare error. | Note its number and whether you've finished `ingress`. | Before ingress, an unreachable site is expected; afterwards, the number helps separate reachability from certificate problems. See [Cloudflare errors](#cloudflare-shows-an-error-page-520526). |
| A stage stops with `stage: message`. | Record that line and your last passed stage. | Search the relevant stage notes and this page before repeating anything. |
| The sign-in page loads but login or claim fails. | Repeat the matching [Part 6 check](part-6-first-use.md) with a fictional account. | A working web connection doesn't prove account setup or provider settings work. |
| A backup command finishes without listing the saved file. | Read its error and look for a `.partial` file. | That attempt hasn't produced a completed backup. Keep previous good copies; see [Part 7.2](part-7-keep-it-running.md#72-back-up-the-database). |

**Three steps for an unfamiliar error:** record the current state, inspect the
specific failure, then make one bounded repair and repeat its check. Changing
several things at once makes it harder to know which one mattered.

## Collect useful information

Write down the chapter and step, release tag and full SHA, last successful
checkpoint, failing command, error line and whether the server holds real
classroom data. These facts help either a person or an AI agent distinguish
a settings mistake from a release defect.

For a web-app failure, run these **on the server as root**, one at a time:

```bash
systemctl status cth-web.service --no-pager
journalctl -u cth-web.service -n 30 --no-pager
curl --fail --show-error --max-time 10 http://127.0.0.1:8000/health
```

`systemctl` shows whether the app is running. The journal shows its recent
messages. The last command asks the app directly, inside the server, whether
it can reach the database. If it prints `ok` while the public page fails,
inspect HTTPS, DNS and the firewall next. If it fails, inspect the web app and
its dependencies before changing DNS. A failed `systemctl status` can return
you to the prompt with a nonzero exit code; read the displayed state.

Read the log locally. A short error description with names and keys removed
is enough to start a conversation. An agent with authorized server access can
inspect private state without copying it into chat.

Start with the **If something looks wrong** notes in the step you were on.
This page collects problems that need more explanation. Most of them were
first seen on the project's own staging servers.

Installer errors look like `stage: message`. Search this page for the message.

## Problems fixed in newer releases

These came up during the project's staging run on 22 November 2026 and were
fixed on `main`. Check that your selected release actually contains the
linked fixes; a later version number alone is not proof. The tutorial
requires those fixes. Notes below explain older failures, not a recommendation
to start a new installation on an older release.

### Redis stage fails on its first run

**Symptom.** `python3 infra/self-hosting/install.py apply redis …` prints
`redis: external command failed; inspect local service state`, yet
`systemctl status cth-rate-limit.service cth-student-setup.service` shows both
running.

**Cause.** The installer asked Redis for a response the instant the service
started, a moment before Redis was ready to answer.

**Fix.** Fixed by [#1787](https://github.com/timwonderer/classroom-token-hub/pull/1787)
(issue [#1790](https://github.com/timwonderer/classroom-token-hub/issues/1790)):
the stage now waits up to 25 seconds. On an older release, run the same
`apply redis` once more; it records the stage when both services answer.

### Release stage fails with "can't chdir"

**Symptom.** `release: external command failed; inspect local service state`.
Running the release's `gunicorn --version` as the `cthapp` account shows
`can't chdir to '/root/cth-installer'`.

**Cause.** The installer ran its commands from the folder you were in,
`/root/cth-installer`. The `cthapp` account isn't allowed into `/root`, so
programs run as `cthapp` refused to start.

**Fix.** Fixed by [#1787](https://github.com/timwonderer/classroom-token-hub/pull/1787):
installer commands now run from `/`. On an older release, upgrade to a fixed
release before installing; there's no safe workaround inside a half-finished
stage.

### Student claim returns 503

**Symptom.** Everything else works and every check passes, but a student
trying to claim an account gets an "unavailable" error (HTTP 503).

**Cause.** Ubuntu 22.04's Redis is version 6. Before the fix, CTH read three
Redis settings in one request, which only Redis 7 and newer understand.
Redis 6 refused, so the app treated the student-setup store as unavailable.

**Fix.** Fixed by [#1789](https://github.com/timwonderer/classroom-token-hub/pull/1789)
(see [#1788](https://github.com/timwonderer/classroom-token-hub/issues/1788)):
the app now reads one setting per request. Install a release that includes
it. Don't change the Redis configuration to work around it; the memory-only
safety settings must stay.

### Host stage fails with "interpreter must be root-owned and traversable"

**Symptom.** `host: interpreter must be root-owned and traversable`.

**Cause.** This only happens when the manifest has the optional `python`
field, which selects a trial interpreter. This tutorial doesn't use it. The
installer unpacked that interpreter with permissions that were too loose,
then rightly refused it.

**Fix.** Fixed by [#1787](https://github.com/timwonderer/classroom-token-hub/pull/1787).
Leave the `python` field out of your manifest.

## Problems you may still meet

### PostgreSQL package version

**Symptom.** `host: trusted APT candidate must be PostgreSQL 14.24: postgresql-14`
during `apply host`.

**Cause.** Each release expects one exact PostgreSQL 14 package version.
When Ubuntu publishes a newer one, the release's installer won't install it.

**Fix.** Nothing is wrong with your server. Check the
[Releases page](https://github.com/timwonderer/classroom-token-hub/releases)
for a newer release; if there's none, [open an issue](https://github.com/timwonderer/classroom-token-hub/issues)
quoting the message. Don't install PostgreSQL yourself to get past it.

### Host or postgres check fails after Ubuntu updates

**Symptom.** Weeks after installing, `check host` reports
`requires PostgreSQL 14.24 packages`, or `check postgres` reports
`requires PostgreSQL server 14.24`.

**Cause.** Ubuntu's automatic security updates installed a newer PostgreSQL
14. These two checks compare against the exact version the release was
installed with.

**Fix.** This version mismatch alone does not prove the app is broken or
healthy. Keep the security update; do not downgrade to satisfy the old check.
Run `check readiness`, check service logs, and repeat teacher/student sign-in.
Ask maintainers which release supports the installed package; a future fix
is not guaranteed by this guide.

### Cloudflare shows an error page (520–526)

**Symptom.** Visiting your site shows a Cloudflare error page instead of CTH.

**Cause and fix.**

- **Before Part 5 finishes:** expected. Nothing answers on port 443 until the
  `ingress` stage.
- **521 or 522** afterwards: Cloudflare can't reach the server. Check
  `systemctl status cth-ingress.service --no-pager` on the server, and that the
  firewall allows port 443 from every Cloudflare range ([Part 2, 2.4](part-2-create-the-server.md#24-turn-on-the-firewall)).
- **525 or 526:** a certificate problem. Check the certificate hasn't expired
  (`openssl x509 -in /etc/cth/tls/origin.crt -noout -enddate`), matches your
  hostname, and that the SSL/TLS mode is **Full (strict)**.

### Ingress check fails with a Cloudflare Origin CA certificate

**Symptom.** `apply ingress` fails with `runtime check failed (curl)` although
Cloudflare itself accepts the certificate.

**Cause.** The installer checks HTTPS from the server too, using Ubuntu's
trusted authorities. Ubuntu doesn't trust Cloudflare's Origin CA.

**Fix.** Use a publicly trusted certificate, such as Let's Encrypt
([Part 4, 4.4](part-4-describe-your-installation.md#44-get-the-https-certificate)).

### Locked out of SSH, or the web console won't connect

**Symptom.** SSH times out, or the provider's web console never connects.

**Cause.** Usually the firewall: your home IP address changed, or (on
DigitalOcean, as the project's rehearsal found) limiting SSH to your address
also blocked the web console.

**Fix.** Compare your current public IP with the firewall's allowed SSH
source in the provider dashboard. Correct that source and test a new SSH
connection. If you need the provider's console, check whether it uses SSH or
a separate recovery connection; the console's access rules depend on the
provider. Use its recovery instructions if neither path works. Keep a working
session open while testing a replacement connection.

### SSH warns "REMOTE HOST IDENTIFICATION HAS CHANGED"

**Cause.** Either you rebuilt the server, or something is pretending to be
it.

**Fix.** If you didn't rebuild or replace the server, **stop** and don't
connect. If you did, check the new fingerprint in the web console, then follow
[Starting over](part-5-install-stages.md#starting-over).

## Asking for help

You can use the [troubleshooting agent prompt](working-with-an-agent.md#when-something-fails)
to inspect the failure and work out a repair. It asks the agent to read the
actual release rather than guess from a generic Linux example.

If the source has a defect or the documented result cannot be reproduced,
open an issue on the [project's GitHub](https://github.com/timwonderer/classroom-token-hub/issues)
with the release tag, the stage, the exact redacted error line, what you
expected and which checks you tried. An operator shouldn't need to invent
an undocumented workaround to finish installation. Never include keys,
the runtime file, logs that contain names, backups, or your server's IP
address.
