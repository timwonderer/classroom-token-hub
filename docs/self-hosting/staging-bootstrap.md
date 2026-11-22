---
title: Attended staging installation
category: self-hosting
description: Prepare your staging settings, verify the temporary guest and run the canonical installer.
roles: [operator]
---

# Attended staging installation

**Offline tested.** The GitHub-hosted installation job uses your staging-only SSH key and application credentials. It transfers a clean Git bundle for your chosen SHA and calls the [B2 installer](reference-installation.md). Use a separate staging project, application hostname and authentication provider registrations. [Phase C plan](phase-c.md)

## Set up the staging install environment

| Environment setting | Value |
| --- | --- |
| `STAGING_SSH_PRIVATE_KEY` | A dedicated staging client key authorized by the DigitalOcean SSH key ID used to create the VM. Use a GitHub environment secret. |
| `STAGING_HOST_PIN` | A per-run JSON environment secret you set after observing the new guest, as described below. |
| `STAGING_HOSTNAME`, `STAGING_ADMISSION_HOSTNAME` | The selected staging application and access-gate hostnames. |
| `STAGING_MARKETING_URL`, `STAGING_PASSWORDLESS_URL` | Leave the marketing setting unset to use the application’s public informational site, or supply an approved HTTPS site. Leave the Passwordless URL unset to use the SDK’s hosted API; only a custom provider deployment needs an override. Credentials remain staging-only. |
| `STAGING_TURNSTILE_SITE_KEY`, `STAGING_TURNSTILE_SECRET_KEY`, `STAGING_PASSWORDLESS_API_PUBLIC`, `STAGING_PASSWORDLESS_API_KEY` | Deployment-specific values from your staging registrations. The installer creates independent encryption, session, lookup, audit and export keys on every run. |
| `STAGING_ORIGIN_CERT`, `STAGING_ORIGIN_KEY` | PEM chain and private key for the staging origin. Both Cloudflare and the host HTTPS client must trust the issuer; use the staging Let’s Encrypt certificate. |

Store private values as protected environment secrets. The runner reads them when its installation job starts. Bootstrap does not forward runner or DigitalOcean credentials to the application. Review browser destinations and keep optional notification/status integrations disabled until isolated. Ordinary unrestricted outbound traffic is supported.

## Verify the new guest

1. Open the newly created Droplet in your authenticated DigitalOcean console. Compare the numeric ID, installation UUID, public address, staging VPC and profile with the run record.
2. In the Recovery Console, read the CTH staging banner at the guest login prompt. It displays the installation UUID and the guest's public Ed25519 host key. With console shell access you can read the same values from `/etc/cth-stage-id` and `/etc/ssh/ssh_host_ed25519_key.pub`. Do not use an unverified SSH scan as the source of the pin.
3. Point the proxied staging A record at this guest’s verified IPv4 address. Confirm the staging firewall attachment and owner-only Access policy, then set `STAGING_HOST_PIN` for this installation environment to a JSON object with `installation_id` (observed UUID), `droplet_id` (numeric ID), and `host_key` (`ssh-ed25519`, one space, base64 public key, without the key comment). Release the installation job after the values agree. On disagreement, keep the job blocked and inspect the selected VM.
4. The `python` input selects the application interpreter. Keep `3.10` for the production profile; `3.14` runs the trial interpreter described in [operations](operations.md).
5. The job verifies the name-bound SSH key at the provider-reported IPv4 address, guest metadata ID, installation UUID and machine ID before transfer. It runs `apply` and `check` in B2 stage order. Only successful stage names and outcomes appear in the installation output. Keep shell tracing disabled. A failure goes to the [run cleanup procedure](staging-controller.md).

## Optional acceptance

Set `STAGING_ACCEPTANCE_PATH` to a reviewed shell script tracked by the selected SHA, and `STAGING_ACCEPTANCE_SHA256` to its verified digest. Keep both unset to skip it. Put a staging-only Access service token in `STAGING_ACCESS_CLIENT_ID` and `STAGING_ACCESS_CLIENT_SECRET` for an authorized harness. The guest runs the script as a transient dynamic user. It receives the public staging origin in `CTH_PUBLIC_ORIGIN`, the installed release environment on PATH, and token JSON (`CF-Access-Client-Id`, `CF-Access-Client-Secret`) at `$CREDENTIALS_DIRECTORY/access.json`. Send those headers only to the exact approved origin. Provision synthetic classroom activity through authorized application workflows. Test output stays out of Actions evidence. Exit zero only after the approved scenarios pass.

When you finish, verify the Droplet's absence and retire the per-run host pin, origin credentials, service token and any associated staging-only DNS or external credentials according to their intended lifetime. Record any unresolved item for follow-up. A successful guest install does not attest to this cleanup.
