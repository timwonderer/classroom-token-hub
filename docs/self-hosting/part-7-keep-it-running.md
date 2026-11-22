---
title: "Part 7: Keep it running"
category: self-hosting
description: Encrypted backups with a test restore, certificate renewal, system updates, upgrades and logs for a self-hosted Classroom Token Hub.
roles: [operator]
keywords: [self-hosting, tutorial, backup, restore, age, certificate renewal, upgrade, logs]
---

# Part 7: Keep it running

Set up backups **before** real students join. A backup you've never restored
is only a hope, so this part also restores one.

The backup commands run on **your computer** in a macOS or Linux terminal. On
Windows, use [WSL](https://learn.microsoft.com/windows/wsl/install): PowerShell
can corrupt the binary data these commands pass along.

Replace `203.0.113.10` with your server's IP address throughout.

## 7.1 Make a backup key

**What you're doing.** Creating a key pair that encrypts your backups.

**Why.** Backups hold student names and every classroom record. Encrypting
them on the way to your computer means a lost laptop or a synced folder
doesn't expose them. The private half of the key never goes near the server.

**Steps.**

1. Install [age](https://github.com/FiloSottile/age#installation)
   (macOS with Homebrew: `brew install age`; Ubuntu or WSL: `sudo apt install age`).
2. Create the key:

   ```bash
   age-keygen -o ~/cth-backup.agekey
   ```

3. Save the file `~/cth-backup.agekey` in your password manager as an
   attachment, or copy it to a USB stick you keep somewhere safe.

Add to your note: the **public key** printed by `age-keygen` (it starts `age1`).

**What you should see.** `Public key: age1…`.

**If something looks wrong.** If you lose `cth-backup.agekey`, every backup made
with it is unreadable. Keep two copies in different places.

## 7.2 Back up the database

**What you're doing.** Copying the whole database from the server, encrypted,
into a file on your computer.

**Why.** The database is everything: accounts, classes, balances and history.

**Steps.** Replace `age1…` with your public key:

```bash
ssh root@203.0.113.10 'cd / && runuser -u postgres -- pg_dump --format=custom cth_reference' \
  | age -r age1… > "cth-db-$(date +%Y-%m-%d).dump.age"
ls -lh cth-db-*.dump.age
```

**What you should see.** No output from the first command, then a file of at
least several hundred kilobytes, larger as your classes grow.

**If something looks wrong.** A file of 0 bytes means the dump failed: the
error appears above `ls`. Check you used the right IP address and the database
name `cth_reference`.

## 7.3 Back up the keys and settings

**What you're doing.** Copying `/etc/cth` (the manifest, the runtime file
and the certificate) the same way.

**Why.** The database backup is useless without the keys in the runtime file.
`ENCRYPTION_KEY` decrypts student names; `PEPPER_KEY` is needed for anyone to
sign in. They exist only on the server until you copy them.

**Steps.**

```bash
ssh root@203.0.113.10 'tar -C /etc -cf - cth' \
  | age -r age1… > "cth-etc-$(date +%Y-%m-%d).tar.age"
ls -lh cth-etc-*.tar.age
```

**What you should see.** A small file, a few kilobytes.

**If something looks wrong.** As in 7.2, a 0-byte file means the command
failed; read the error above it.

> [!IMPORTANT]
> You only need a new copy of this file when something in `/etc/cth` changes,
> such as a renewed certificate. Keep at least one copy for as long as you
> keep database backups.

## 7.4 Test that a backup restores

**What you're doing.** Restoring a database backup into a throwaway database
on your computer, and checking the data is there.

**Why.** It proves your backup file and your key both work. Do this after your
first backup and every few months after.

**Steps.**

1. Install the PostgreSQL **14** tools. On macOS with Homebrew:

   ```bash
   brew install postgresql@14
   brew services start postgresql@14
   export PATH="$(brew --prefix postgresql@14)/bin:$PATH"
   ```

   On Ubuntu or WSL, install `postgresql-14` from the
   [PostgreSQL apt repository](https://www.postgresql.org/download/linux/ubuntu/).
   The version must be 14; newer tools write backups older servers reject.

2. Restore into a scratch database, check it, and delete it. Use your backup
   file's name:

   ```bash
   createdb cth_restore_test
   age -d -i ~/cth-backup.agekey cth-db-2026-11-22.dump.age \
     | pg_restore --no-owner --no-privileges --dbname=cth_restore_test
   psql -d cth_restore_test -Atc 'SELECT version_num FROM alembic_version'
   psql -d cth_restore_test -Atc 'SELECT count(*) FROM seats'
   dropdb cth_restore_test
   ```

   `--no-owner --no-privileges` is needed because your computer doesn't have
   the server's `cthowner` and `cthapp` accounts.

3. Check the key backup opens too:

   ```bash
   age -d -i ~/cth-backup.agekey cth-etc-2026-11-22.tar.age | tar -tf -
   ```

**What you should see.** A revision ID (12 letters and digits), a count of
seats (your test student and teacher, at least 2), and a file list including
`cth/runtime.env` and `cth/installation.json`.

**If something looks wrong.**

- **`no identity matched any of the recipients`:** the backup was encrypted to
  a different public key than the private key you used.
- **Errors about roles:** you left out `--no-owner --no-privileges`.
- **`unsupported version` from `pg_restore`:** your tools aren't version 14.

This proves your backups can be read. Restoring onto a **new server** after a
disaster isn't a rehearsed tutorial path yet. The
[operations reference](operations.md#backups-restoration-and-deletion) covers
it, and it's advanced. If you ever need it, take your time and ask for help
before touching the old server.

## 7.5 Make backups a habit

**What you're doing.** Deciding when to back up and how long to keep copies.

**Why.** A backup only helps if it's recent.

**Steps.**

- Run [7.2](#72-back-up-the-database) at least **once a week** during the school
  year, and always **before** any change to the server.
- Run [7.3](#73-back-up-the-keys-and-settings) after anything in `/etc/cth` changes.
- Keep a few weeks of database backups and delete older ones. When a student or
  class is deleted from CTH, older backups still contain them. Follow your
  school's rules on how long to keep student data.
- Repeat [7.4](#74-test-that-a-backup-restores) every few months.

**What you should see.** A folder of dated, encrypted files.

**If something looks wrong.** If you miss a week, just run a backup now.

## 7.6 Renew the certificate

**What you're doing.** Getting a new certificate before the old one expires,
and putting it in place.

**Why.** When the certificate expires, Cloudflare refuses to connect to your
server and your site goes down. A manually issued Let's Encrypt certificate
doesn't renew itself.

**Steps.** About two weeks before the expiry date in your note, on the server
as root:

```bash
CTH_HOSTNAME=classroom.example.org
certbot certonly --manual --preferred-challenges dns -d "$CTH_HOSTNAME"
```

Choose to renew when asked, and create the new TXT record exactly as in
[Part 4, step 4.4](part-4-describe-your-installation.md#44-get-the-https-certificate).
Then:

```bash
install -m 0644 "/etc/letsencrypt/live/$CTH_HOSTNAME/fullchain.pem" /etc/cth/tls/origin.crt
install -m 0600 "/etc/letsencrypt/live/$CTH_HOSTNAME/privkey.pem" /etc/cth/tls/origin.key
systemctl restart cth-ingress.service
cd /root/cth-installer
python3 infra/self-hosting/install.py check ingress --config /etc/cth/installation.json
openssl x509 -in /etc/cth/tls/origin.crt -noout -enddate
```

Update the expiry date in your note, and back up `/etc/cth` again ([7.3](#73-back-up-the-keys-and-settings)).

> [!NOTE]
> The project hasn't rehearsed this renewal on a reference server yet. If the
> `check ingress` line doesn't end in `"result": "ok"`, see
> [Troubleshooting](troubleshooting.md).

**What you should see.** `"stage": "ingress"` … `"result": "ok"`, and a
`notAfter=` date about three months away.

**If something looks wrong.** If `cth-ingress` won't start, run
`journalctl -u cth-ingress.service -n 30 --no-pager`. The usual causes are
swapped certificate and key files or a wrong file mode.

## 7.7 Ubuntu updates and reboots

**What you're doing.** Keeping the operating system patched.

**Why.** Security fixes for Ubuntu, PostgreSQL, Redis and nginx come through
Ubuntu's updates.

**Steps.**

- Ubuntu installs security updates automatically by default. Leave that on.
- Some updates need a reboot. If the file `/var/run/reboot-required` exists,
  back up ([7.2](#72-back-up-the-database)), then run `reboot` at a quiet time.
- After any reboot, log in and run `check readiness` as in
  [Part 6, step 6.7](part-6-first-use.md#67-check-health-from-the-server).

**What you should see.** `"result": "ok"` after the reboot. All CTH services
start on their own.

**If something looks wrong.** See [Troubleshooting](troubleshooting.md#host-or-postgres-check-fails-after-ubuntu-updates).

## 7.8 Upgrading CTH and rolling back

**What you're doing.** Planning how you'll move to a newer CTH release.

**Why.** New releases fix bugs and security problems.

**Read this first.** The installer **installs one release on a new server**.
It doesn't upgrade an existing installation yet. Upgrading means moving
a new release into place beside the old one, updating the database, and
switching the service over, by hand. Those steps are in the
[operations reference: upgrades and runtime rollback](operations.md#upgrades-and-runtime-rollback).
They're written for experienced operators.

**Steps, for now.**

1. Watch the [Releases page](https://github.com/timwonderer/classroom-token-hub/releases).
   (On GitHub, **Watch → Custom → Releases** emails you.)
2. Read each release's notes. Most releases don't need urgent action on a
   private server; a security fix might.
3. Before any upgrade, take both backups ([7.2](#72-back-up-the-database),
   [7.3](#73-back-up-the-keys-and-settings)) and switch the Access application
   back to covering the whole site ([Part 2, 2.6](part-2-create-the-server.md#26-put-cloudflare-access-in-front-of-the-site)),
   so nobody uses the site mid-change.
4. **Rolling back** is the same procedure in reverse, and depends on whether
   the database changed. It's in the same reference section. Never "roll back"
   by restoring an old backup over a live database without reading it first:
   you'd lose everything since that backup.

**If something looks wrong.** Keep the Access gate closed, and don't try
fixes you don't understand. Ask for help with the release tag and the exact
error message, but never paste keys, logs with names, or backups.

## 7.9 Reading logs

**What you're doing.** Finding out what a service is doing or why it failed.

**Why.** Logs are the first place to look when something's wrong.

**Steps.** On the server as root:

| To see | Run |
| --- | --- |
| Whether every CTH service is running | `systemctl status cth-web.service cth-ingress.service cth-rate-limit.service cth-student-setup.service --no-pager` |
| The web app's recent messages | `journalctl -u cth-web.service -n 50 --no-pager` |
| The app's own log file | `tail -n 50 /var/log/cth-web/app.log` |
| The HTTPS front end | `journalctl -u cth-ingress.service -n 50 --no-pager` |
| Messages since the last boot | add `-b` to a `journalctl` command |

**What you should see.** `active (running)` for each service, and recent log
lines with timestamps.

**If something looks wrong.** Logs can contain student names and other
private details. Read them on the server; if you share an excerpt to get
help, remove names, usernames, IP addresses and anything that looks like a key
first.

**Next:** [Part 8: Shut it down](part-8-shut-down.md), for when you're finished.
