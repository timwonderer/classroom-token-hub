---
title: Deployment configuration and credentials
category: self-hosting
description: Select installation targets, prepare private credentials and verify the reference runtime.
roles: [operator]
keywords: [self-hosting, configuration, credentials, admission, Redis]
---

# Deployment configuration and credentials

Use this page when you want to know **what a setting means**. For creating
the files, follow [Part 4](part-4-describe-your-installation.md); it supplies
the commands and expected results.

There are two files. `installation.json` identifies this server and the
version first installed on it. `runtime.env` holds the settings the running
app needs, including private keys. JSON is a structured text format; an
environment file is a list of `NAME=value` lines. Neither file is something
you need to program.

**Example:** `hostname` is your address without `https://`.
`DATABASE_URL` is the app's connection description for its database, not a
website to open. Keep its provided format unless you're deliberately changing
the installation design.

When this page says **mode 0600** or **`600 root root`**, it means the file
belongs to the server administrator and only that account can read or write
it. The leading zero is conventional notation for file permissions; you aren't
being asked to invent a password.

Configuration parsing, required-field rejection, credential separation and template checks were tested locally. Host rehearsal results are release-specific; the [rehearsal record](rehearsal-findings.md) identifies what ran and what remains unverified. Do not read a successful parser check as proof that a provider key or browser flow works. See the [handbook](handbook-overview.md), [credential contract](../SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md) and [credential operations procedure](../STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md).

## Installation manifest

Store a root-owned mode-0600 JSON file outside the checkout under a root-controlled directory. All manifest values are strings. These identify infrastructure. They carry no classroom permissions. The installer checks them against its enrollment record and its selected host. If an existing record disagrees, inspect the original enrollment before continuing. Never edit the manifest to claim a previously initialized machine or database.

| Field | Source and consumer | Check |
| --- | --- | --- |
| `installation_id` | Generate one independent UUID, lowercase canonical form. Installer state and the operator's database enrollment comment use this value. | Compare the host record, selected manifest and database enrollment. |
| `machine_id` | Copy the 32 lowercase hex digits from the new host's own machine-id, using the operator console. Avoid publishing it in evidence. | Host identity must match on every invocation. |
| `release_sha` | Select an exact reviewed Git commit (40 lowercase hex digits). Used by release extraction, venv and the web unit. | Confirm the supplied source contains that commit and its reviewed database artifact. |
| `database` | Select a new, unreserved lowercase PostgreSQL database name, beginning with a letter, up to 63 characters. | The fresh database owner, enrollment, version and app peer connection must resolve to it. |
| `hostname` | Register the public DNS name of this installation. Enroll this hostname with the selected ingress. | Verify the origin certificate name at this name. |
| `ingress_mode` | Optional; the default and only supported value is `cloudflare-proxy`. Manual installation and Actions use the same IPv4 proxied HTTPS profile. | The installer checks the selected TLS listener. |
| `admission_hostname` | Optional. The Cloudflare Access team hostname, if you use Access for maintenance mode. Manifests from earlier releases may keep it. | When present, it must be a valid hostname distinct from `hostname`. The installer does not probe Access. |
| `runtime_env` | Path to an existing root-owned private systemd environment file under `/etc/cth/`. Reference path `/etc/cth/runtime.env`. | Config stage parses all required fields. |
| `tls_cert` | Absolute root-owned regular PEM chain file under `/etc/cth/` for the origin hostname. | Nginx checks pairing with the key. Health probe verifies hostname, chain, and expiry using the host CA store. |
| `tls_key` | Separate root-owned private PEM key file under `/etc/cth/`. Generate and transport through the operator's TLS process. Keep normal group/other permissions cleared. Unattended startup requires a readable key without an interactive passphrase. | Nginx configuration check must succeed. Preserve the key on failure. |

## Runtime environment

Use a trusted console and a private file editor or secret manager to provision the root-owned environment file with mode 0600. Systemd reads this file and injects it into the `cthapp` process. Keep keys and enrollment material out of Git, shell history, service arguments, telemetry and test artifacts. Use one unquoted `NAME=value` per line. Blank lines and lines starting with `#` are accepted. Shell expansion, duplicate keys, unknown variables and multiline values fail preflight. Use canonical ASCII URL/credential forms. The parser reports the field or failure class without its value.

