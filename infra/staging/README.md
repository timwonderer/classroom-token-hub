# Owner-attended staging in GitHub Actions

**Offline-tested implementation. Live use requires separate Phase C approval.** Begin on the [Phase C checklist](../../docs/self-hosting/phase-c.md). Each manual dispatch approves one exact application SHA and asks the dedicated staging provider account for one SFO3 Premium AMD Droplet. The owner is responsible for verifying cleanup when available and before authorizing another run. The hosted runner checks out the controller from the protected workflow SHA. The approved application checkout supplies the canonical [B2 installer](../../docs/self-hosting/reference-installation.md).

## Prepare the repository and staging account

1. Use a dedicated staging DigitalOcean team/default project, VPC, SSH key and firewall. The token must have no access to production. Enroll only the resource/read scopes required by `infra/staging/digitalocean.py`; grant the allocation and read scopes only. Omit Droplet and other resource deletion scopes. Keep SSH key-based, close public database and Redis access, and allow outbound traffic only to explicitly reviewed staging and dependency destinations. A standard GitHub-hosted install runner has rotating public addresses. If the owner explicitly permits public key-only SSH for the short test window, restrict that rule to TCP port 22. Keep application ingress behind its separately protected staging tunnel and ensure all other inbound ports remain closed. No workflow modifies a firewall, provider account or production environment.
2. Publish the reviewed workflow on the protected default branch. Set **repository variable** `CTH_STAGING_OWNER` to the authorized owner's GitHub login. Restrict all three staging environments to that branch and keep secrets scoped to their respective environment. A push or PR cannot start this staging workflow. An Actions re-run of a previous dispatch cannot allocate a second Droplet.
3. In the **`cth-staging-cloud` environment**, set secret `DO_STAGING_TOKEN` and variable `DO_STAGING_POLICY` to a JSON object matching the staging enrollment. Use actual checked values; zeroes and angle brackets below are placeholders.

   ```json
   {
     "team_uuid": "<staging-team>",
     "project_uuid": "<staging-default-project>",
     "vpc_uuid": "<staging-vpc>",
     "image_id": 0,
     "ssh_key_id": 0,
     "firewall_id": "<staging-firewall>",
     "allow_public_ssh": true,
     "firewall_rules_sha256": "<approved-rules-sha256>"
   }
   ```

   Select the numeric ID of the public Ubuntu 22.04 x64 image in SFO3. Compute the firewall digest from the provider's exact `inbound_rules` and `outbound_rules` arrays in an object using compact JSON separators and sorted keys; preserve list order. Apply the firewall to the exact staging tag `cth-ephemeral-staging`. Set `allow_public_ssh` to true only when the owner has approved public key-only SSH on TCP port 22 for the standard hosted runner. Review expected staging cost and human cleanup ownership before dispatch. The cloud environment is used for allocation only.
4. In the **`cth-staging-install` environment**, set up an owner approval hold before releasing credentials. The same owner may dispatch and approve. Leave “Prevent self-review” unchecked for this arrangement. The hold lets the owner enter the fresh, independently observed host pin after allocation. Confirm that the repository plan supports the hold before any live run.
5. Prepare this install environment's variables and secrets. The [guest enrollment procedure](../../docs/self-hosting/staging-bootstrap.md) defines the formats and trust boundaries. Only the guest installation step receives these values. The install job receives no cloud API token.

   | GitHub type | Names |
   | --- | --- |
   | Variables | `STAGING_HOSTNAME`, `STAGING_ADMISSION_HOSTNAME`, `STAGING_MARKETING_URL`, `STAGING_PASSWORDLESS_URL`, `STAGING_CONNECTOR_VERSION`, `STAGING_CONNECTOR_SHA256` |
   | Secrets | `STAGING_HOST_PIN`, `STAGING_SSH_PRIVATE_KEY`, `STAGING_TURNSTILE_SITE_KEY`, `STAGING_TURNSTILE_SECRET_KEY`, `STAGING_PASSWORDLESS_API_PUBLIC`, `STAGING_PASSWORDLESS_API_KEY`, `STAGING_ORIGIN_CERT`, `STAGING_ORIGIN_KEY`, `STAGING_TUNNEL_TOKEN` |
   | Optional, only for explicitly authorized acceptance | Variables `STAGING_ACCEPTANCE_PATH`, `STAGING_ACCEPTANCE_SHA256` and secrets `STAGING_ACCESS_CLIENT_ID`, `STAGING_ACCESS_CLIENT_SECRET` |

   Use dedicated staging DNS, origin TLS, restricted tunnel/admission and authentication provider registrations. Select an application-relative acceptance script at the approved SHA and verify its hash before setting both acceptance variables. Omit that pair to install without executing synthetic scenarios.

## Run, inspect and close

1. In the DigitalOcean staging console, check that there are no outstanding Droplets or unresolved billable leftovers from the previous run. Select **Owner-attended CTH staging** on the default branch, enter the exact approved 40-hex application SHA, choose the reference profile, and confirm both dispatch checkboxes. Keep the GitHub run ID and selected resource profile handy.
2. As soon as a valid create response arrives, the allocation step records the **numeric provider ID** in job outputs and the run summary. Match it with the provider console and the run-specific label. If no numeric receipt arrives, a timeout may still have allocated a resource. Stop further dispatch and reconcile the account manually. Never use a matching name or tag by itself as deletion authority.
3. Before releasing the install job, use the provider console to independently obtain the SSH host key and installation UUID for that exact Droplet. Update `STAGING_HOST_PIN` in the protected install environment for this run and then approve the waiting job. A previous run's host key or an unverified network scan is insufficient. Installer stdout contributes only allowlisted completed stage names to the summary. Preserve the resulting install and cleanup statuses; never paste raw secrets, logs, classroom records or audit events into the run.
4. Configure `cth-staging-first-use` with the owner as required reviewer, self-review permitted, main-only deployment and no secrets. After successful installation this job waits while the owner follows the [first-use and recovery procedures](../../docs/self-hosting/operations.md). Approve after recording successful checks, or reject if incomplete or failed. Billing continues during the hold. Installation failure skips the hold. The closeout job reports the resource ID for manual destruction. If it never runs, consult the creation receipt and DigitalOcean activity directly.
5. **After every run**, match the numeric ID and creation activity to the staging project, inspect attached resources and complete any required recovery checks. Personally destroy the verified Droplet in DigitalOcean and confirm absence. Inspect volumes, snapshots, backups and reserved IPs, retire per-run credentials and record the time and disposition. Leave the exercise open if ownership is uncertain. Billing can continue until destruction.

For a one-team installation use the [manual handbook rehearsal](../../docs/self-hosting/staging-controller.md#rehearsal-with-one-digitalocean-team).
