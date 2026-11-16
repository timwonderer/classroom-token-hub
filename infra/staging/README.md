# Enrolling the staging coordinator

**Locally fixture-tested.** Complete these steps only after the owner approves Phase C. The coordinator is an existing dedicated, reachable Linux operator machine with a private path to the staging VPC. GitHub sends an authorized request over SSH. The coordinator retains the lease and the cloud token. Its systemd timer uses the same inventory even when the SSH session or GitHub runner disappears. The temporary Droplet receives no DigitalOcean token.

## Prepare the control host

1. As host administrator, install a reviewed copy of this repository, including its Git history, at `/opt/cth-staging` on a root-owned filesystem. Check its exact full SHA out detached. All checkout files and their parent directories must be root-controlled, with no writable group/other permissions. Use Python 3.10+, Git and OpenSSH. Confirm that the dedicated operator account `cthstage` can execute the checkout and cannot edit it. Keep the SSH account's shell available only through its restricted public key below; disable password, interactive authentication and all other authorized keys for that account.
2. Create protected control directories. In a new installation, root can use the following commands once the account/group exist. Inspect pre-existing paths separately. The service group needs read access to its own staging-only enrollment. Group members must not include other users.

   ```sh
   install -d -m 0750 -o root -g cthstage /etc/cth-staging /etc/cth-staging/runs
   install -d -m 0700 -o cthstage -g cthstage /var/lib/cth-staging
   for part in pending runs evidence; do
     install -d -m 0700 -o cthstage -g cthstage "/var/lib/cth-staging/$part"
   done
   ```

   The expected result is a private persistent filesystem with working local SQLite, POSIX locks and synchronized time. A runner's checkout, temporary directory and network share are unsuitable for this inventory. If a lease, directory or database is missing on an established coordinator, quarantine dispatch and reconcile with the provider; do not reset the ledger. Never restore an old copy while new allocation is enabled.

3. As the staging infrastructure owner, enroll a dedicated DigitalOcean team, its empty default project, a separate VPC and a static tag-based firewall. The token's account boundary must exclude all production resources. Review ingress (private SSH only from the coordinator) and egress allowlists, private routing/NAT if used, and verify exclusion of production destinations. Require distinct staging DNS, edge identity, tunnel, notification destinations, and stage-specific Turnstile and Passwordless registrations. The controller creates only the temporary Droplet. Use precise endpoint scopes documented in the [provider API](https://docs.digitalocean.com/reference/api/reference/droplets/), including the read dependencies of the enrolled team, project, VPC, image, firewall/tag, size and auxiliary-resource queries.
4. Install the token alone in `/etc/cth-staging/token` and the policy below in `/etc/cth-staging/policy.json`. Both are root-owned regular files, group `cthstage`, mode 0640. Substitute checked operator values. The firewall digest is SHA-256 of the exact provider rule object containing the keys `inbound_rules` and `outbound_rules`, serialized with sorted keys, compact JSON separators and original list order. The enrolled image ID must be the public Ubuntu 22.04 x64 image actually available in SFO3. Recheck current catalog and billing before enrollment. Image, team, SSH key and firewall identifiers below are placeholders.

   ```json
   {
     "controller_sha": "<full-reviewed-coordinator-commit>",
     "provider": {
       "team_uuid": "<staging-team-uuid>",
       "project_uuid": "<default-staging-project-uuid>",
       "vpc_uuid": "<dedicated-staging-vpc-uuid>",
       "image_id": 0,
       "firewall_id": "<staging-firewall-uuid>",
       "firewall_rules_sha256": "<approved-rules-digest>",
       "ssh_key_id": 0
     }
   }
   ```

