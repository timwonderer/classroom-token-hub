# App health collector activation

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
   `cth-status-prod`. The collector carries no Cloudflare Access credential
   (`SPEC-OPS-006` 1.6): the health endpoints are public, and while the Access
   gate is closed it reads nothing from the application. The identity needs no
   Secret Manager access; remove any grant on `cth-status-cf-access-client-id`
   or `cth-status-cf-access-client-secret` left from before 1.6.
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
   is an explicit operator action; no workflow deployment
   implicitly starts collection.
4. Execute the job once manually and inspect the execution state and bounded
   observations in `cth-status-prod`. Check that with the Access gate closed the
   run stores only the gate check (`GATE_CLOSED`), with the endpoint and database
   `NOT_COLLECTED` and no request telemetry, that a valid response has one
   correlation ID across its signals, and that the public projection does not
   declare unevaluated capabilities healthy. Then enable the Scheduler job.

If any prerequisite fails, leave the GitHub variable unset or false and keep
the Scheduler job disabled. Do not publish a healthy app status from missing
or stale observations.

## Request-billed collector service migration

This is a separate operator cutover. The existing Job and Scheduler continue to
collect while the replacement is prepared. The service uses the same image,
`status-probe` identity, Firestore database, and collector
logic. Its only application route is `POST /collect`; Cloud Run admits only
authenticated internal traffic. The service returns HTTP 204 after both
telemetry and platform writes complete. A storage error returns HTTP 500 so
Scheduler can retry. A source fetch failure remains bounded unavailable evidence,
as required by `SPEC-OPS-006`.

1. Confirm the deployment identity may deploy a Cloud Run service as
   `status-probe` and set its invoker policy. Set GitHub production variable
   `STATUS_COLLECTOR_SERVICE_ENABLED=true`, then let the next status workflow
   deploy `cth-status-collector`. Its verification step must pass. No workflow
   step changes the Scheduler target. Confirm the service reports `internal`
   ingress, no `allUsers` or `allAuthenticatedUsers` invoker, request-based
   billing, one vCPU, 512 MiB, zero minimum instances, and the probe identity.
   Keep the Job deployment
   variable enabled until after the cutover has proved stable.
2. Get the service's default `run.app` URL and grant
   `status-scheduler@cth-production-status.iam.gserviceaccount.com`
   `roles/run.invoker` on **this service only**. Read back the policy before
   proceeding:

   ```bash
   SERVICE_URL=$(gcloud run services describe cth-status-collector --region us-west2 --project cth-production-status --format='value(status.url)')
   gcloud run services add-iam-policy-binding cth-status-collector --region us-west2 --project cth-production-status --member='serviceAccount:status-scheduler@cth-production-status.iam.gserviceaccount.com' --role='roles/run.invoker'
   gcloud run services get-iam-policy cth-status-collector --region us-west2 --project cth-production-status
   ```

3. Save the current Scheduler job configuration privately and confirm its
   location, schedule, retry policy, and 180-second deadline. Pause the existing
   `cth-status-app-health-collector` Scheduler job, then switch its HTTP target
   to `<service-url>/collect` and authentication to OIDC. Use the root service
   URL (without `/collect`) as the OIDC audience. These commands assume the
   current Scheduler location is `us-west2`; use the location from the saved
   configuration if different:

   ```bash
   gcloud scheduler jobs describe cth-status-app-health-collector --location us-west2 --project cth-production-status --format=json
   gcloud scheduler jobs pause cth-status-app-health-collector --location us-west2 --project cth-production-status
   gcloud scheduler jobs update http cth-status-app-health-collector --location us-west2 --project cth-production-status --uri="$SERVICE_URL/collect" --http-method=POST --oidc-service-account-email=status-scheduler@cth-production-status.iam.gserviceaccount.com --oidc-token-audience="$SERVICE_URL" --attempt-deadline=180s
   gcloud scheduler jobs describe cth-status-app-health-collector --location us-west2 --project cth-production-status --format=json
   gcloud scheduler jobs resume cth-status-app-health-collector --location us-west2 --project cth-production-status
   ```

   Check the `describe` output reports `PAUSED` before resuming. Cloud
   Scheduler rejects a forced run while paused. Observe the next scheduled run
   and confirm it received HTTP 204. Check a new `telemetry_snapshots` minute
   (or a bounded `telemetry_attempts` failure), a new `platform_observations`
   entry, current pointers, and the rendered public page. A 204 alone does not
   establish that source evidence was available.

4. Observe at least five consecutive scheduled minutes. Verify no missing or
   duplicated source-minute history, current platform freshness, and no
   unexpected retries. Only then leave the Job unused for rollback. A later
   cleanup can remove the old Job and disable its deployment flag after the
   service has remained stable.

Rollback: pause the Scheduler job, restore the saved Job API URI and OAuth
`cloud-platform` token configuration, confirm it remains paused, then resume
the minute schedule:

```bash
gcloud scheduler jobs pause cth-status-app-health-collector --location us-west2 --project cth-production-status
gcloud scheduler jobs update http cth-status-app-health-collector --location us-west2 --project cth-production-status --uri='https://run.googleapis.com/v2/projects/cth-production-status/locations/us-west2/jobs/cth-status-app-health-collector:run' --http-method=POST --oauth-service-account-email=status-scheduler@cth-production-status.iam.gserviceaccount.com --oauth-token-scope=https://www.googleapis.com/auth/cloud-platform --attempt-deadline=180s
gcloud scheduler jobs describe cth-status-app-health-collector --location us-west2 --project cth-production-status --format=json
gcloud scheduler jobs resume cth-status-app-health-collector --location us-west2 --project cth-production-status
```

Verify the next scheduled Job run and fresh Firestore evidence after resuming.

Keep the old Job provisioned during this period. Do not rewrite retained
snapshots, attempts, or platform observations.

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
