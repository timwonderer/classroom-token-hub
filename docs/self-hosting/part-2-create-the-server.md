---
title: "Part 2: Create and secure the server"
category: self-hosting
description: Create an Ubuntu 22.04 server, connect to it safely, restrict its firewall and point your domain at it.
roles: [operator]
keywords: [self-hosting, tutorial, server, SSH, firewall, DNS]
---

# Part 2: Create and secure the server

From this part on, **billing has started**. If you stop for more than a few
days, read [Part 8](part-8-shut-down.md) first.

The steps show DigitalOcean's screens as a labelled example. Every provider
has the same pieces under slightly different names.

## 2.1 Create the server

**What you're doing.** Renting a new, empty Ubuntu server.

**Why.** The installer only works on a fresh Ubuntu 22.04 x86-64 server, and
it refuses a machine that already runs a database, web server or Redis.

**Steps.**

1. Create a new server with:
   - **Image:** Ubuntu **22.04** LTS, x86-64. Not 24.04, and not an ARM server.
   - **Size:** the tested size is 2 vCPUs, 4 GB memory, 80 GB disk. Smaller
     sizes are untested.
   - **Region:** one near you and your students.
   - **Authentication:** your SSH **public key**, not a password.
2. Don't add the provider's one-click apps, managed databases or extra
   volumes. CTH installs everything it needs itself.

> **Example (DigitalOcean).** **Create → Droplets**, choose a region, **Ubuntu
> 22.04 (LTS) x64**, a Basic plan with 2 vCPUs and 4 GB, and under
> **Authentication** choose **SSH Key** and select yours.

Add to your note: **server IP address** (the IPv4 address the dashboard shows).

**What you should see.** The server is listed as running, with an IPv4 address.

**If something looks wrong.** If Ubuntu 22.04 isn't offered, choose another
region or provider. The installer won't accept any other version.

## 2.2 Read the server's fingerprint in the web console

**What you're doing.** Finding out the server's true identity through a
channel an attacker can't fake: your provider's own website.

**Why.** The first time you SSH in, your computer can't tell your server from
an impostor. Comparing fingerprints settles that.

**Steps.**

1. Open the server's **web console** from your provider's dashboard
   (DigitalOcean: **Access → Launch Droplet Console**).
2. Run:

   ```bash
   ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
   ```

Add to your note: the fingerprint, the part starting `SHA256:`.

**What you should see.** One line like
`256 SHA256:Xb3f…Q7k root@your-server (ED25519)`.

**If something looks wrong.** The web console can take a minute to connect
after the server is created. If it never connects, use your provider's
recovery console, or contact their support.

## 2.3 Connect with SSH for the first time

**What you're doing.** Logging in from your own terminal.

**Why.** Every later step runs in an SSH session.

**Steps.** On **your computer**, replace the address with your server's:

```bash
ssh root@203.0.113.10
```

SSH asks whether to trust the server and shows an `ED25519 key fingerprint
is SHA256:…` line. **Compare it, character by character, with the fingerprint
in your note.** Type `yes` only if they're identical.

Some providers don't allow `root` to log in directly and give you a user such
as `ubuntu` instead. In that case run `ssh ubuntu@203.0.113.10`, then
`sudo -i` to become root.

**What you should see.** A prompt ending in `#`, such as `root@your-server:~#`.
The `#` means you are root.

**If something looks wrong.**

- **Fingerprints differ:** type `no`. Don't continue. Check you used the right
  IP address. If it still differs, destroy the server and create a new one.
- **`Permission denied (publickey)`:** the server doesn't have your public
  key, or your terminal isn't offering it. Check the key you chose in 2.1.
- **Asked for a passphrase:** that's your SSH key's own passphrase, not a
  server password. Type it at the prompt.

## 2.4 Turn on the firewall

**What you're doing.** Allowing only two kinds of incoming traffic: SSH from
you, and HTTPS from Cloudflare.

**Why.** Nothing else should be able to reach the server. The installer also
configures the web server to answer only Cloudflare, and the firewall
enforces the same rule a layer earlier.

**Steps.** Create a firewall at your provider with these **inbound** rules,
and attach it to the server:

| Type | Port | Allowed sources |
| --- | --- | --- |
| SSH | 22 | Your own public IP address (search "what is my IP"), if your provider's web console still works with that restriction; see below |
| HTTPS | 443 | Every range listed at [cloudflare.com/ips-v4](https://www.cloudflare.com/ips-v4) |

Leave **outbound** traffic allowed. The installer downloads packages and
Python libraries during Part 5. Don't open port 80 or any other port.

> **Example (DigitalOcean).** **Networking → Firewalls → Create Firewall**.
> Replace the default rules with the two above, and add each Cloudflare range
> as its own source. Under **Apply to Droplets**, choose your server.

On DigitalOcean the project's own rehearsal found that limiting SSH to one
address also blocked the web console. If you rely on the web console, allow
SSH from all addresses while you need it, and narrow it again afterwards.
Your SSH key still protects the login either way.

**What you should see.** The firewall listed as attached to your server. Your
SSH session from 2.3 keeps working.

**If something looks wrong.** If SSH stops working, your public IP may have
changed (home networks change it now and then). Update the SSH rule.

## 2.5 Point your domain at the server

**What you're doing.** Creating the DNS record that sends your CTH hostname
to the server, through Cloudflare.

**Why.** Students and teachers will type your hostname, not an IP address.
Routing it through Cloudflare's proxy hides the server's address.

**Steps** *(Cloudflare dashboard)*.

1. Open your domain, then **DNS → Records → Add record**.
2. **Type** `A`, **Name** the subdomain part of your CTH hostname (for
   `classroom.example.org`, enter `classroom`), **IPv4 address** your server's
   IP, **Proxy status** **Proxied** (the orange cloud). Save.
3. Open **SSL/TLS → Overview** and set the encryption mode to **Full (strict)**.

**What you should see.** The record listed with an orange cloud. If you visit
your hostname now you'll get a Cloudflare error page such as 521 or 522.
That's expected: nothing is installed yet.

**If something looks wrong.** A grey cloud means the record isn't proxied:
edit it and switch the proxy on. The installer only accepts traffic that
comes through Cloudflare.

## Checkpoint

You have a running, firewalled server and a proxied DNS record. Your note now also holds the server's IP address and fingerprint.

**Next:** [Part 3: Get CTH onto the server](part-3-get-cth.md)