5. As root, install the reviewed `cth-staging-cleanup.service` and `cth-staging-cleanup.timer` from this directory under `/etc/systemd/system/`, mode 0644. Verify the exact paths and enrollment before the first service activation. Run `systemd-analyze verify` on both units, then `systemctl daemon-reload` and `systemctl enable --now cth-staging-cleanup.timer`. Confirm a successful execution and fresh `/var/lib/cth-staging/sweep-ok`. The timer runs every minute and catches up after reboot. Monitor failed cleanup units and absence of a successful heartbeat **from outside this host**. Assign the on-call operator an overdue-lease alert and the ability to inspect the staging account independently. Loss of the coordinator or provider can extend billing beyond the target lifetime.
6. Install a dedicated public dispatch key in a root-controlled SSH authorized-keys file for `cthstage`. Prefix the key with these literal options:

   ```text
   restrict,command="/usr/bin/python3 -EsB /opt/cth-staging/infra/staging/controller.py forced"
   ```

   Require an independent host-key pin for the coordinator. The GitHub environment `cth-ephemeral-staging` must restrict deployment to the protected default branch and provide a hold while the operator records the pending run ID. Configure required reviewer approval where supported. A sole operator can authorize their own pending dispatch; a separate reviewer is an optional local control. If your GitHub plan cannot hold environment jobs, use the owner-enrollment wait described below. Configure only `STAGING_COORDINATOR_HOST` (environment variable), `STAGING_DISPATCH_KEY` and `STAGING_COORDINATOR_KNOWN_HOST` (environment secrets). The last contains the OpenSSH host key line with the alias `cth-staging-coordinator`. Review the workflow's immutable artifact-action pin. No application checkout, cloud token, customer database or guest credential belongs on the hosted runner.

## Authorize one run

1. The operator selects **Ephemeral CTH staging** on the reviewed default-branch workflow and dispatches the exact approved application SHA and `sfo3-premium-amd` profile. Leave the environment job waiting at its approval gate when available. Without environment waiting rules, the coordinator allows up to five minutes for a missing per-run approval file to appear; it allocates nothing during this wait. Record the new numeric GitHub run ID, the workflow commit, the installed coordinator commit, the account/project/resource budgets and the dedicated endpoints. First attempts only; a new dispatch needs a new approval.
2. On the coordinator, root creates `/etc/cth-staging/runs/<run-id>/` as root:cthstage 0750. Install `approval.json` root:cthstage 0640, matching the pending job. Set `dispatch_before` to the UTC epoch second by which the job must be admitted, at most 15 minutes from dispatch processing. The two-hour lease begins at reservation; cleanup begins five minutes before expiry or immediately after the last test.

   ```json
   {
     "run_id": "<numeric-run-id-as-string>",
     "sha": "<40-hex-application-commit>",
     "profile": "sfo3-premium-amd",
     "controller_sha": "<40-hex-coordinator-commit>",
     "workflow_sha": "<40-hex-dispatched-default-branch-commit>",
     "dispatch_before": 0
   }
   ```

3. Enroll the independent guest inputs and staging registrations for this exact run as documented in the [guest enrollment procedure](../../docs/self-hosting/staging-bootstrap.md). Verify source, immutable executable digests, DNS/edge and egress policy, public denial and private routing. Then release the environment approval. Prepare to independently verify the guest SSH key from its DigitalOcean console and match the Droplet ID, run UUID and key to the protected lease before releasing guest secrets. SSH trust-on-first-use cannot establish this identity.
4. Keep provider and guest raw output on the coordinator. GitHub accepts only a bounded result containing public run metadata, completed stage names and times, bounded acceptance/phase/cleanup outcomes. Its artifact expires after three days; local stage evidence has the same retention. The separate durable lease record retains IDs and terminal disposition to prevent replays.
5. As the on-call owner, use `sudo -u cthstage /usr/bin/python3 -EsB /opt/cth-staging/infra/staging/controller.py inspect <run-id>` on the coordinator to see exact ownership and pending retirement. The dispatch key cannot run this command. Confirm the staging integrations are retired and record the independent revocation receipt. The dispatcher allows 90 seconds after verified destruction for the receipt without extending cloud lifetime. Inspect `current_cleanup` for current disposition and `evidence` for the runner’s observation. Until that receipt is verified the run remains outstanding even if the provider says the Droplet is gone. If the job reports pending receipt, see the next independent reaper result and local disposition. Runner artifacts report only what was verified before the job ended.
6. If creation or deletion times out, consult the restricted ledger, account/project and independently authenticated guest pin. For duplicate candidates, unknown ownership, residual storage/IPs or unverified absence, preserve the lease, avoid another dispatch and have the designated operator reconcile exact IDs. Restart the timer on the same inventory after fixing connectivity or enrollment drift. Do not broaden token scopes opportunistically, delete candidates by tag, or clear the lease to start another run. Inspect provider billing and separate integration usage after cleanup.
