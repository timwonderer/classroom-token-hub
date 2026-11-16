---
title: Attended staging installation
category: self-hosting
description: Prepare your staging settings, verify the temporary guest and run the canonical installer.
roles: [operator]
---

# Attended staging installation

**Offline tested.** The GitHub-hosted installation job uses your staging-only SSH key and application credentials. It transfers a clean Git bundle for your chosen SHA and calls the [B2 installer](reference-installation.md). Use a separate staging account, application hostname and provider registrations. [Phase C plan](phase-c.md)

## Set up the staging install environment

| Environment setting | Value |
| --- | --- |
| `STAGING_SSH_PRIVATE_KEY` | A dedicated staging client key authorized by the DigitalOcean SSH key ID used to create the VM. Use a GitHub environment secret. |
| `STAGING_HOST_PIN` | A per-run JSON environment secret you set after observing the new guest, as described below. |
| `STAGING_HOSTNAME`, `STAGING_ADMISSION_HOSTNAME` | The selected staging application and access-gate hostnames. |
| `STAGING_MARKETING_URL`, `STAGING_PASSWORDLESS_URL` | The approved HTTPS staging marketing origin and authentication provider API for this registration. The B2 preflight rejects hosted CTH destinations. Check routes, credentials and egress independently. |
| `STAGING_TURNSTILE_SITE_KEY`, `STAGING_TURNSTILE_SECRET_KEY`, `STAGING_PASSWORDLESS_API_PUBLIC`, `STAGING_PASSWORDLESS_API_KEY` | Deployment-specific values from your staging registrations. The installer creates independent encryption, session, lookup, audit and export keys on every run. |
| `STAGING_ORIGIN_CERT`, `STAGING_ORIGIN_KEY` | PEM chain and private key for the staging origin. The host and connector must trust the issuer. |
| `STAGING_TUNNEL_TOKEN`, `STAGING_CONNECTOR_VERSION`, `STAGING_CONNECTOR_SHA256` | Staging-only token, reviewed cloudflared release version and SHA-256 for its Linux AMD64 executable. The runner downloads the pinned release, verifies the digest and transfers it over pinned SSH. Configure the staging tunnel to use `https://127.0.0.1:8443`, validate the selected origin SNI and certificate, and require the approved staging audience. Use a version supporting `--token-file`. [Connector flags](https://developers.cloudflare.com/tunnel/reference/run-parameters/) |

Store private values as protected environment secrets. The runner reads them when its installation job starts. Bootstrap does not forward runner or DigitalOcean credentials to the application. Review hardcoded browser destinations and restrict staging egress before enabling any functional tests.

## Verify the new guest

1. Open the newly created Droplet in your authenticated DigitalOcean console. Compare the numeric ID, installation UUID, public address, staging VPC and profile with the run record.
2. In the Recovery Console, read the CTH staging banner at the guest login prompt. It displays the installation UUID and the guest's public Ed25519 host key. With console shell access you can read the same values from `/etc/cth-stage-id` and `/etc/ssh/ssh_host_ed25519_key.pub`. Do not use an unverified SSH scan as the source of the pin.
3. Set `STAGING_HOST_PIN` for this installation environment to a JSON object with `installation_id` (observed UUID), `droplet_id` (numeric ID), and `host_key` (`ssh-ed25519`, one space, base64 public key, without the key comment). Release the installation job after the values agree. On disagreement, keep the job blocked and inspect the selected VM.
4. The job verifies the name-bound SSH key at the provider-reported IPv4 address, guest metadata ID, installation UUID and machine ID before transfer. It runs `apply` and `check` in B2 stage order. Only successful stage names and outcomes appear in the installation output. Keep shell tracing disabled. A failure goes to the [run cleanup procedure](staging-controller.md).

## Optional acceptance

Set `STAGING_ACCEPTANCE_PATH` to a reviewed shell script tracked by the selected SHA, and `STAGING_ACCEPTANCE_SHA256` to its verified digest. Keep both unset to skip it. Put a staging-only Access service token in `STAGING_ACCESS_CLIENT_ID` and `STAGING_ACCESS_CLIENT_SECRET` for an authorized harness. The guest runs the script as a transient dynamic user. It receives the public staging origin in `CTH_PUBLIC_ORIGIN`, the installed Python 3.10 environment on PATH, and token JSON (`CF-Access-Client-Id`, `CF-Access-Client-Secret`) at `$CREDENTIALS_DIRECTORY/access.json`. Send those headers only to the exact approved origin. Provision synthetic classroom activity through authorized application workflows. Test output stays out of Actions evidence. Exit zero only after the approved scenarios pass.

When you finish, verify the Droplet's absence and retire the per-run host pin, tunnel enrollment, origin credentials, service token and any associated staging-only DNS or external credentials according to their intended lifetime. Record any unresolved item for follow-up. A successful guest install does not attest to this cleanup.
