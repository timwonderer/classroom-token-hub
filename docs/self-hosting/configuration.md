---
title: Deployment configuration and credentials
category: self-hosting
description: Select installation targets, prepare private credentials and verify the reference runtime.
roles: [operator]
keywords: [self-hosting, configuration, credentials, admission, Redis]
---

# Deployment configuration and credentials

**Locally tested** covers configuration parsing, required-field rejection, credential separation, template rendering and simulated checks. **Proposed** covers systemd, Ubuntu, provider registration, gate admission and deployed verification. See the [handbook](README.md), [credential contract](../SPEC/SPEC-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_CODE_CONTRACT.md) and [credential operations procedure](../STANDARD_OPERATING_PROCEDURES/SECURITY/SOP-SEC-001_CREDENTIALS_AND_IDENTITY_LOOKUP_OPERATIONS.md).

## Installation manifest

Store a root-owned mode-0600 JSON file outside the checkout under a root-controlled directory. All manifest values are strings. The proxy profile also requires its origin client CA. These identify infrastructure. They carry no classroom permissions. The installer checks them against its enrollment record and its selected host. If an existing record disagrees, inspect the original enrollment before continuing. Never edit the manifest to claim a previously initialized machine or database.

| Field | Source and consumer | Check |
| --- | --- | --- |
| `installation_id` | Generate one independent UUID, lowercase canonical form. Installer state and the operator's database enrollment comment use this value. | Compare the host record, selected manifest and database enrollment. |
| `machine_id` | Copy the 32 lowercase hex digits from the new host's own machine-id, using the operator console. Avoid publishing it in evidence. | Host identity must match on every invocation. |
| `release_sha` | Select an exact reviewed Git commit (40 lowercase hex digits). Used by release extraction, venv and the web unit. | Confirm the supplied source contains that commit and its reviewed database artifact. |
| `database` | Select a new, unreserved lowercase PostgreSQL database name, beginning with a letter, up to 63 characters. | The fresh database owner, enrollment, version and app peer connection must resolve to it. |
| `hostname` | Register the public DNS name of this installation. Enroll this hostname with the selected ingress. | Verify origin certificate name and external Access challenge at this name. |
| `ingress_mode` | For a manual, IPv4 Cloudflare-proxied origin, set `cloudflare-proxy` before the first host stage. Omit for the tunnel profile used by Actions. | The installer checks the selected TLS listener and the external Access gate. |
| `admission_hostname` | Exact distinct team DNS hostname selected by the administrator of the access policy. | An anonymous HTTPS request to the application login must redirect to this host's Access login path. |
| `runtime_env` | Path to an existing root-owned private systemd environment file under `/etc/cth/`. Reference path `/etc/cth/runtime.env`. | Config stage parses all required fields. |
| `tls_cert` | Absolute root-owned regular PEM chain file under `/etc/cth/` for the origin hostname. | Nginx checks pairing with the key. Health probe verifies hostname, chain, and expiry using the host CA store. |
| `origin_client_ca` | Required for `cloudflare-proxy`. Root-owned PEM CA certificate under `/etc/cth/` that signs only this deployment's origin-pull client certificate. Keep its private signing key offline. | Separate from all other manifest file paths. The installer checks file ownership and expiry; Nginx verifies incoming client certificates against it. |
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
| `PASSWORDLESS_API_URL` | Passwordless server SDK, required explicit HTTPS service endpoint for this profile | Select the registered provider endpoint. Browser SDK and CSP still select the hosted provider CDN/API. Only a matching tested integration can claim browser parity. |
| `MARKETING_SITE_URL` | Main blueprint redirect base, required explicit HTTPS marketing origin | Select your separately served home/privacy/terms/district origin. Check resulting redirect locations. Avoid mapping the application's own redirecting home to itself. |
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
| Status collector, optional monitoring and backups | Their separately owned credentials, recipients, projects and retention are outside this EnvironmentFile. Supply them only to their own service. See [installation boundaries](README.md) and the [external status persistence contract](../SPEC/SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md). |

## TLS and admission prerequisites