| Runtime variable | Consumer and requirement | Source, format and verification |
| --- | --- | --- |
| `FLASK_ENV` | App startup, required, public setting | Set `production`. This selects secure cookies and requires Turnstile. |
| `DATABASE_URL` | SQLAlchemy, required, connection metadata | Set `postgresql:///<database>?host=/var/run/postgresql&port=5432`, using the exact manifest database. Local peer authentication maps the running OS account to PostgreSQL `cthapp`. No database password is needed for this profile. |
| `RATELIMIT_STORAGE_URI` | Flask-Limiter and limits, required, local socket metadata | Use `redis+unix:///run/cth-rate-limit/redis.sock`. Shared across workers. Check permission as `cthapp` and exercise rate limits with two distinct clients. |
| `STUDENT_SETUP_REDIS_URL` | Student claim/recovery, required, local socket metadata | Use `unix:///run/cth-student-setup/redis.sock`. Independent memory-only instance. The Redis stage checks memory-only settings and authority restrictions. Rehearse restart/expiry through the real claim and recovery workflows. |
| `SECRET_KEY` | Flask session signing, required secret | Generate 32 distinct random bytes in lower-case hex using a CSPRNG. Verify session continuity and isolation in a real login. |
| `PEPPER_KEY` | Identity keyed lookups, required secret | Independently generate 32 random bytes in lower-case hex. Verify login and retry using synthetic identities. Preserve across restore. |
| `ENCRYPTION_KEY` | Fernet PII and TOTP encryption, required secret | Independently generate a 32-byte Fernet key in padded URL-safe base64, e.g. via the cryptography library's Fernet key generator inside the secret-provisioning process. Verify by authorized synthetic enrollment and login. |
| `AUDIT_HMAC_KEY` | Audit signing and verification, required secret | Independently generate 32 random bytes in lower-case hex. Verify nonempty protected lineage against the actual complete head. Preserve during restore and rollback. |
| `CONFIGURATION_EXPORT_KEY` | Class configuration export and import, required secret for reference functional acceptance | Independently generate 32 random bytes in lower-case hex. Check a signed export/import through the authorized teacher flow. Rotation invalidates outstanding artifacts. |
| `TURNSTILE_SITE_KEY` | Browser challenge, required public identifier | Register this deployment hostname and use its site identifier. Validate a real challenge in Chromium. |
| `TURNSTILE_SECRET_KEY` | Turnstile server verification, required secret | Inject its matching provider-issued secret. Preflight rejects published testing-key prefixes. Verify challenge denial and success end to end. |
| `PASSWORDLESS_API_PUBLIC` | Passwordless browser enrollment and sign-in, required public key for functional acceptance | Use the deployment's registered public credential. Browser SDK and allowed origins must agree. |
| `PASSWORDLESS_API_KEY` | Passwordless server SDK, required secret for functional acceptance | Inject the matching server credential. Validate enrollment and authentication in the operator-approved provider account. Never test it against a shared production registration. |
| `PASSWORDLESS_API_URL` | Optional Passwordless server SDK endpoint override | Omit to use the SDK’s hosted endpoint, as the application supports. Supply an HTTPS override only for a matching tested provider deployment. Browser SDK and CSP still select the hosted provider CDN/API. Only a matching tested integration can claim browser parity. |
| `MARKETING_SITE_URL` | Optional main blueprint redirect base | Omit to use the application default, `https://classroomtokenhub.com`, for public home/privacy/terms/district pages. An operator may instead supply an HTTPS informational site. This does not grant access to production application state. Check resulting redirect locations. Avoid mapping the application's own redirecting home to itself. |
| `EXTERNAL_DOCS_BASE_URL` | Optional public HTTPS documentation origin | Omit for local route behavior. If set, verify its path map and final destinations. |
| `LOG_FILE` | Flask rotating app log and WSGI error reader, required reference path | Use `/var/log/cth-web/app.log`. Systemd creates a protected writable LogsDirectory and applies a private umask. Verify rotation and operator access. |

As the **root operator** run the shared `python3 infra/self-hosting/install.py check config --config /etc/cth/installation.json` after applying that stage, using the same manifest path supplied during installation. Expect success with no keys printed. On failure, correct the named field or ownership through the secure provisioner. Preserve existing keys and retry the same check. Local parsing cannot prove provider validity, deployment-specific key provenance or end-to-end functionality.

## Conditional features and runtime defaults

The initial reference EnvironmentFile accepts the variables above. Other supported application options require a separately reviewed host configuration. This keeps the first installation from acquiring development switches, old signing keys, unintended endpoints or inherited process settings.

