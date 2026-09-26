# SPEC-OPS-006: Public Request Monitoring

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-OPS-006 | 1.2 | 2026-09-25 | 1.1 | Subordinate implementation contract |

## I. Purpose

Define objective public request measurements, independent operator interpretation
and historical measured-window presentation authorized by DOM-OPS-001 §1.
A request observation never establishes business correctness or universal availability.

## II. Scope

The closed monitoring sampler, transport, snapshot persistence and public display.
No application business changes, synthetic users, domain reads or mutation probes.
Internal feature integrity remains governed by SPEC-OPS-005.

## III. Authority Level

Subordinate to INV-CORE-000, INV-CORE-001, INV-ARC-005, INV-ARC-007,
INV-ARC-009, INV-ARC-020 and DOM-OPS-001. DOM-OPS-001 authorizes the runtime
behavior; this specification supplies its bounded implementation details.

## IV. Dependencies

- DOM-OPS-001_OPERATIONS_DOMAIN.md
- SPEC-OPS-002_EXTERNAL_STATUS_PERSISTENCE_MODEL.md
- SPEC-OPS-003_APPLICATION_OBSERVABILITY_CONTRACT.md
- SPEC-OPS-005_FEATURE_HEALTH_EVIDENCE.md
- SOP-OPS-001_SERVICE_STATUS_AND_INCIDENT_COMMUNICATION.md

## V. Closed numerical schema

The source is fixed by this schema as `GRAFANA_TELEMETRY`; it is not a caller-supplied
field and cannot be relabeled as an independent feature verifier.

A snapshot contains exactly:

- `schema_version`: `request-telemetry-v1`;
- `sampled_at`: source-generated UTC ISO timestamp for the shared query evaluation time;
- `window_seconds`: integer `300`;
- `source_latest_at`: newest nginx log EVENT UTC ISO timestamp (not ingestion time), or null;
- `components`: one object for each of `service`, `login`, `attendance`, `payroll`,
  `roster`, `classroom_economy`, with no duplicate, missing or additional keys.

Each component contains exactly:

- `key`: one closed component key;
- `request_count`, `http_1xx_count`, `http_2xx_count`, `http_3xx_count`, `http_4xx_count`,
  `http_404_count`, `http_500_count`, `http_5xx_count`: nonnegative integers or null;
- `p80_ms`, `p95_ms`: finite nonnegative numbers or null;
- `collection_state`: `OK` or `UNAVAILABLE`.

For `OK`, all counts are integers and the 1xx/2xx/3xx/4xx/5xx counts partition total.
404 is a subset of 4xx and 500 a subset of 5xx. Zero requests requires null
quantiles. A nonempty window requires usable ordered quantiles (`p80_ms <= p95_ms`).
For `UNAVAILABLE`, every numerical value is null. Unknown fields, arbitrary labels,
booleans used as numbers, nonfinite numbers and unbounded values are rejected.
Counts are bounded at 1,000,000,000 per window and latency at 600,000 milliseconds.
Rates are derived from counts; an absent denominator never means zero percent.
Only this reduced schema leaves the monitoring boundary, never log lines or labels.

## VI. Collection, freshness and classification

The sampler queries local Loki with fixed reviewed route expressions and a common
UTC evaluation time. It aggregates away all labels. Caller-defined queries are
forbidden. Request counts and latency come from the same 300-second window.
The service group observes upstream application requests. Route groups are proxies,
not a complete registry of business operations. Source evidence may overlap groups.

Sample once per minute. A snapshot older than 300 seconds is stale; source lag
older than 180 seconds makes monitoring unavailable/stale rather than normal.
Missing source freshness cannot prove current monitoring. Source future timestamps
must not refresh evidence. The static telemetry endpoint polling request can keep the nginx stream active.
Source recency measures nginx log-source activity only; it cannot certify complete
ingestion, application readiness or feature correctness. No new application health endpoint is required; the existing bounded platform
health read remains authorized independently below.
A successfully queried empty route group with a fresh
source is `NO_TRAFFIC`; an unavailable source is `MONITOR_UNAVAILABLE`.
A transport retry must preserve source timestamps. Receipt time is persisted
separately and never renews evidence. Collection or validation failures produce bounded unavailable evidence, never
invented zero counts or a fabricated source sampled time. The persistence API is
`append_snapshot(snapshot_or_none, received_at, diagnostic=None)`. A null snapshot
records a collector failure using receipt time and one of `TRANSPORT_UNAVAILABLE`,
`ACCESS_DENIED`, `INVALID_SNAPSHOT`, or `STALE_SNAPSHOT`, separately
from genuine source-minute snapshots, so a failed attempt cannot suppress a valid
sample from the same minute. Transport failure is not a source measurement.

