---
title: Install the reference host
category: self-hosting
description: Prepare one identified Ubuntu host and install CTH through the versioned operator interface.
roles: [operator]
---

# Install the reference host

**Proposed reference procedure.** Review the [handbook evidence labels](README.md). For a human installation or an automated rehearsal, run the same `infra/self-hosting/install.py` from the operator's reviewed checkout. Use the stage checks to determine what actually exists on the host. An interrupted run needs inspection before any retry.

## Choose the host and release

The first reference configuration is an x86-64 DigitalOcean SFO3 Basic Premium AMD Droplet with 2 vCPUs, 4 GB RAM, 80 GB advertised NVMe, Ubuntu 22.04 LTS, Python 3.10 and PostgreSQL server and client 14.24. It uses two private Redis processes. The plan chosen for this profile was $28/month, approximately $0.042/hour. Two hours of compute at that rate cost about $0.084. Check the selected size's current rate and budget DNS, keys, monitoring, backup storage and transfer separately. Billing continues while a Droplet is powered off. [DigitalOcean billing](https://docs.digitalocean.com/products/droplets/details/pricing/)

1. **Infrastructure owner.** Select a dedicated empty host and record its provider resource ID, image, region, network policy, expected machine identity and the operator responsible for recovery. Reserve an administrator-only control path. Restrict incoming traffic before any app service starts. On an existing database or shared production host, use the established upgrade or restore procedures. A self-hosting test must have no routes, credentials or resources authorizing access to production.
2. **Host administrator.** Arrange trusted Ubuntu package sources carrying Jammy x86-64 packages and the exact PostgreSQL 14.24 server and client. Prepare enough disk space for the release, virtual environment, database and restore drill. If the exact versions or authentication for trusted package sources are unavailable, resolve package provenance before installing. Select another OS, PostgreSQL major or Python runtime only in a separately recorded test.
3. **Release operator.** Obtain the CTH source from the upstream repository or an authenticated mirror. Select the full reviewed commit SHA containing the installer, pin that checkout and verify its provenance. Run the installer only from that operator-controlled tree. An untrusted checkout executed as root has the authority of root. Record the complete SHA; a moving branch or unreviewed workspace is unsuitable.
4. **Host administrator.** From a private administrative terminal, compare the host's machine identity (command `cat /etc/machine-id`) with the instance inventoried in step 1. Prepare a root-owned, private installation manifest using the release's `infra/self-hosting/installation.example.json` and the [configuration dictionary](configuration.md). Supply separate deployment-specific runtime secrets through the prescribed private file. If the identities disagree, stop and check the connected host. Never copy a production environment file.
5. **Ingress owner.** Prepare a deployment-specific HTTPS hostname, certificate chain, protected private key and restricted audience/admission policy. Register deployment-specific Turnstile and Passwordless credentials for that origin. For this implementation, provide an external gate whose unauthenticated response redirects to the chosen HTTPS admission host under `/cdn-cgi/access/login/`. Configure its authenticated tunnel to `127.0.0.1:8443`, require hostname/SNI and chain validation, and ensure the trusted proxy overwrites client IP headers. The host installer creates the loopback TLS origin. External gate, DNS, tunnel setup and identity grants belong to the ingress operator. Other redirect protocols need separately tested support. Keep public traffic gated while the initial operator and browser checks run. For optional status, telemetry and notification services, verify every destination against the [integration inventory](README.md) before enabling it.

## Prepare the operator inputs

On a fresh host, root uses a private administrative shell. Supply `source_url` from the authenticated upstream or a verified mirror, and `sha` from a separately authenticated release record. If this B2 release is still local to the maintainer's worktree, obtain a reviewed, verifiable Git bundle or publish the reviewed commit before an independent host installation. A checkout cannot fetch a local-only commit from the upstream.

```sh
set -eu
: "${source_url:?set the approved repository or local verified bundle}"
: "${sha:?set the full reviewed Git SHA}"
apt-get update
apt-get install --no-install-recommends -y git ca-certificates
test ! -e /root/cth-installer
git clone --no-checkout -- "$source_url" /root/cth-installer
cd /root/cth-installer
git checkout --detach "$sha"
test "$(git rev-parse HEAD)" = "$sha"
test -z "$(git status --porcelain --untracked-files=all)"
```