| Variables or integration | Current consumer, format, sensitivity and operating decision |
| --- | --- |
| `SECRET_KEY_FALLBACKS`, `CSRF_SECRET_KEY` | Flask session key rotation (comma-separated retired secrets) and optional dedicated CSRF secret. Omit on a fresh baseline, where no retired session is valid. Use the security SOP for rotation and explicitly extend/test the installer before enrolling a deployment that requires these. Never regenerate credentials on retry. |
| `REDIS_URL`, `CI`, `GITHUB_ACTIONS`, `DEV_ENABLE_RATELIMIT` | Alternative or development Flask-Limiter inputs. The reference uses explicit socket URI and a production environment. Reject these aliases and flags in the runtime file. |
| `FLASK_APP`, `TZ` | CLI selects the app explicitly with `--app app`; WSGI selects UTC. No private value or runtime override required. Class timezone remains class-scoped. |
| `STATUS_PAGE_URL`, `GRAFANA_URL` | WSGI validates a narrow list of hosted status URLs. The optional sysadmin Grafana proxy defaults to localhost port 3000. Omit status publication and reserve that port for an authorized service or leave it unbound. Do not exercise optional proxy/status features until isolated. |
| `SUPPORT_IFTTT_EVENT`, `SUPPORT_IFTTT_KEY`, `SUPPORT_EMAIL` | Optional notification event ID and IFTTT secret require an explicitly approved recipient and integration. `SUPPORT_EMAIL` is mentioned by the deployment runbook; hardcoded contact links need a separate implementation change. None is enrolled by the reference. |
| `LOGIN_NOTICE_PATH` | Optional root-managed sign-in notice path. Omit on the initial installation. |
| `LOG_LEVEL`, `LOG_FORMAT`, `TLCP_NOISE_ENDPOINT_PREFIXES` | Optional logging level/format and comma-separated request-telemetry filtering inputs. Use the built-in production settings. Never add secrets/PII to log formats. |
| `TRUSTED_PROXY_CIDRS` | Optional additional trusted proxy networks. Keep omitted. Gunicorn receives requests from the dedicated local Nginx proxy. |
| Status collector, optional monitoring and backups | Their separately owned credentials, recipients, projects and retention are outside this EnvironmentFile. Supply them only to their own service. See [installation boundaries](handbook-overview.md) and the [external status persistence contract](../SPEC/SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md). |

## TLS and admission prerequisites

Use your own hostname, provider registrations and TLS files for an independent
installation. [Part 4](part-4-describe-your-installation.md#44-get-the-https-certificate)
provides the certificate steps. The installer manages `cth-ingress.service`;
keep the stock Nginx service masked and Gunicorn on loopback.

**Current installer constraint: Cloudflare-proxied IPv4 HTTPS.** Publish a
proxied A record, set Full (strict) TLS, and permit incoming TCP 443 only from
Cloudflare's current IPv4 ranges. Compare those ranges with `EDGE_IPV4` in the
selected release. Limit SSH to the sources needed for your administrator and
recovery access; leave port 80 closed. Use a publicly trusted certificate that
both Cloudflare and the host's own HTTPS client accept. A Cloudflare Origin CA
certificate alone does not satisfy the local probe.
[Cloudflare source ranges](https://www.cloudflare.com/ips-v4)

No Cloudflare Tunnel, private CA or origin-pull client certificate is required
by this installer. The IP allowlist identifies a Cloudflare network peer, not
a particular account or Access admission. Local checks do not prove that every
alternative route to the origin is blocked; test direct-origin denial from
outside the host too.

**Maintenance access.** Access is not an installation precondition. When you
need to restrict the application audience during setup or maintenance, follow
[Part 7](part-7-keep-it-running.md#710-optional-maintenance-mode-with-cloudflare-access).
An Access login does not replace CTH's teacher or student login, and does not
stop scheduled jobs.

**Certificate renewal.** The installer copies no automated renewal workflow.
Its dedicated Nginx service and PEM input paths differ from the project's
hosted Certbot setup. Follow [renewal and verification](part-7-keep-it-running.md#76-renew-the-certificate)
before the actual expiry date. Choosing a different certificate automation
tool is possible, but its deployment/reload steps need separate verification.

**Maintainer rehearsal only.** The recorded trial used the project's
`staging.classroomtokenhub.com`, a previously issued certificate and owner-only
Access admission. Those were resources for that trial, not values for another
operator to copy. Historical staging instructions remain in
[staging bootstrap](staging-bootstrap.md) and the [rehearsal record](rehearsal-findings.md).

Monitoring services such as Pulsetic use public HTTPS and need no special client certificate. During an Access-restricted window, an unadmitted monitor encounters the gate; that is an admission observation, not application health. A specialized status service is not an installation prerequisite.

The ingress and readiness checks probe the HTTPS origin only. They do not require Cloudflare Access: Access is optional and serves only as maintenance mode, so an open site passes. For real acceptance, use an external browser to check distinct client rate-limit attribution and denial of direct-origin access.

The shipped browser templates still embed hosted status, policy, support, provider SDK and challenge URLs. Configuring marketing and docs bases does not rewrite literal markup. Inspect the rendered destinations and exercise only approved links and staging provider registrations. The automated allocation profile checks the enrolled firewall digest but permits ordinary unrestricted outbound rules. Staging isolation comes from the selected host, private state and independent credentials; a public informational link is not a production business integration. The smallest application change is to source those links and SDK destinations from validated settings or omit optional links. That change requires separate review. Monitoring cannot grant application authority.
