---
title: Staging guest enrollment and private inputs
category: self-hosting
description: Prepare the protected input directory and join a staging Droplet through the provider console.
roles: [operator]
---

# Staging guest enrollment and private inputs

**Offline verified with fixtures.** Guest SSH, external enrollment, the provider console, VPC routing and tunnel operation await a separately authorized [Phase C exercise](phase-c.md). The runner receives only the controller's filtered result. A trusted operator supplies these private files to the coordinator through its administrative channel.

## Prepare the approved run

Under `/etc/cth-staging/runs/<numeric-run-id>/`, root owns the directory (0750) and inputs (0640, group limited to the staging service, or 0600 when accessible to that service). Use regular files and separate credentials for this run. The Phase C operator verifies provenance and registers the actual staging destinations with the providers. The inventory, per-run SSH client key and approved host pin remain outside the Actions workspace.

| Private input | Contents and verification |
| --- | --- |
| `authority.json` | Exact fields `release_sha`, `hostname`, `admission_hostname`, `marketing_url`, `passwordless_url`, `allowed_hosts`, `bundle_sha256`, `connector_sha256`, `acceptance_sha256`. The hostnames and each HTTPS URL's host must appear in the positive staging-only list. The CTH production zone is rejected. Select the explicit approved nonproduction origin and authorized registration for any shared provider API hostname. Enforce restricted routing and egress separately, including browser destinations and hosted links documented by B2. |
| `release.bundle` | A self-contained Git bundle from the reviewed application repository advertising the approved SHA as a head. Include source-only history. Verify its SHA-256 independently, and identify this artifact in the run approval. The clean guest checkout must resolve to precisely this SHA. |
| `connector`, `tunnel.token` | Reviewed Linux x86-64 cloudflared executable (version supporting `tunnel run --token-file`, 2025.4.0 or later) and a per-run remotely managed tunnel credential. Set the configured route to `https://127.0.0.1:8443` with the selected origin SNI/Host, certificate verification enabled, and the authorized staging audience at the edge. Pin the executable digest. Confirm the token belongs to the staging account and this exact tunnel. |
| `origin.crt`, `origin.key` | Dedicated origin PEM certificate chain and private key. The reference host and connector must already trust the issuing chain. The operator checks the hostname, expiry and key association. |
| `integration.json` | Four private deployment-registered values keyed by `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `PASSWORDLESS_API_PUBLIC`, `PASSWORDLESS_API_KEY`. Session, data-encryption, audit, lookup and configuration-signing material are generated per run. All transfers use the pinned SSH connection. No cloud-control token is provided to the guest. |
| `acceptance.sh` | Optional, separately authorized shell harness pinned by `acceptance_sha256`. Set that field to JSON `null` to skip the harness. A transient systemd service with a distinct dynamic user runs the shell on the guest. It receives the selected Python 3.10 venv on PATH, a private writable runtime directory and `CTH_PUBLIC_ORIGIN` set to the enrolled HTTPS origin. Review the harness for lawful application entry points, isolated endpoints and synthetic data. It exits zero only if every approved scenario succeeds. Its raw output is discarded; CI records only the bounded acceptance outcome. |
| `acceptance.json` | Required only with a harness. Supply exactly `CF-Access-Client-Id` and `CF-Access-Client-Secret` for an expiring staging admission service token scoped only to the test origin. Systemd delivers the JSON to the dynamic test user at `$CREDENTIALS_DIRECTORY/admission.json`. Scope browser credential headers to that exact origin and never forward them across redirects. The user has neither the `cthapp` peer role nor its runtime credentials. Review any required browser prerequisites with the selected tests; a passing hook attests only its reviewed scenarios. Revoke this token during retirement. |

The staging owner records ingress and egress verification, provider account/registration ownership, DNS routing, tunnel identity and expiry in the private run authorization. A controller cannot establish those properties from credential syntax. The reference uses the existing B2 Access admission protocol. See the [Cloudflare connector flags](https://developers.cloudflare.com/tunnel/reference/run-parameters/) and [tunnel-token lifecycle](https://developers.cloudflare.com/tunnel/reference/tunnel-tokens/).

## Join the guest

The creation request contains the installation UUID and a freshly generated public client key. Cloud-init generates the server's host key on the guest and installs the restricted client public key. The controller does not learn a host key from an unauthenticated network scan.

As the staging owner, inspect the run's restricted inventory, select its matching Droplet on the independently authenticated **DigitalOcean control-plane console**, and compare the reserved installation UUID, project, VPC, creation time and numeric Droplet ID. Use the provider's authenticated Recovery Console to view the CTH staging enrollment banner at the login prompt. Cloud-init emits the reserved UUID and public host key to the console and installs them in the getty issue banner. Viewing them does not require an SSH connection, a root password or a rescue reboot. If console access is already available, read `/etc/cth-stage-id` and the public key in `/etc/ssh/ssh_host_ed25519_key.pub` there. The boot finishes by replacing root's initially enrolled provider SSH key with the unique restricted run key. The provider key is not an alternative proof after boot. Expect the reserved UUID and an Ed25519 public key. If the guest, ID or UUID is ambiguous, leave the enrollment pending and investigate through the control plane.

Write `host-pin.json` into the same root-controlled input directory with the fields `installation_id` (reserved UUID string), `droplet_id` (positive JSON integer), and `host_key` (only `ssh-ed25519`, a space and its base64 key). The controller waits up to ten minutes within its lease. It authenticates the host over its private VPC address, verifies the guest's reservation and link-local metadata ID, and obtains its machine ID before transferring private inputs. The enrollment is a deliberate operator action. An absent or mismatched pin cannot establish ownership for an ambiguous allocation.

After cloud-init finishes, the controller transfers the release and inputs, verifies the checkout, and invokes the [same B2 stage entry point](reference-installation.md) for both apply and check. The staging tunnel starts before the ingress stage. An interrupted bootstrap goes to resource cleanup. A later run uses a fresh enrollment, secrets and installation UUID.

## Retire external enrollment

After verified Droplet removal, the credential owner revokes the per-run connector token and provider credentials, invalidates origin credentials and any acceptance service token, disables ephemeral routes and removes or explicitly reconciles DNS, Access enrollment and any provider-side residuals. Confirm the tunnel is disconnected and credentials can no longer grant access. Clean up the private per-run sources under the operator's retention policy.

Only then supply `revoked.json` in the protected input directory with `installation_id`, the exact numeric `droplet_id` (JSON `null` for a verified never-allocated run), and `integrations_revoked` literally `true`. This independent operator attestation permits retirement of the local private client key and completion of cleanup reporting. An absent or mismatched receipt leaves retirement outstanding. Keep a private, bounded review record and retire credential-bearing source files separately.
