---
title: Troubleshooting
category: self-hosting
description: Real failures seen while installing a self-hosted Classroom Token Hub, what causes them and how to fix them.
roles: [operator]
keywords: [self-hosting, troubleshooting, errors, installer, Redis, certificate]
---

# Troubleshooting

Start with the **If something looks wrong** notes in the step you were on.
This page collects problems that need more explanation. Most of them were
first seen on the project's own staging servers.

Installer errors look like `stage: message`. Search this page for the message.

## Problems fixed in newer releases

These came up during the project's staging run on 22 November 2026 and were
fixed on `main` that day. A release published after v2.4.5 includes the fixes.
If you install such a release, you won't see them. On an older release, use
the workaround.

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

**Fix.** Your site keeps working: `check readiness` doesn't check package
versions. Keep the security update; don't downgrade PostgreSQL. A newer CTH
release will expect the newer version.

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

**Fix.** Edit the firewall's SSH rule in your provider's dashboard. Your
provider's recovery console works even when SSH doesn't.

### SSH warns "REMOTE HOST IDENTIFICATION HAS CHANGED"

**Cause.** Either you rebuilt the server, or something is pretending to be
it.

**Fix.** If you didn't rebuild or replace the server, **stop** and don't
connect. If you did, check the new fingerprint in the web console, then follow
[Starting over](part-5-install-stages.md#starting-over).

## Asking for help

Open an issue on the [project's GitHub](https://github.com/timwonderer/classroom-token-hub/issues)
with the release tag, the stage, and the exact error line. Never include keys,
the runtime file, logs that contain names, backups, or your server's IP
address.
