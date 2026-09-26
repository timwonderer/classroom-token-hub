# Public request telemetry deployment

Authority: DOM-OPS-001 and SPEC-OPS-006. Request cards now use numerical telemetry. The existing `/health/status`
endpoint independently supplies actual endpoint/database connectivity checks.
Application business code and private Grafana access remain independent. Installing these files is an explicit deployment operation.

## Monitoring host

1. Inspect current nginx origin/Cloudflare Access restrictions and private Loki
   listener. The sampler uses only `http://127.0.0.1:3100`, no credentials or
   arbitrary query parameters from users. Confirm `/health/telemetry` receives the
   collector's existing Cloudflare service-token policy; do not broaden app access.
2. Create dedicated system user `cth-status`, group `www-data`, no interactive
   login. Install this commit's `status/__init__.py`, `status/measurements.py`,
   `status_service/__init__.py`, `status_service/log_sampler.py`, and
   `status_service/route_groups.json` under `/opt/cth-status-sampler` in their same
   package directories. These modules use Python standard library only. Keep code
   root-owned, directories0755 and files0644. Do not install the application .env.
3. Install `infra/status/cth-status-sampler.service` and `.timer` under
   `/etc/systemd/system/`. Confirm host Python supports Python3.10 or newer. The
   service writes only its StateDirectory and has loopback-only network access.
   `systemd-analyze verify` both files, reload systemd, run the service once and
   inspect only bounded output JSON. Verify ownership permits nginx (`www-data`)
   to read `/var/lib/cth-status/telemetry.json` (0640). The timer runs at second05
   each minute; query evaluation time is the preceding UTC minute boundary.
4. Include `infra/status/nginx-telemetry.conf` inside the existing app HTTPS server
   block. Inspect inheritance: an exact location must not bypass server-origin
   protections or depend on directives present only in `location /`. Validate
   `nginx -t`; reload only after review. GET/HEAD serve a static no-store snapshot;
   other methods are denied. It has no app session or Grafana proxy dependency.
5. Verify authorized external fetch is JSON200, unauthorized fetch is denied,
   redirects fail closed, raw Loki remains private, and file timestamps advance.
   Enable the timer only after these checks. No synthetic classroom action is needed.

## Collector and Firestore

Deploy the status image normally; existing Cloud Run job and Scheduler identities
and CF secret references remain. Collector reads `/health/telemetry` for request measurements and independently
reads `/health/status` for endpoint/database connectivity.
Keep the one-minute schedule. Service-token deny, malformed JSON, stale source
snapshot and transport failure produce distinct closed unavailable attempts.
Source-minute retries are idempotent; original sample time never becomes receipt
time. Current cards read persisted state only.

Provision Firestore TTL on field `expires_at` for `telemetry_snapshots` (seven-day
expiry) and `telemetry_days` (90-day expiry), plus `telemetry_attempts` (seven-day expiry). TTL deletion is asynchronous; the
reader always bounds history to90 UTC dates. Keep old evidence and notice
retention unchanged. Ensure the current projection and failure-attempt storage
follow the deployment's scoped Firestore permission/retention policy.

## Interpretation and verification

Route expressions are checked-in in `status_service/route_groups.json`. They are
selected request families, not complete domain operations. All service metrics
filter nginx's application upstream127.0.0.1:8000; service totals can include
health polls. Never add query-string, raw URI, user or class labels to snapshots.

Newest broad nginx EVENT time is a source-recency proxy, not ingestion time or
proof of complete logging/application readiness. Static endpoint polls themselves
can maintain that stream. With fresh source recency, no app-family traffic means
NO_TRAFFIC. A stopped/unavailable source remains explicit; counts do not become
zero on failed queries. Quantiles combine matching samples and are reported only
when all counted requests have usable duration values.

Before calling deployment complete, verify source → endpoint → collector →
Firestore → rendered cards/history. Exercise no traffic, low traffic, invalid
snapshot, denied access, source lag, duplicate delivery and recovery with bounded
fixtures or isolated tests, never fabricated production business activity.
Confirm all 404/500/5xx percentages, sample windows and historical coverage labels.

Rollback: disable the new timer, restore the previous reviewed nginx configuration,
validate/reload nginx, and restore the previous status image/job together if
needed. Preserve append-only telemetry and notices; never rewrite new snapshots
as old feature-integrity evidence. Save private configuration backups before any
installation and preserve later operator edits.

## Independent measured platform checks

The collector also performs the existing bounded GET `/health/status` using its
same Cloudflare service-token identity. The app executes its existing `SELECT 1`;
no new application endpoint or business query is introduced. Only endpoint
response and the structured database signal are persisted in the separate
`platform-check-v1` record. All unregistered feature/integrity placeholders are
ignored. HTTP200 establishes endpoint response even if the database check fails.
Only the actual `DATABASE_UNAVAILABLE` result can mark that database check failed;
Access denial, network failure, invalid response and stale source evidence mean
monitoring could not verify it. Original database `checked_at` governs freshness.

Request snapshots and platform checks are collected independently. Test the
service token against both fixed URLs. A platform failure must not discard an
otherwise valid request snapshot. Platform rows become stale after300seconds and
must not claim business correctness. Provision `platform_observations` with seven-day `expires_at` TTL and the
replaceable `platform_current/current` projection. These records never update
request-history rollups. A delayed platform result cannot rewind the current
platform receipt time.

## Bursty activity policy (SPEC-OPS-006 v1.2)

Deploy the status public service and collector together. This revision reuses the
existing minute-by-minute endpoint/database probes and unchanged sampler schema;
no new host service or synthetic business probe is needed. Overall availability
uses fresh platform checks independently of request volume. Feature observations
have no minimum count; 404s remain measurements rather than feature-outage claims.

The collector retains each component's latest nonempty valid source window in
`telemetry_current/current.last_activity`. Context starts with newly collected
activity after deployment; no backfill or rewrite of historical snapshots is
required. Quiet/failed attempts preserve its original time, and readers and writes
bound it to seven days. Idle historical observations do not become current success.
Old daily counters retain their original policy; the page discloses that older
windows required 20 requests. Verify quiet, error, recovery and stopped-monitoring
views before calling the deployment complete.
