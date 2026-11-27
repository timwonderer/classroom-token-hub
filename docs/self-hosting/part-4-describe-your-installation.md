---
title: "Part 4: Describe your installation"
category: self-hosting
description: Write the installation manifest and runtime file, install the HTTPS certificate and check them before installing.
roles: [operator]
keywords: [self-hosting, tutorial, manifest, runtime file, keys, certificate]
---

# Part 4: Describe your installation

You are preparing three things CTH needs before it can start:

| Item | What it tells CTH | Keep in mind |
| --- | --- | --- |
| Installation manifest | “This server, this release, this web address.” | Created once for this installation. |
| Runtime file | “Use these settings and these secret keys.” | Preserve its keys when restoring data. |
| HTTPS certificate and private key | “This server can answer securely for this hostname.” | The certificate expires and needs renewal. |

You will create the first two files by copying blocks, not writing Python.
Read the replacement instructions before pasting. A block that generates keys
is for a new installation; rerunning it is not a general repair method.

In this part you write the files the installer reads. Everything goes in
`/etc/cth/`, a folder only root can open. The full meaning of every field is
in the [configuration dictionary](configuration.md); you don't need it to
follow these steps.

All commands run on **the server**, as root. In each new SSH session, run
`umask 077` and `set -o noclobber` before creating files, even if you completed
an earlier step yesterday. These shell settings do not survive a logout.

## 4.1 Set your hostname for this session

**What you're doing.** Storing your CTH hostname in a shell variable so later
commands can use it.

**Why.** Typing a hostname once avoids typos in several places.

**Steps.** Replace the value with the one in your note:

```bash
export CTH_HOSTNAME=classroom.example.org
```

**What you should see.** Nothing. `echo "$CTH_HOSTNAME"` prints your hostname.

**If something looks wrong.** Variables only last until you log out. If you
come back to this part in a new SSH session, run this line again.

## 4.2 Write the installation manifest

**What you're doing.** Creating `/etc/cth/installation.json`, which says
*which* installation this is: its ID, this server's identity, the release,
your web address, and where the other files live.

**Why.** The installer checks the manifest on every run. It refuses to run on
a different server, a different release or a changed copy of the code, so a
command can't accidentally act on the wrong installation.

**Steps.**

```bash
cd /root/cth-installer
umask 077
set -o noclobber
mkdir -m 0700 /etc/cth /etc/cth/tls
cat > /etc/cth/installation.json <<EOF
{
  "installation_id": "$(python3 -c 'import uuid; print(uuid.uuid4())')",
  "machine_id": "$(cat /etc/machine-id)",
  "release_sha": "$(git -C /root/cth-installer rev-parse HEAD)",
  "database": "cth_reference",
  "hostname": "$CTH_HOSTNAME",
  "runtime_env": "/etc/cth/runtime.env",
  "tls_cert": "/etc/cth/tls/origin.crt",
  "tls_key": "/etc/cth/tls/origin.key"
}
EOF
cat /etc/cth/installation.json
stat -c '%a %U %G' /etc/cth/installation.json
```

`umask 077` makes every new file private to root. `set -o noclobber` stops
`>` from overwriting a file that already exists.

**What you should see.**

- The manifest printed with real values: a UUID, a 32-character machine ID,
  your 40-character release SHA, and your hostname. No `<…>` or
  `example` values remain.
- `600 root root` from the last command.

**If something looks wrong.**

- **`mkdir: cannot create directory '/etc/cth': File exists`:** you've been
  here before. Look at what's in `/etc/cth` before changing anything.
- **`cannot overwrite existing file`:** the manifest already exists. If this is
  a fresh server and you haven't run any stage yet, inspect it and remove it
  with `rm /etc/cth/installation.json` before trying again. Once a stage has
  run, never change the manifest.
