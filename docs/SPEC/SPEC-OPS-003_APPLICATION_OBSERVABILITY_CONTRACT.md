# SPEC-OPS-003: Application Observability Contract

| Field | Value |
|---|---|
| Identifier | SPEC-OPS-003 |
| Version | 1.0 |
| Status | Normative |
| Authority | DOM-OPS-001; Batch B Operations Verifier Policy Decision Package |
| Date | 2026-09-04 |

## I. Purpose

This specification defines the bounded application telemetry CTH may emit for
operational observation. It supplies evidence to Prometheus and Grafana; it
does not define Ledger truth, business-domain policy, or public status
directly.

The evidence path is:

```text
HTTP route / FEAT execution
        ↓
approved capability key
        ↓
bounded operational outcome
        ↓
Prometheus
        ↓
Grafana telemetry
        ↓
closed status evidence adapter
        ↓
DOM-OPS capability projection
```

## II. Capability boundary

Every emitted application series MUST map to one capability key from the
closed Operations capability registry. The mapping is maintained by an
implementation registry; this document does not enumerate every Flask route.

The approved capability keys are:

- `public_service_reachability` — whether the public service can serve the
  applicable request path;
- `dependency_readiness` — whether an approved dependency is ready;
- `ledger_correctness` — reserved for Ledger proof surfaces, not ordinary
  request telemetry;
- `production_telemetry` — bounded operational telemetry evidence;
- `audit_integrity` — reserved for the canonical audit-lineage verifier.

Internal-only routes and FEATs MAY emit telemetry for operator diagnosis, but
MUST be marked non-public and MUST NOT be mapped to a public capability unless
the capability registry authorizes that mapping.

## III. Operational outcome vocabulary

Application execution telemetry uses this closed outcome vocabulary:

- `SUCCESS` — the route or FEAT completed its authorized operation;
- `EXPECTED_DENIAL` — the application deliberately rejected the request under
  an existing domain, authorization, validation, or economic rule;
- `SYSTEM_FAILURE` — execution could not complete because of an unhandled
  application, infrastructure, dependency, or persistence failure.

HTTP status alone MUST NOT determine this classification. In particular,
`403`, `409`, `422`, and other client-visible denials are not system failures
unless the owning route/FEAT contract identifies an execution failure.

An expected denial is positive evidence that the applicable rule was
enforced. It MUST NOT increase an operational failure metric.

## IV. Observation boundary

Each route or FEAT execution MUST be classified exactly once at its canonical
execution boundary. Instrumentation MUST wrap the boundary that owns the
outcome, rather than adding independent counters throughout domain helpers.

The implementation MUST preserve the existing execution behavior. Telemetry
failure MUST NOT change the result, transaction boundary, authorization,
rollback behavior, or user-visible business outcome.

## V. Metric contract

The implementation MAY expose the following metric families:

```text
cth_http_requests_total{
    capability,
    method,
    outcome
}

cth_http_request_duration_seconds{
    capability,
    method
}

cth_feat_executions_total{
    capability,
    feat_code,
    outcome
}
```

The exact implementation registry MUST use only closed values for `capability`,
`method`, `feat_code`, and `outcome`. `feat_code` MUST identify a bounded
canonical FEAT family, not a request, transaction, or user instance.

The following labels and values are prohibited:

- `class_id`, `seat_id`, `user_id`, or any tenant/identity identifier;
- request, correlation, transaction, reservation, or trace identifiers;
- exception text, stack traces, denial reasons, URLs with parameters, or raw
  payload values;
- arbitrary labels supplied by a caller.

Metrics MUST be safe for Prometheus cardinality and MUST NOT contain PII,
financial values, or tenant-specific business state.

## VI. Status eligibility

Application telemetry is operational evidence only. It MUST flow through the
Grafana telemetry adapter as a bounded `Observation` with
`EvidenceSource.GRAFANA_TELEMETRY` before it participates in a DOM-OPS
projection.

Telemetry MUST NOT directly create a public incident, canonical incident, or
Operational Truth. Grafana telemetry and Ledger verifier evidence remain
distinct sources. If they disagree, the projection rules in SPEC-OPS-002 and
the Batch B policy package apply; telemetry MUST NOT overwrite or reinterpret
Ledger evidence.

## VII. Required validation

Before a telemetry query enters the closed registry, focused tests MUST prove:

1. a successful route/FEAT increments `SUCCESS`;
2. an expected business denial increments `EXPECTED_DENIAL` and not
   `SYSTEM_FAILURE`;
3. an unhandled execution failure increments `SYSTEM_FAILURE`;
4. prohibited identifiers and arbitrary diagnostic values cannot become metric
   labels;
5. telemetry failure does not alter application execution;
6. Prometheus can scrape the bounded exposition endpoint.

The production Grafana query registry MUST be derived only after these
semantics are verified against emitted series.

## VIII. Non-authority and deferrals

This specification does not choose Prometheus retention, Grafana dashboard
layout, Cloud deployment topology, Firestore persistence, public incident
wording, or individual query thresholds. Those decisions belong to the
applicable infrastructure and status specifications.

It also does not authorize inventing a new economic or domain rule. Where a
route or FEAT cannot distinguish `EXPECTED_DENIAL` from `SYSTEM_FAILURE` using
its existing contract, instrumentation MUST stop and the owning authority
must define the distinction first.
