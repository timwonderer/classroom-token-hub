# Host upgrade: Tailscale 1.102.4 → 1.104.2, 2026-10-24

A host package upgrade outside a release. No application code, migration or configuration changed, and the
application was not stopped.

| | |
|---|---|
| Trigger | Tailscale bulletin TS-2026-013 (2026-10-21): Tailscale 1.104.2, built with Go 1.27.3, distrusts the compromised eMudhra certificate authorities even where the host OS still trusts them. TLS validation only; WireGuard traffic between nodes is unaffected |
| Exploitation | None found. No credentials rotated, no incident declared |
| CI side | PR #1664 (merge `9614dd071`) moved `release-v2.yml`, `login-notice.yml` and `tailscale-ssh-smoke-test.yml` to `tailscale/github-action` v4.3.0, whose default client is 1.104.2 (v4.2.0 defaulted to 1.94.2). Smoke test on `main`: [run 39981138068](https://github.com/timwonderer/classroom-token-hub/actions/runs/39981138068), resolved 1.104.2, success |
| Host before | Ubuntu 22.04.5; Tailscale 1.102.4 (Go 1.26.6); apt candidate 1.104.2 |
| Timing | Held until after school hours (owner, 2026-10-23); run 2026-10-24 02:36 UTC |
| Droplet snapshot | Taken by the owner in the DigitalOcean panel before the upgrade as a break-glass; deleted 2026-10-24 once the checks below passed, since it holds the database and `.env` |
| Command | `ssh root@cth 'nohup sh -c "apt-get update && apt-get install -y --only-upgrade tailscale" >/root/tailscale-upgrade.log 2>&1 &'`, run by the owner with the DigitalOcean console as the fallback path |
| Upgrade | dpkg: `upgrade tailscale:amd64 1.102.4 1.104.2` at 02:36:35; `tailscaled` active again at 02:36:38. needrestart: no further services, sessions or guests outdated |
| Host after | `tailscale version` 1.104.2; `tailscaled` and `classroom-economy` active; `127.0.0.1:8000/health` `ok` |
| Listeners off loopback | Only nginx `:80`/`:443`, sshd `:22` and Tailscale, matching `docs/ops/PRODUCTION_HOST_NETWORK.md` drift check 1 |
| CI transport after | Smoke test on `main`: [run 40054931243](https://github.com/timwonderer/classroom-token-hub/actions/runs/40054931243), success |
| Verification | Checks run by an AI assistant; advisory under `SOP-DEP-001` §XIII |

## Follow-ups

- [#1665](https://github.com/timwonderer/classroom-token-hub/issues/1665): Tailscale is outside `unattended-upgrades`, and the `cth` node key expires in about five months.