For the CTH rehearsal, use `staging.classroomtokenhub.com` in the existing DNS zone. Protect that exact hostname and every path with a separate Cloudflare Access application. Scope the DNS record, origin certificate, browser session cookies and authentication registrations to staging. Admit only the owner's enrolled identity. Keep the stock Nginx service masked. The installer manages `cth-ingress.service` and Gunicorn stays on loopback.

**Manual proxied HTTPS.** Set `"ingress_mode": "cloudflare-proxy"` in the installation manifest. Before allocation, prepare the Access application, hostname and origin certificate. On the staging firewall allow inbound TCP 443 only from the current Cloudflare IPv4 ranges and SSH only from the operator's approved source. Compare the ranges with `EDGE_IPV4` in the reviewed installer. After allocation, point a proxied A record at the verified staging IPv4 and choose Full (strict) TLS. Use an origin certificate for the staging hostname trusted by both Cloudflare and the host's local HTTPS client. Keep port 80 closed. Nginx checks the original TCP peer, TLS server name and HTTP hostname, overwrites forwarded addresses and admits host-local TLS probes only for the two health paths. Publishing the origin requires the exact staging firewall to be attached. [Cloudflare source ranges](https://www.cloudflare.com/ips-v4)

**Authenticate the staging origin.** Create a dedicated CA and client certificate using the linked Cloudflare procedure. Upload the client certificate and its private key to per-hostname Authenticated Origin Pulls, associated only with `staging.classroomtokenhub.com`. Install the CA's public certificate at `/etc/cth/tls/origin-client-ca.crt` and set `"origin_client_ca": "/etc/cth/tls/origin-client-ca.crt"` in the manifest before enrollment. Retain the CA signing key in private operator custody. Use this CA exclusively for this deployment. Cloudflare's shared global origin-pull certificate cannot establish deployment identity. Record the uploaded certificate ID, association, CA fingerprint and expiration privately. [Cloudflare custom per-hostname certificate procedure](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/set-up/per-hostname/)

Nginx requires successful client-certificate verification from every Cloudflare peer before forwarding requests, including public health endpoints. The only certificate-free exception is a connection from loopback to `/health` or `/health/status`. The TLS handshake requests a certificate optionally so those local probes work; the HTTP admission rule requires a verified certificate for edge traffic. Keep the Access policy restricted. During live verification, confirm the enrolled hostname works and a controlled alternate zone forwarding the same Host/SNI without the enrolled client certificate is denied. Offline tests simulate this with a shared peer and a foreign certificate. Provider enrollment and actual edge behavior still require the live check.

Monitoring services such as Pulsetic use the public HTTPS hostname with normal server-certificate validation. Cloudflare supplies the origin-pull credential on its connection to the origin. Monitoring clients need no special client certificate. During a restricted Access window, an unadmitted monitor encounters the gate; that result does not establish application health. Certificate renewal must update the scoped Cloudflare association and, when the CA changes, the origin trust file through a reviewed maintenance operation. Retire the origin-pull credential at decommissioning.

**Tunnel profile.** With the default manifest, route the authenticated connector to `https://127.0.0.1:8443`. Verify the origin certificate, SNI and Host header against the enrolled hostname. The connector overwrites client-address headers. Only the host-local connector is trusted to supply them. Keep the connector credential private.

The ingress check probes the anonymous public login and the HTTPS origin separately. A closed gate must redirect to the exact selected admission hostname and its Access login path. It sends no provider credential and follows no redirect. For real acceptance, use an external browser and two enrolled test origins to check admitted and denied identities, distinct client rate-limit attribution, and denial of direct-origin access. Keep the gate closed if any check fails. Other admission providers can be evaluated separately against the deployment contract.

The shipped browser templates still embed hosted status, policy, support, provider SDK and challenge URLs. Configuring marketing and docs bases does not rewrite literal markup. Inspect the rendered destinations and exercise only approved links and staging provider registrations. The automated allocation profile also checks outbound firewall rules. The smallest application change is to source those links and SDK destinations from validated settings or omit optional links. That change requires separate review. Monitoring cannot grant application authority.
