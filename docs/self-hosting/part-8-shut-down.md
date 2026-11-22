---
title: "Part 8: Shut it down"
category: self-hosting
description: Retire a self-hosted Classroom Token Hub, stop billing and clean up its accounts and data.
roles: [operator]
keywords: [self-hosting, tutorial, shut down, destroy, decommission, billing]
---

# Part 8: Shut it down

Use this part at the end of the school year, if you move to the hosted site,
or if you set up a test server and are done with it.

> [!CAUTION]
> Destroying the server deletes every class, account and record on it,
> permanently. Your provider can't bring it back.

## 8.1 Decide what happens to the data

**What you're doing.** Deciding, before anything is deleted, what you must
keep and what you must remove.

**Why.** Your school may require you to keep records for a time, or to
delete student data by a date. Students may want their own records first.

**Steps.**

1. Check your school's rules on keeping and deleting student data.
2. Tell teachers and students using the server when it will close, so they
   can note anything they need.
3. If you must keep the data, take a final backup ([Part 7, 7.2 and 7.3](part-7-keep-it-running.md#72-back-up-the-database))
   and test it ([7.4](part-7-keep-it-running.md#74-test-that-a-backup-restores)).
   If you must not keep it, plan to delete your backups too (step 8.4).

**What you should see.** A written decision: keep a final backup until a
date, or delete everything.

**If something looks wrong.** If you aren't sure who decides, ask before
deleting anything. Nothing in this part can be undone.

## 8.2 Close the site

**What you're doing.** Putting the whole site back behind Access.

**Why.** Nobody should be signing in or changing data while you close it.

**Steps.** Switch the Access application back to covering your whole CTH
hostname ([Part 2, 2.6](part-2-create-the-server.md#26-put-cloudflare-access-in-front-of-the-site)).

**What you should see.** A private window shows the Access page on
`/student/login` as well as `/admin/login`.

**If something looks wrong.** Check the application's destination is the
whole hostname, with no path.

## 8.3 Destroy the server

**What you're doing.** Deleting the server at your provider.

**Why.** This stops the bill. Turning the server off doesn't.

**Steps.**

1. In your provider's dashboard, find the server by name and IP address.
   Check it's the right one.
2. Destroy (delete) it. *DigitalOcean example: the Droplet's **Destroy** tab.*
3. Also delete anything you created for it: snapshots, backups at the
   provider, extra volumes, and the firewall.

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
- **Cloudflare Access:** delete the "CTH" application.
- **Turnstile:** delete the widget.
- **Passwordless.dev:** delete the application.
- **Your backups:** keep or delete them, as you decided in 8.1. If you delete
  them, also delete any copies in synced folders or cloud storage. Keep
  `cth-backup.agekey` exactly as long as you keep backups.
- **Your password manager:** archive the "CTH install" note once nothing
  depends on it.
- **The domain:** keep it, or let it expire if you bought it only for CTH.

**What you should see.** Nothing left in any dashboard that names your CTH
hostname.

**If something looks wrong.** If you can't remove something now, write down
what's left and when you'll remove it.

## That's it

You've run a server from start to finish. For the full decommissioning
checklist operators use, see the
[operations reference: decommissioning](operations.md#decommissioning).