Initial policy thresholds are strict greater-than comparisons:

- 5xx / requests > 2%: elevated server-error responses;
- 404 / requests > 5%: elevated not-found responses;
- p95 > 1500 ms: high latency.

404 is a descriptive anomaly signal, not `SYSTEM_FAILURE`: expected resource
absence may account for it. All threshold crossings remain visible regardless of sample size. Any nonempty
window without a threshold crossing is `NORMAL`; there is no minimum count.
This numerical classification does not certify successful classroom actions.
Distinct states are `NORMAL`, `ELEVATED_ERRORS`, `HIGH_LATENCY`,
`NO_TRAFFIC`, `MONITOR_UNAVAILABLE`, and `STALE`. Show all applicable reasons;
where a single state is required, unavailable/stale takes precedence, followed by
elevated errors, high latency, no traffic and normal. Elevated errors
must distinguish server-error responses from not-found responses in visible wording.
These numerical thresholds are disclosed publicly and changed only with a versioned
code/contract amendment. They do not diagnose user impact or create incidents.

## VII. Storage and history

`telemetry_snapshots` stores append-only genuine source snapshots with a deterministic source-UTC-
minute ID and separate `received_at`. A transaction appends each minute once,
updates a monotonic `telemetry_current/current` pointer, and updates that source
UTC day's `telemetry_days/YYYY-MM-DD` rollup once. All transactional reads precede
writes. Duplicate delivery cannot increase coverage; old delivery cannot move the
current pointer backward. Reject stale source snapshots at collector ingestion.

Daily per-component counters are `sampled`, `measured`, `normal`,
`elevated_errors`, `high_latency`, and `other`. `sampled` counts unique persisted
minute windows; `measured` counts eligible windows classified NORMAL,
ELEVATED_ERRORS or HIGH_LATENCY. Empty and unavailable/stale windows do
not establish a normal operating range and are excluded from that denominator.
`normal / measured` is the share of eligible observed windows within thresholds.
With no eligible windows this percentage is unavailable, never 100%.

Display 90 UTC calendar dates including today. Gaps are explicit. Coverage is
eligible measured windows divided by scheduled elapsed minute windows for each
UTC day, not request success or application uptime. Today's denominator stops at
the observation time. Sampled and eligible counts remain available for explanation.
Do not sum overlapping five-minute request counts into daily traffic totals.
A daily single-state tally follows classification precedence while current cards
preserve all applicable threshold reasons.

Historical rollups retain the policy applied at collection; older windows may have
required 20 requests. This distinction is disclosed beside history; old counters
are not recomputed or relabeled as uptime.

Detailed snapshots expire after seven days; daily rollups after 90 days. Use
separate Firestore TTL expiry fields/provisioning for these collections. Do not
alter existing observation or notice retention. The current pointer is replaceable
and still subject to read-time freshness. Old integrity observations are retained
under their existing policy and never transformed into request history.

## VIII. Public interface and operator interpretation

Public layout follows the shared public-page design in this order: overall status
hero, operator incident/update banner, simple teacher/student service cards, and
platform status with database reachability plus request measurements/history.

Overall availability uses the existing independent endpoint/database checks polled
every minute. Both fresh PASS results yield `APP REACHABLE`, including during idle
request traffic. A fresh FAIL yields `AVAILABILITY CHECK FAILED`; missing, unknown,
stale or future checks yield `AVAILABILITY NOT VERIFIED`. A current operator notice
or fresh nonzero HTTP 5xx count qualifies the summary as `ISSUES REPORTED` unless a
connectivity check already failed. The hero's timestamp is the older of the two
fresh PASS/FAIL check timestamps, never stale/future evidence or the request snapshot time. Reachability establishes
connectivity only, not business correctness.

