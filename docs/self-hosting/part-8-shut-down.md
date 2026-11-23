---
title: "Part 8: Shut it down"
category: self-hosting
description: Retire a self-hosted Classroom Token Hub, stop billing and clean up its accounts and data.
roles: [operator]
keywords: [self-hosting, tutorial, shut down, destroy, decommission, billing]
---

# Part 8: Shut it down

**Choose the outcome first:** are you retiring an empty practice server,
closing a classroom installation, or moving to a replacement? For a move, use
[Recovery](recovery.md) and verify the replacement before destroying the old
server. A classroom's last day doesn't automatically require deleting its server.

Most of this part happens in your provider's dashboard. The stop command in
8.2 happens on the server; backup commands still happen on your computer.

Use this part at the end of the school year, if you move to the hosted site,
or if you set up a test server and are done with it.

> [!CAUTION]
> Destroying the server deletes every class, account and record on it,
> from its active disk. Do not rely on provider recovery. Separate snapshots
> and backups may survive and need their own retention or deletion decision.

## 8.1 Decide what happens to the data

**What you're doing.** Deciding, before anything is deleted, what you must
keep and what you must remove.

**Why.** Your school may require you to keep records for a time, or to
delete student data by a date. Students may want their own records first.

**Steps.**

1. Check your school's rules on keeping and deleting student data.
2. Tell teachers and students using the server when it will close, so they
   can note anything they need.
3. Decide whether you'll keep a final backup (taken in step 8.2, after the
   app is stopped) or delete your backups too (step 8.4).

**What you should see.** A written decision: keep a final backup until a
date, or delete everything.

**If something looks wrong.** If you aren't sure who decides, ask before
deleting anything. Nothing in this part can be undone.

## 8.2 Stop the app and take the final backup

**What you're doing.** Stopping CTH on the server, then backing up the data
exactly as it was left.

**Why.** While the app runs, people can sign in and its scheduler keeps running
payroll and rent. A backup taken while it runs can miss the changes made after
it. Stopping the app first means the final backup holds everything.

**Steps.**

1. On the server as root, stop the web front end and the app (which includes
   the scheduler):

   ```bash
   systemctl stop cth-ingress.service cth-web.service
   systemctl is-active cth-ingress.service cth-web.service
   ```

2. If you're keeping the data, take both backups
   ([Part 7, 7.2 and 7.3](part-7-keep-it-running.md#72-back-up-the-database)).
   The database is still running, so the backup works with the app stopped.
3. Test the database backup restores ([7.4](part-7-keep-it-running.md#74-test-that-a-backup-restores))
   **before** you destroy anything.

**What you should see.** `inactive` twice from the `is-active` command, then
backups that pass the restore test.

**If something looks wrong.** If a backup or its restore test fails, don't
destroy the server. Fix the backup first; the server still has the only
complete copy of the data.

## 8.3 Destroy the server

**What you're doing.** Deleting the server at your provider.

**Why.** This stops the bill. Turning the server off doesn't.

**Steps.**

1. In your provider's dashboard, find the server by name and IP address.
   Check it's the right one.
2. Destroy (delete) it. *DigitalOcean example: the Droplet's **Destroy** tab.*
3. Reconcile snapshots, provider backups, volumes and the firewall against
   your decision in 8.1. Delete only resources dedicated to this installation
   whose retention has ended. Do not delete a shared firewall or a backup you
   deliberately retained; record any remaining storage and charges.

**What you should see.** The server no longer appears in the dashboard, and
the provider's billing page shows no running resources for it.

**If something looks wrong.** If a snapshot or volume remains, it's still
billed. Delete it, or keep it on purpose and note why.

## 8.4 Clean up everything else

**What you're doing.** Removing the accounts and records that pointed at the
server.

**Why.** Leftover keys and DNS records are a security risk, and a leftover
DNS name can later point at someone else's server.

**Steps.**

- **Cloudflare DNS:** delete the `A` record for your CTH hostname, and any
  leftover `_acme-challenge` TXT record.
- **Cloudflare Access:** if you set up maintenance mode, delete the "CTH" application.
- **Turnstile:** delete the widget.
- **Passwordless.dev:** delete the application.
- **Your backups:** keep or delete them, as you decided in 8.1. If you delete
  them, also delete any copies in synced folders or cloud storage. Keep
  `cth-backup.agekey` exactly as long as you keep backups.
- **Your password manager:** archive the "CTH install" note once nothing
  depends on it.
- **The domain:** keep it, or let it expire if you bought it only for CTH.

**What you should see.** The retired server and its dedicated integrations
are gone. Any deliberately retained domain, encrypted backup or storage item
has an owner, an expiry date and a recorded cost. You can explain every item
that remains.

**If something looks wrong.** If you can't remove something now, write down
what's left and when you'll remove it.

## Checkpoint

Record the server name and IP you retired, when you confirmed its absence,
what storage you kept and any continuing charges. Check your next provider
invoice against that note. If a resource remains unexpectedly, keep the
cleanup task open until you've accounted for it.

## That's it

You've run a server from start to finish. For the full decommissioning
checklist operators use, see the
[operations reference: decommissioning](operations.md#decommissioning).
