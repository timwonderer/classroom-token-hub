---
title: Attended staging workflow
category: self-hosting
description: Dispatch, exact-ID teardown and owner recovery for one temporary staging host.
roles: [operator]
---

# Attended staging workflow

The infrastructure owner runs a single exercise from GitHub Actions and closes it in DigitalOcean. Use the [Phase C approval plan](phase-c.md), [workflow configuration](https://github.com/timwonderer/classroom-token-hub/blob/main/infra/staging/README.md) and [guest preparation instructions](staging-bootstrap.md).

1. In DigitalOcean, confirm the preceding exercise has been cleared. In Actions, manually dispatch the reviewed staging workflow with the approved full release SHA and reference profile. Keep the Actions run link.
2. Watch allocation. Record the numeric Droplet ID as soon as the provider returns it. If the response is lost, leave allocation unresolved and inspect the console before another dispatch.
3. Verify the new guest's SSH identity through the authenticated DigitalOcean console, then release the staging installation inputs. The workflow invokes the same B2 installer as a self-hosting operator. Keep raw logs, credentials, authentication material and classroom records out of Actions evidence.
4. After successful installation, leave the first-use environment waiting while you complete the [handbook checks](operations.md). Record results privately. Approve after success or reject after failure or an early stop.
5. After the decision or an installation failure, review the cleanup job. It can request destruction only for the recorded Droplet ID after checking ownership. Runner loss or cancellation can interrupt that job. A green job alone does not close the exercise.

## Manual recovery

Open the staging team and project in the DigitalOcean console. Match the Actions run to the provider's create activity, timestamp and actual numeric ID. The run label helps locate a candidate. Confirm ownership independently of the label before destroying it. If records are ambiguous, preserve the candidates, investigate with the provider and leave the exercise open.

Destroy the identified remaining staging Droplet and verify it is absent. Check the project's ancillary resources and retire run-specific credentials. Record the run link, confirmed resource ID if available, final disposition and time of the owner's check. The permanent production app-server is outside this procedure.