Feature cards describe recent activity, not yes/no functionality estimates. Any
fresh 5xx is `Server errors observed`; otherwise p95 above 1,500 ms is `Slow responses
observed`; otherwise a window containing 2xx/3xx is `Requests responding`. Windows
with only remaining response classes say `Requests declined or not found` without
claiming outage. These labels have no minimum count. Quiet windows say `No recent
activity`; missing/stale collection says `Monitoring unavailable`/`Monitoring out of
date`. All cards disclose their scope in visible text.

The current telemetry projection retains `last_activity`, a map of the closed
component keys to their latest nonempty, valid, fresh source window's `sampled_at`,
`source_latest_at` and validated `component`. The collector updates it atomically
with the current pointer only when that pointer advances. Idle or failed attempts
preserve historical activity without refreshing its timestamp; duplicate or delayed
samples cannot overwrite it. Readers validate retained data and exclude future or
older-than-seven-day entries; advancing writes prune expired entries. No new raw
fields, tenant labels or business data are retained. Absence means no retained
activity. Historical outcomes use neutral styling during inactivity or monitoring
loss, visibly labeled `Last observed` with the original five-minute window end.
They never establish present health or conceal a monitoring failure. Public GET
remains read-only.

Counts, 404/500/5xx percentages, p80/p95, source timing and 90-day history appear in
the lower platform section. Explain their scope and thresholds there, without long
technical qualifications on every teacher card. Preserve the original public brand
wordmark, hero composition, typography and status-card styling. Historical bars
expose full text and keyboard/touch disclosure, not color or hover alone.
Operator notices are independent, explicitly attributed human
interpretation, with optional snapshot links and an investigation evidence note
or reference when no automated snapshot is linked. They do not overwrite metrics.

Public GET reads persisted projections only. The browser never receives Loki,
Grafana or monitoring credentials or a raw-query interface. The sampler writes
bounded validated JSON atomically to `/var/lib/cth-status/telemetry.json`;
`/health/telemetry` is an exact static nginx endpoint permitting GET/HEAD with
`Cache-Control: no-store` and existing Cloudflare Access/origin restrictions.
Collector access uses the existing authorized service-token transport with timeout,
response-size limit and no redirects. Grafana operator authentication is unchanged.
Installing the sampler and endpoint is a separate reviewed deployment operation.

### Independent platform checks

Platform connectivity is persisted separately from request telemetry. Its record has
exactly `schema_version: platform-check-v1`, UTC ISO `received_at`, and `checks`.
Checks contain exactly one `endpoint` and one `database` result, each with `key`,
`outcome` (PASS/FAIL/UNKNOWN), `checked_at` (UTC ISO or null), and a closed diagnostic.
Endpoint HTTP_OK is PASS; HTTP_UNAVAILABLE is FAIL. Actual database
DATABASE_REACHABLE is PASS and DATABASE_UNAVAILABLE is FAIL. ACCESS_DENIED,
TRANSPORT_UNAVAILABLE and INVALID_RESPONSE are UNKNOWN for either check;
STALE_SOURCE is additionally permitted for database UNKNOWN. UNKNOWN carries null
checked_at; proven checks preserve their source timestamp, never later than receipt.
Current results expire after 300 seconds; future or malformed evidence is unknown.
A bounded read of the existing health endpoint may obtain these two actual checks
without collecting its feature placeholders. This is connectivity, not domain proof.

`platform_observations` retains append-only records for seven days using `expires_at`;
`platform_current/current` is a monotonic replaceable projection. Reads are pure.
These records do not contribute to request-window history or service-card proofs.

## IX. Validation

Focused tests cover strict schema/redaction, query failure, malformed/multi-series
responses, no/low traffic, thresholds and their boundaries, 404 versus semantic
failure, stale/future timestamps, retry idempotency, monotonic current pointer,
UTC rollover, history denominators/gaps, independent notices, auth/CSRF and pure
GET. Render populated/idle/stale history and cards for keyboard/touch access.
A deployed claim requires source → collector → Firestore → rendered evidence.

## X. Amendment

Increment version, update date and documentation index, and review changes against
DOM-OPS-001. No amendment may relax internal verification or privacy authority.
