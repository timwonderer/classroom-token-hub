# SPEC-OPS-006: Public Request Monitoring

| Reference Number | Version | Effective Date | Supersedes | Authority Level |
|---|---|---|---|---|
| SPEC-OPS-006 | 1.3 | 2026-09-30 | 1.2 | Subordinate implementation contract |

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

The public pages are written for teachers and students. Labels use plain language
and describe what a reader can rely on; protocol names, enum values and
investigation references never serve as headings. Public layout follows the shared
public-page design in this order: overall status hero, operator incident/update
banner, simple teacher/student service cards, and platform status with database
reachability plus request measurements/history.

The hero asks "Is Classroom Token Hub Working?" and answers with exactly one state.
Precedence is top to bottom; the first condition that holds decides:

| State | Public label | Condition |
|---|---|---|
| `maintenance` | `Under maintenance` | A fresh `gate` check reports the Application Availability Gate closed (§Independent platform checks) |
| `unavailable` | `Mostly unavailable` | A fresh endpoint or database check is FAIL |
| `degraded` | `Detected problems` | A current operator notice, or a fresh nonzero HTTP 5xx count |
| `available` | `No known issues` | Both endpoint and database checks are fresh PASS, including during idle request traffic |
| `unknown` | `Unknown` | Anything else: missing, unknown, stale or future checks |

`Under maintenance` is gate messaging under DOM-OPS-001 §Application Availability
Gate. It communicates an access restriction and makes no claim about application
health; it overrides the other states because readers cannot enter while the gate is
closed, whatever the checks report. `No known issues` claims only the absence of a
known problem: reachability establishes connectivity, not business correctness. The
hero's timestamp is the older of the two fresh endpoint/database PASS/FAIL check
timestamps, never stale/future evidence or the request snapshot time. Each state
carries a visible word as well as its colour (INV-ARC-020).

Feature cards describe recent activity, not yes/no functionality estimates. While
the hero is `Under maintenance`, every card reads `Closed for maintenance`: nobody
can enter, whatever requests from behind the gate show. Otherwise a
current operator notice for the card's capability takes precedence: an `AWARE`
notice reads `Checking reports`, any other active notice `Having problems`.
Otherwise any fresh 5xx is `Checking: errors seen` — an automatic observation at the
`AWARE` level, which never creates or implies a notice; p95 above 1,500 ms is
`Slower than usual`; a window containing 2xx/3xx is `Working`. Windows with only
remaining response classes say `Nothing to report`, claiming neither success nor
outage. These labels have no minimum count. Quiet windows say `Quiet`; missing or
stale collection says `Status unknown`. All cards disclose their scope in visible
text.

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
the lower platform section, collapsed by default behind a visible disclosure, and
the 90-day history may also be summarised beside the main column. Explain their
scope and thresholds there, without long technical qualifications on every teacher
card. The hero uses the public site's landing composition and the brand wordmark
under SPEC-DES-001 §IX; the footer is the public site's footer. Historical bars
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
exactly `schema_version`, UTC ISO `received_at`, and `checks`. A
`platform-check-v2` record contains exactly one `endpoint`, one `database` and one
`gate` result; a `platform-check-v1` record, written before v2, contains exactly the
first two and is read as carrying no gate evidence. Each result has `key`,
`outcome` (PASS/FAIL/UNKNOWN), `checked_at` (UTC ISO or null), and a closed diagnostic.
Endpoint HTTP_OK is PASS; HTTP_UNAVAILABLE is FAIL. Actual database
DATABASE_REACHABLE is PASS and DATABASE_UNAVAILABLE is FAIL. ACCESS_DENIED,
TRANSPORT_UNAVAILABLE and INVALID_RESPONSE are UNKNOWN for either check;
STALE_SOURCE is additionally permitted for database UNKNOWN. UNKNOWN carries null
checked_at; proven checks preserve their source timestamp, never later than receipt.
Current results expire after 300 seconds; future or malformed evidence is unknown.
A bounded read of the existing health endpoint may obtain these two actual checks
without collecting its feature placeholders. This is connectivity, not domain proof.

The `gate` check observes whether the Application Availability Gate (DOM-OPS-001)
is closed. Outside operational work the application hostname has no Cloudflare
Access policy in front of public pages, so the check sends one bounded GET for a
static public asset on that hostname with **no** service token or other credential,
follows no redirect, and reads only the status line and `Location` header. A
redirect whose `Location` host is a Cloudflare Access login host
(`*.cloudflareaccess.com`) is `GATE_CLOSED` (FAIL). Any other HTTP response — including
an application error, which the endpoint check reports separately — is `GATE_OPEN`
(PASS). An HTTP 401 or 403 is `UNEXPECTED_DENIAL` (UNKNOWN), because a public asset is
never denied when the gate is open and the gate's own response is not otherwise
established. Transport failure is `TRANSPORT_UNAVAILABLE` (UNKNOWN). The service-token
health read cannot stand in for this check: there `ACCESS_DENIED` also describes a
lapsed or revoked monitoring credential, so it remains UNKNOWN and never implies the
gate is closed. A closed gate is an access restriction, not an application failure,
and never contributes FAIL to the endpoint or database results.

`platform_observations` retains append-only records for seven days using `expires_at`;
`platform_current/current` is a monotonic replaceable projection. Reads are pure.
These records do not contribute to request-window history or service-card proofs.

## IX. Validation

Focused tests cover strict schema/redaction, query failure, malformed/multi-series
responses, no/low traffic, thresholds and their boundaries, 404 versus semantic
failure, stale/future timestamps, retry idempotency, monotonic current pointer,
UTC rollover, history denominators/gaps, independent notices, auth/CSRF and pure
GET. Gate tests cover an Access redirect, an open response, an application error,
401/403, transport failure, and a lapsed service token with an open gate. Render
populated/idle/stale history and cards for keyboard/touch access.
A deployed claim requires source → collector → Firestore → rendered evidence.

## X. Amendment

Increment version, update date and documentation index, and review changes against
DOM-OPS-001. No amendment may relax internal verification or privacy authority.