Expect a clean, root-controlled source tree at the authenticated SHA. On a package, repository or SHA mismatch, stop. If the path already exists, inspect its owner, origin and state separately. Never replace it to satisfy the check. The installer must run on the identified target machine, not on the workstation from which it was provisioned.

Root creates the example manifest only on this new installation. The following commands require a previously unused `/etc/cth` and use the reviewed source as their working directory. Use the generated UUID and observed machine ID for this installation in the private editor. Set every remaining field to the selected real value, including full SHA, approved hostname, admission hostname and origin certificate paths.

```sh
set -euC
umask 077
mkdir -m 0700 /etc/cth
mkdir -m 0700 /etc/cth/tls
manifest=/etc/cth/installation.json
cat infra/self-hosting/installation.example.json > "$manifest"
python3 -c 'import uuid; print(uuid.uuid4())'
cat /etc/machine-id
editor "$manifest"
stat -c '%a %U %G' "$manifest"
```

Expect `600 root root` and a manifest with no example values; the UUID and machine ID are identifiers. Stop if the directory or file exists unexpectedly. Prepare the deployment-specific runtime file following the [configuration dictionary](configuration.md). Use the enrolled `runtime_env` and never source an unreviewed file as shell code. Deposit the origin certificate and private key at `tls_cert` and `tls_key` through the operator's secure certificate process. Use a certificate chain trusted by the host client and tunnel connector. Keep the private key root-owned and mode 0600. Check certificate validity and hostname independently before dispatching the ingress stage.

**Admission and egress checks.** From an unadmitted external browser, the ingress owner requests the deployment's `/admin/login`. Expect an HTTPS redirect to the enrolled admission hostname under the configured login path. From an admitted test identity, expect the application login only after services are healthy. Confirm direct public access to the origin is blocked and DNS selects the dedicated edge. If either identity sees the wrong destination or bypasses the gate, correct the external policy before accepting the installation. For staging, apply an egress policy for approved package repositories, DNS/time, the dedicated edge and registered authentication providers. Explicitly deny access to production application, data, observability and notification destinations; test it with the network provider's policy inspection or a controlled, isolated test destination. Do not send probes to production to demonstrate denial.

## Installation stages

Use a root administrative terminal on the enrolled host and work from the selected checkout. The commands below assume the operator has set the shell variable `manifest` to the absolute path of the private JSON, normally `/etc/cth/installation.json`. The table lists the permitted operation, required prior state, success signal and recovery for each command. Run one stage at a time in the order shown.

For each stage, root runs `python3 infra/self-hosting/install.py check STAGE --config "$manifest"`, replacing `STAGE` with the literal name in the table. A successful check verifies its required host state. On a new host, an absent stage can require its first apply. Before the first apply or before a stage has started, a check may return nonzero because its journal state does not yet exist. An unexpected identity, version, resource, partial state or permission failure requires investigation before applying. After each apply, repeat its check and retain only the sanitized result. A clean exit is necessary for the next stage.

