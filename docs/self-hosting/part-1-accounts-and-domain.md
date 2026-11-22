---
title: "Part 1: Accounts and a domain"
category: self-hosting
description: Open the accounts a self-hosted Classroom Token Hub needs and choose its web address.
roles: [operator]
keywords: [self-hosting, tutorial, domain, Cloudflare, Turnstile, Passwordless]
---

# Part 1: Accounts and a domain

Nothing in this part touches a server, and nothing here is billed by the hour.
Do it all in your web browser. At the end you'll have five values saved in your
password manager.

Keep a note called **"CTH install"** in your password manager now. Each step
tells you what to add to it.

## 1.1 Pick a server provider

**What you're doing.** Opening an account with a company that rents servers.

**Why.** CTH needs a computer that's always on and reachable from the
internet.

**Steps.**

1. Choose any provider that offers **Ubuntu 22.04 LTS on x86-64**. DigitalOcean,
   Hetzner, Linode (Akamai), Vultr and AWS Lightsail all do.
2. Create an account and add a payment method.
3. Don't create a server yet. That's Part 2.

**What you should see.** A dashboard with a button such as "Create",
"Deploy" or "Add server".

**If something looks wrong.** Some providers need a day to approve new
accounts. Wait for approval before continuing.

## 1.2 Put your domain on Cloudflare

**What you're doing.** Getting a web address and letting Cloudflare manage it.

**Why.** The current installer expects the Cloudflare proxy in front of the server
([why](before-you-begin.md#strongly-recommended-with-alternatives)). Cloudflare
can only do that for a domain whose DNS it manages.

**Steps.**

1. Create a free account at [cloudflare.com](https://dash.cloudflare.com/sign-up).
2. Either:
   - **you already own a domain:** in Cloudflare choose **Add a domain**, pick the
     Free plan, and follow the prompts to change the domain's nameservers at
     your registrar; or
   - **you need a domain:** buy one through **Cloudflare Registrar** (or any
     registrar, then add it as above).
3. Choose the name for your CTH, usually a subdomain such as
   `classroom.example.org`. It must be a domain you control; the installer
   refuses the project's own `classroomtokenhub.com`.

Add to your note: **CTH hostname** = `classroom.example.org` (yours).

**What you should see.** In Cloudflare, your domain shows **Active**.
Nameserver changes can take from a few minutes to a day.

**If something looks wrong.** If the domain stays "Pending", check that the
nameservers at your registrar exactly match the two Cloudflare gave you.

## 1.3 Create the Turnstile keys

**What you're doing.** Registering your site with Cloudflare Turnstile.

**Why.** CTH shows a Turnstile check on sign-up and sign-in pages to stop
bots. It's required: the app won't start in production without it.

**Steps** *(Cloudflare dashboard, November 2026; the menus may move)*.

1. In the Cloudflare dashboard, open **Turnstile** and choose **Add widget**.
2. Name it, for example "CTH".
3. Add your **CTH hostname** as the hostname.
4. Leave the widget mode as **Managed**, and create it.

Add to your note: **Turnstile site key** and **Turnstile secret key**.

**What you should see.** Two long values. The site key is public; the secret
key is private.

**If something looks wrong.** Keys that start with `1x0000`, `2x0000` or
`3x0000` are Cloudflare's published *test* keys. The installer rejects them.
Create a real widget.

## 1.4 Create the Passwordless.dev keys

**What you're doing.** Registering your site with Bitwarden Passwordless.dev,
the passkey service CTH uses.

**Why.** The current installer requires these keys
([#1791](https://github.com/timwonderer/classroom-token-hub/issues/1791)), and
passkeys are a strongly recommended way to sign in
([why](before-you-begin.md#strongly-recommended-with-alternatives)).

**Steps.**

1. Sign up at [admin.passwordless.dev](https://admin.passwordless.dev/).
2. Create an application for your CTH. Where it asks for your site's origin
   or domain, use `https://` plus your CTH hostname.
3. Copy its **public key** (also called the API key) and its **private
   secret** (also called the API secret).

Add to your note: **Passwordless public key** and **Passwordless private secret**.

**What you should see.** Two different values. The public one is safe to
show; the private one is not.

**If something looks wrong.** If you lose the private secret, create a new
one in the Passwordless.dev admin console. Don't reuse keys from another site.

## Checkpoint

Your "CTH install" note now holds:

- CTH hostname
- Turnstile site key and secret key
- Passwordless public key and private secret

**Next:** [Part 2: Create and secure the server](part-2-create-the-server.md)
