# App health collector activation (prelaunch)

This setup implements bounded external observation under `DOM-OPS-001`,
`SPEC-OPS-002`, and `SOP-OPS-001`. The collector does not create canonical
incidents or access tenant data. This document is an operator setup step, not
evidence that the infrastructure is provisioned or running.

1. Confirm the Cloud Run job identity
   `status-probe@cth-production-status.iam.gserviceaccount.com` has only the
   dedicated scoped Firestore role granting `datastore.databases.get` (required
   to begin and roll back transactions), `datastore.entities.create`,
   `datastore.entities.get`, `datastore.entities.list`, and
   `datastore.entities.update`, with a condition restricting access to database
   `cth-status-prod`, and Secret Manager version access to
   `cth-status-cf-access-client-id` and `cth-status-cf-access-client-secret`.
   Confirm each latest secret version is enabled and has a nonblank value.
   Do not display their payloads in logs or command output.
2. Confirm the deployment identity can deploy Cloud Run jobs and act as the
   probe identity. Set the GitHub production environment variable
   `STATUS_APP_HEALTH_COLLECTOR_ENABLED` to `true` only after these checks.
   The next status workflow deployment creates or updates
   `cth-status-app-health-collector` from the same image as the status services.
   It does not execute the job.
3. Create a dedicated Scheduler caller identity with permission to execute
   only this Cloud Run job. Configure an authenticated Cloud Scheduler HTTP
   request with method `POST`, a one-minute schedule (`* * * * *`), and OAuth scope
   `https://www.googleapis.com/auth/cloud-platform`. The request target is
   `https://run.googleapis.com/v2/projects/cth-production-status/locations/us-west2/jobs/cth-status-app-health-collector:run`.
   Do this after inspecting the deployed job configuration. Scheduler creation
   is an explicit operator action; no secret reference or workflow deployment
   implicitly starts collection.
4. Execute the job once manually and inspect the execution state and bounded
   observations in `cth-status-prod`. Check that a denied Access request yields
   unknown/unavailable capability evidence, that a valid response has one
   correlation ID across its signals, and that the public projection does not
   declare unevaluated capabilities healthy. Then enable the Scheduler job.

If any prerequisite fails, leave the GitHub variable unset or false and keep
the Scheduler job disabled. Do not publish a healthy app status from missing
or stale observations.

## App evidence protocol rollout

The app and status service deploy independently. The v2 health payload adds a
per-signal `checked_at` timestamp so a collector receipt cannot make an old
app result fresh. Receipt time orders observations; the original check time
governs freshness. The collector also preserves application-origin evidence separately
from the collector's own reachability probe. The collector rejects the old
signal shape. During a mixed-version rollout, app-derived signals therefore
become `UNKNOWN` (not healthy) until both sides serve v2.

Before declaring the rollout complete, verify the app's `/health/status`
returns `checked_at` for the database check and null for unregistered
features, run the collector, then verify Firestore keeps
`APPLICATION_RUNTIME_EVIDENCE` for app signals and `EXTERNAL_PROBE` for
`public_service_reachability`. Confirm the public page still shows unregistered
features as Unknown and does not treat an old feature check as fresh. Do not
call feature-health evaluation complete merely because this transport is
working; owning-domain evidence producers are separate work.
