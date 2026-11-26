---
title: Attended staging workflow
category: self-hosting
description: Dispatch, exact-ID teardown and owner recovery for one temporary staging host.
roles: [operator]
---

# Attended staging workflow

**Maintainer/rehearsal reference.** This page describes how the project
prepares or records a temporary test installation. It isn't another task list
for teachers to complete. For your own server, follow [the tutorial](README.md).
**Staging** means a separate practice environment; a **rehearsal** is a trial
run used to discover problems before relying on a procedure.

The infrastructure owner runs a single exercise from GitHub Actions and closes it in DigitalOcean. Use the [Phase C approval plan](phase-c.md), [workflow configuration](https://github.com/timwonderer/classroom-token-hub/blob/main/infra/staging/README.md) and [guest preparation instructions](staging-bootstrap.md).

1. In DigitalOcean, confirm the preceding exercise has been cleared. In Actions, manually dispatch the reviewed staging workflow with the approved full release SHA and reference profile. Keep the Actions run link.
2. Watch allocation. Record the numeric Droplet ID as soon as the provider returns it. If the response is lost, leave allocation unresolved and inspect the console before another dispatch.
3. Verify the new guest's SSH identity through the authenticated DigitalOcean console, point the proxied staging A record at its IPv4 address, confirm the firewall attachment, then release the staging installation inputs. The workflow invokes the same B2 installer as a self-hosting operator. Keep raw logs, credentials, authentication material and classroom records out of Actions evidence.
4. After successful installation, leave the first-use environment waiting while you complete the [handbook checks](operations.md). Record results privately. Approve after success or reject after failure or an early stop.
5. After the decision or an installation failure, read the closeout summary. It reports the creation receipt for the operator. If the run was canceled or its summary is missing, reconcile the provider activity directly.

## Operator teardown

Open the enrolled team and staging project in the DigitalOcean console. Match the Actions run to the provider's create activity, timestamp and actual numeric ID. The run label helps locate a candidate. Confirm ownership independently of the label before destroying it. If records are ambiguous, preserve the candidates, investigate with the provider and leave the exercise open.

After the checks and any required recovery evidence are complete, open the confirmed Droplet in DigitalOcean, choose Destroy, and personally confirm the irreversible action. Verify the ID is absent. Check the project's ancillary resources and retire run-specific credentials. Record the run link, confirmed resource ID if available, final disposition and time of the owner's check. The permanent production app-server is outside this procedure.

## Rehearsal with one DigitalOcean team

Use a separate staging project in the existing team. Actions also supports this project arrangement; manual creation avoids placing a team-level token in GitHub. Prepare the [manual proxied HTTPS profile](configuration.md#tls-and-admission-prerequisites) and select a reviewed release that includes it. After explicit approval, the operator creates one temporary Droplet in that project through the console and records its numeric ID. Prepare the private staging EnvironmentFile directly on the new host through the operator’s administrative session; the installer reads and validates it there. No application secrets need to be stored in GitHub for this path. Follow the [reference installation](reference-installation.md) and [first-use checks](operations.md) using staging-only inputs. Use the operator teardown above. This exercises the handbook without placing a team-level token in GitHub. Record the Actions allocation path as untested for this run.