| Stage and command, as host root | Prerequisite and permitted action | Expected result and failure recovery |
| --- | --- | --- |
| `python3 infra/self-hosting/install.py apply host --config "$manifest"` | Correct machine ID and reference OS. Prepare system prerequisites and dedicated noninteractive accounts. | Required packages, OS and accounts pass the check. Inspect package availability and pre-existing account ownership on failure. |
| `python3 infra/self-hosting/install.py apply postgres --config "$manifest"` | Prepared host and trusted 14.24 packages. Configure the scoped database roles and fresh target on the local cluster. | Expected server, client, role identities, peer access and enrolled empty database. Stop on an existing or unknown target. Use the correct host or a separately provisioned empty database. |
| `python3 infra/self-hosting/install.py apply redis --config "$manifest"` | Prepared accounts, isolated local sockets. Configure separate limiter and student-setup services. | Both instances answer on their intended transports. Student setup is memory-only with persistence, replication and slow logging disabled. Correct configuration and socket ownership before starting the application. |
| `python3 infra/self-hosting/install.py apply release --config "$manifest"` | Exact reviewed Git SHA, Python 3.10, trusted dependency sources. Install the selected release and production dependency manifest under its versioned paths. | Checkout and virtual environment correspond to the selected release. On failure inspect package availability, native build prerequisites, disk space and release ownership. |
| `python3 infra/self-hosting/install.py apply config --config "$manifest"` | Private deployment runtime configuration prepared by the operator. Validate required and conditional settings, key formats, storage and target selection. | Preflight accepts configuration without revealing values. Fix the named setting in private storage. Preserve keys already associated with persisted data. |
| `python3 infra/self-hosting/install.py apply database --config "$manifest"` | Offline, enrolled empty PostgreSQL target, matching release and owner. Invoke the B1 reviewed installer. | The baseline digest, 15 required support categories, sequence state and release head are verified before admission. On a partially initialized target follow the [database recovery procedure](fresh-database.md). |
| `python3 infra/self-hosting/install.py apply services --config "$manifest"` | Verified release, config, database and Redis. Install the reference Gunicorn/systemd service configuration. | The selected release, account, environment and local bind agree with the unit. Inspect unit status and configuration privately if start or verification fails. |
| `python3 infra/self-hosting/install.py apply scheduler --config "$manifest"` | One selected Gunicorn service. Verify the scheduler ownership and startup model. | Exactly the intended service owns scheduling. Stop an unexpected duplicate and inspect ownership before accepting timed financial jobs. |
| `python3 infra/self-hosting/install.py apply ingress --config "$manifest"` | Deployment DNS, certificate, restricted ingress and admission configuration are available. Configure the host side of HTTPS access. | Expected private origin and gated audience. Keep the admission gate closed if certificates, host routing or authorization are uncertain. |
| `python3 infra/self-hosting/install.py apply readiness --config "$manifest"` | All infrastructure stages completed. Check processes, health and available admission observations. | The stage reports the bounded observations it checks. Complete the [operator and browser checks](operations.md) before opening general access. Investigate a missing, unauthorized or unhealthy result. |

The stage journal and lock belong to the identified installation. On a failed or interrupted apply, preserve them and keep the host offline. Check the recorded step against real files, services, database revision and ownership. Resume through the same stage only when it recognizes the completed state or its prerequisites permit safe continuation. If state is ambiguous, retain sanitized diagnostics and recover manually on the enrolled target or replace a confirmed disposable host. Resetting the journal, changing the enrollment, overwriting secrets or stamping a partial database destroys the basis for verifying a retry.

## Service and authority boundaries

The external edge admits only the authorized audience. A host-local ingress forwards to Gunicorn, which executes application routes and the selected scheduler. PostgreSQL holds authoritative business state. The application runtime and schema owner have separate database identities. Redis limiter traffic is separate from ephemeral student setup. Exclude the student-setup service, memory, temporary records and credentials from backup and diagnostic capture. The status publisher and external monitoring can observe their approved signals independently.

The installer provisions infrastructure. Classroom registration, access, deletion and protected writes stay on their own authenticated or explicitly authorized FEAT paths. The first authorized use begins in the [operations chapter](operations.md).

## What has been exercised locally

A second local PostgreSQL 14.24 derivation produced the same SQL and manifest bytes as the B1 artifact. The direct installer initialized an empty database under an ordinary owner and verified 15 reference categories, 27 sequences and the expected Alembic head. Two disposable Redis 8.10.2 processes used the committed service configurations with temporary socket paths. A real limiter increment/read and a student-setup namespaced write/read with expiry succeeded. Local nginx 1.31.6 accepted the rendered TLS configuration with a disposable certificate and temporary paths.

The Ubuntu reference still requires the exact distro package set, peer role setup, protected file permissions, systemd boot and restart, cgroup limits, Gunicorn scheduler lock, remote admission and enrolled browser paths to pass together. Independent installation and external service parity require separate evidence.