- **The hostname is empty:** you skipped [4.1](#41-set-your-hostname-for-this-session)
  in this session.

## 4.3 Write the runtime file

**What you're doing.** Creating `/etc/cth/runtime.env`, the private settings
CTH reads when it starts: five secret keys generated on the server, your four
provider keys, and five fixed settings.

**Why.** The keys protect sessions, encrypt student names and authenticator
secrets, and sign the audit trail. Generating them on the server means they
do not need to be pasted into the terminal. Their encrypted backup will later
travel over SSH. The provider keys are typed at hidden prompts,
so they never appear on screen or in your shell history.

**Steps.** Save the commands as a small script, then run that script. This
keeps pasted command text separate from the answers to the hidden prompts.
The script contains commands only; you'll enter the provider keys when it runs.

On the server as root, paste this whole block to **save** the script. It does
not ask for your provider keys yet. Keep the first and last lines:

```bash
cat > /root/cth-write-runtime.sh <<'CTH_RUNTIME_SCRIPT'
#!/bin/bash
set -euo pipefail
umask 077
set -o noclobber
test ! -e /etc/cth/runtime.env
read -rsp 'Turnstile site key: ' turnstile_site; echo
read -rsp 'Turnstile secret key: ' turnstile_secret; echo
read -rsp 'Passwordless public key: ' passwordless_public; echo
read -rsp 'Passwordless private secret: ' passwordless_secret; echo
hex() { python3 -c 'import secrets; print(secrets.token_hex(32))'; }
fernet() { python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())'; }
{
  printf '%s\n' "FLASK_ENV=production"
  printf '%s\n' "PASSKEY_EXPECTED_ORIGIN=https://${CTH_HOSTNAME:?run section 4.1 in this session and export CTH_HOSTNAME}"
  printf '%s\n' "DATABASE_URL=postgresql:///cth_reference?host=/var/run/postgresql&port=5432"
  printf '%s\n' "STUDENT_SETUP_REDIS_URL=unix:///run/cth-student-setup/redis.sock"
  printf '%s\n' "RATELIMIT_STORAGE_URI=redis+unix:///run/cth-rate-limit/redis.sock"
  printf '%s\n' "LOG_FILE=/var/log/cth-web/app.log"
  printf '%s\n' "SECRET_KEY=$(hex)"
  printf '%s\n' "PEPPER_KEY=$(hex)"
  printf '%s\n' "AUDIT_HMAC_KEY=$(hex)"
  printf '%s\n' "CONFIGURATION_EXPORT_KEY=$(hex)"
  printf '%s\n' "ENCRYPTION_KEY=$(fernet)"
  printf '%s\n' "TURNSTILE_SITE_KEY=$turnstile_site"
  printf '%s\n' "TURNSTILE_SECRET_KEY=$turnstile_secret"
  printf '%s\n' "PASSWORDLESS_API_PUBLIC=$passwordless_public"
  printf '%s\n' "PASSWORDLESS_API_KEY=$passwordless_secret"
} > /etc/cth/runtime.env
unset turnstile_site turnstile_secret passwordless_public passwordless_secret
stat -c '%a %U %G' /etc/cth/runtime.env
cut -d= -f1 /etc/cth/runtime.env
CTH_RUNTIME_SCRIPT
```

When the terminal prompt returns, run **this command by itself**:

```bash
bash /root/cth-write-runtime.sh
```

It asks for four keys, one at a time. Paste only the key named by the prompt,
then press Enter before entering the next one. Nothing appears while you
paste; that is deliberate. Don't paste another command while a key prompt is
waiting. The script stops if a command fails and refuses to replace an
existing runtime file.

The functions `hex()` and `fernet()` generate random keys in the formats CTH
expects. The lines starting `printf` write settings to the file; they don't
print those settings on your screen because the block redirects them into
`runtime.env`. You do not need to invent values for the generated keys.

The database name in `DATABASE_URL` must match `"database"` in the manifest.
Both use `cth_reference`.

**What you should see.** `600 root root`, then the fifteen setting names
(names only, no values):
`FLASK_ENV`, `PASSKEY_EXPECTED_ORIGIN`, `DATABASE_URL`, `STUDENT_SETUP_REDIS_URL`,
`RATELIMIT_STORAGE_URI`, `LOG_FILE`, `SECRET_KEY`, `PEPPER_KEY`,
`AUDIT_HMAC_KEY`, `CONFIGURATION_EXPORT_KEY`, `ENCRYPTION_KEY`,
`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `PASSWORDLESS_API_PUBLIC`,
`PASSWORDLESS_API_KEY`.

> [!IMPORTANT]
> This file holds the keys to your data. Without `ENCRYPTION_KEY` and
> `PEPPER_KEY`, a database backup can't be read and nobody can sign in.
> [Part 7](part-7-keep-it-running.md) backs this file up. Never paste its
> contents anywhere, and never generate new keys for an installation that
> already holds data.

**If something looks wrong.**

- **`cannot overwrite existing file`:** a runtime file already exists. If no
  stage has run yet, inspect it, then remove only the confirmed new runtime
  file and run `bash /root/cth-write-runtime.sh` again. Otherwise keep it:
  the existing keys belong to your data.
- **You pasted a wrong provider key:** edit only that line privately with
  `nano /etc/cth/runtime.env`, then run the validation in 4.5. Leave the
  generated application keys alone. You do not need to recreate the file.
- **The script file already exists:** don't paste its creation block again.
  Confirm it contains the commands above, then run the saved script by itself.
  It must still refuse to replace an existing runtime file.

## 4.4 Get the HTTPS certificate

**What you're doing.** Getting a free certificate for your CTH hostname from
Let's Encrypt, and copying it to where the installer expects it.

**Why.** Cloudflare connects to your server over HTTPS and checks its
certificate (that's what **Full (strict)** means). The installer also checks
it from the server itself, using Ubuntu's list of trusted authorities.

> [!NOTE]
> Cloudflare's own "Origin CA" certificates don't work here. Ubuntu doesn't
> trust them, so the installer's own HTTPS check fails. Use a publicly
> trusted certificate such as Let's Encrypt.

A **certificate authority**, here Let's Encrypt, issues the certificate after
you prove control of the web address. A **TXT record** is a DNS entry holding
text rather than a server address. Certbot gives you the exact text to enter;
it is asking for proof, not asking you to invent another password.

**Steps.** The server's port 80 is closed, so you prove you own the domain
with a DNS record instead. Stop after any failed command; do not copy files
until Certbot confirms issuance:

```bash
apt-get install -y certbot
certbot certonly --manual --preferred-challenges dns -d "$CTH_HOSTNAME"
```

Certbot asks for your email and agreement to its terms. Then it shows a
**TXT record** to create, named `_acme-challenge.` plus your hostname, with a
long value. **Don't press Enter yet.**

1. In Cloudflare, open your domain's **DNS → Records → Add record**.
2. **Type** `TXT`, **Name** `_acme-challenge.classroom` (with your subdomain),
   **Content** the value certbot showed. Save.
3. Wait about a minute, then press Enter in the terminal.

Then copy the certificate and key into place:

```bash
install -m 0644 "/etc/letsencrypt/live/$CTH_HOSTNAME/fullchain.pem" /etc/cth/tls/origin.crt
install -m 0600 "/etc/letsencrypt/live/$CTH_HOSTNAME/privkey.pem" /etc/cth/tls/origin.key
openssl x509 -in /etc/cth/tls/origin.crt -noout -subject -enddate
```

**What you should see.** Certbot ends with `Successfully received
certificate`. The last command prints `subject=CN = classroom.example.org`
(yours) and a `notAfter=` expiry date. Use the actual date printed, rather
than assuming a fixed certificate lifetime.

Add to your note: **certificate expiry date**. You must renew it before then
([Part 7](part-7-keep-it-running.md#76-renew-the-certificate)).

**If something looks wrong.** If certbot says the TXT record wasn't found,
wait another minute and try again. You can delete the TXT record once the
certificate is issued.

## 4.5 Check your files before installing

**What you're doing.** Running the installer's own validation on your
manifest and runtime file, without installing anything.

**Why.** It's much easier to fix a typo now than halfway through Part 5.

**Steps.**

```bash
cd /root/cth-installer
python3 -B -c 'import sys; sys.path.insert(0, "infra/self-hosting"); from pathlib import Path; import install, runtime; cfg = install.parse_manifest(Path("/etc/cth/installation.json").read_text()); runtime.parse_env(Path(cfg["runtime_env"]).read_text(), cfg); print("manifest and runtime file look valid")'
git status --porcelain --untracked-files=all
```

This uses the same checks the installer runs, and changes nothing. It never
prints a key.

**What you should see.** `manifest and runtime file look valid`, and then
nothing from `git status`.

**If something looks wrong.** A failure prints several lines ending in
`ValueError:` and a message. The message names the problem, never the value:

| Message | Fix |
| --- | --- |
| `manifest must contain exactly the documented string fields` | A field is missing, misspelt or extra. Compare with [4.2](#42-write-the-installation-manifest). |
| `invalid deployment DNS field: hostname` | The hostname is empty, uppercase, or under `classroomtokenhub.com`. |
| `missing runtime fields: …` | The listed lines are missing from the runtime file. |
| `provide registered deployment credentials for …` | That provider key is too short, a placeholder, or a published test key. |
| `keys must be independent` | Two keys have the same value, usually the same thing pasted twice. |

## Checkpoint

Continue when the validator prints **`manifest and runtime file look valid`**,
Git prints no changes, and the certificate shows your hostname and a future
expiry date. Save that date now; renewal is manual.

The validator checks the settings' format. Part 6 will check whether the
provider keys actually work in a browser. If validation fails, fix the named
field before installing. You can pause here with all three files saved.

**Agent prompt, if validation fails:**

```text
I'm at Part 4.5 of docs/self-hosting. Explain this validation error in plain
language: [paste the error line after removing private details]. Read
infra/self-hosting/install.py and runtime.py from my chosen release to find
the actual validation rule. Identify the field and give one bounded repair
and a check. Never print runtime.env, regenerate application keys, change the
release SHA or edit the installation journal to make the check pass.
```

**Next:** [Part 5: Install one stage at a time](part-5-install-stages.md)
