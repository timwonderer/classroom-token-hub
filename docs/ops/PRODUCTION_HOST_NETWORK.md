# Production host network exposure

**Descriptive operations record, not a normative document.** Governing authority for
application admission is `DOM-OPS-001` (Cloudflare Access is the sole infrastructure
gate) and `SOP-DEP-002`. This page records how the production host is exposed, what was
changed on 2026-09-27, and what has to stay true.

Last verified: 2026-09-27, app revision `26d1792b5`.

**This is the public, de-identified form.** The repository is public, so this page
carries the layers, the rules and the drift checks, but not the identifiers an attacker
would use to find or map the origin: its public address, host and Tailscale names, the
DigitalOcean droplet and firewall IDs, the per-port listener inventory, and host
configuration paths. Those are held in the operator's private infrastructure record.
Commands below use placeholders (`<prod-host>`, `<droplet-id>`, `<cloudflare-firewall-id>`,
`<origin-ipv4>`) for them. Earlier revisions of this file in git history carry the
identifying version (removed 2026-09-29; history was not rewritten).

## Layers, outermost first

| Layer | What it admits | Where it is configured | In git? |
|---|---|---|---|
| Cloudflare proxy and Access | `app.classroomtokenhub.com` over HTTPS; Access policy while gated | Cloudflare dashboard | No |
| DigitalOcean cloud firewall `Cloudflare` | TCP 80 and 443 from Cloudflare's published ranges only; nothing else inbound | DigitalOcean console | No (rules recorded below) |
| Tailscale | Tailnet devices, including CI (`tag:ci`) for releases and SSH | Tailscale admin console | No |
| nginx | 80 → 301 to HTTPS; 443 → the app on loopback, and Grafana on loopback behind an `auth_request` to the app | Host nginx configuration | No |

The cloud firewall is the layer that decides what the public internet can reach. So
every monitoring and application service binds to loopback (next section), and nothing
depends on a host-level firewall to stay private. SSH is reached over Tailscale; public
access to port 22 is closed by the cloud firewall.

## DigitalOcean cloud firewall

Read with `doctl compute firewall list -o json` on 2026-09-27.

**`Cloudflare`** (created 2025-11-27):

- Inbound TCP 80 and TCP 443 from 22 source ranges. They match Cloudflare's published
  list exactly (`https://www.cloudflare.com/ips-v4`, `/ips-v6`, fetched the same day):
  `103.21.244.0/22`, `103.22.200.0/22`, `103.31.4.0/22`, `104.16.0.0/13`, `104.24.0.0/14`,
  `108.162.192.0/18`, `131.0.72.0/22`, `141.101.64.0/18`, `162.158.0.0/15`,
  `172.64.0.0/13`, `173.245.48.0/20`, `188.114.96.0/20`, `190.93.240.0/20`,
  `197.234.240.0/22`, `198.41.128.0/17`, `2400:cb00::/32`, `2405:8100::/32`,
  `2405:b500::/32`, `2606:4700::/32`, `2803:f800::/32`, `2a06:98c0::/29`, `2c0f:f248::/32`.
- No other inbound rule, so SSH (22) and every other port are closed publicly. The
  public probe in the next section observed exactly that.
- Outbound: all TCP, UDP and ICMP.

A second firewall attached to the droplet has no inbound rules and allows all outbound.

**This firewall protects the production droplet.** That is established in
`docs/ops/audits/PROD_AUDIT_2026-07-01.md` (addendum: the droplet sits behind a
DigitalOcean cloud firewall admitting 80 and 443 only from Cloudflare's ranges), and the
2026-09-27 probe below behaves exactly as its rules predict. The API confirms it too:
`doctl compute firewall list-by-droplet <droplet-id>` (the ID comes from the droplet's
metadata service) returns `Cloudflare` and the second firewall. A scoped token may be
unable to read the droplet itself (403), and the plain firewall listing then shows
`droplet_ids: []`, so use `list-by-droplet` to check attachment.

Tailscale needs no inbound rule: it connects outbound and falls back to relays.

## Host listeners

After the 2026-09-27 change, only three things listen on a non-loopback address:

| Listener | Why it is not loopback |
|---|---|
| nginx, TCP 80 and 443 | The public entry point |
| sshd, TCP 22 | Reached over Tailscale; blocked publicly by the `Cloudflare` cloud firewall, and the public probe of 22 times out |
| tailscaled | Tailscale itself |

Everything else listens on `127.0.0.1` only: the application (gunicorn), Grafana,
Prometheus, node-exporter, process-exporter, Loki and Promtail. The port-by-port
inventory and the configuration file that sets each binding are in the operator's
private infrastructure record.

### What changed on 2026-09-27

Prometheus, both exporters, Loki and Promtail listened on every interface, and no
host-level firewall filtered them. The cloud firewall kept them off the public internet,
but every tailnet device could reach them, and any change to the cloud firewall would
have exposed them. Nothing outside the host used them: Prometheus scrapes `localhost`,
Grafana reads its Prometheus and Loki datasources on loopback, and Promtail pushes to
Loki on `localhost`. So all five now bind to `127.0.0.1`. Scrape targets were left as
`localhost:*` so existing dashboard filters (`instance="localhost:…"`) keep matching.
Go's dialer tries `::1` first and falls back to `127.0.0.1`.

The previous configuration files are kept on the host beside the edited ones as dated
`.bak` copies. The process-exporter change is a systemd drop-in, so deleting it restores
the unit's own all-interfaces listen address.

**Verified after the change:**

- **Scrapes:** all four Prometheus targets (`cth_app`, `node`, `process`, `prometheus`) report `up` on the next 60-second scrape.
- **Ingest:** Loki kept ingesting (557 lines in the first minute).
- **Promtail:** its only error was `context canceled` from the old process shutting down during the restart.
- **Loki `/ready`:** returned 503 both before and after the change. That predates the change and is unrelated.

**Probed after the change** (from an off-host workstation, HTTP to each port):

| Port | From the public internet | From the tailnet |
|---|---|---|
| Every monitoring port, Grafana and the app's loopback port | timeout (filtered) | refused (nothing listening) |
| 443 | timeout (filtered; the workstation is not a Cloudflare address) | open |
| 22 | timeout (filtered; probed before the change at ~15:58 UTC) | open (sshd) |

The public column is the `Cloudflare` firewall at work: only Cloudflare's ranges reach
80 and 443, and nothing else is admitted.

The tailnet reaches nginx on 443 directly, without Cloudflare Access. That is how
operators and CI reach the origin (`SOP-DEP-002` §VI: host-local probes do not traverse
Access), and it is limited to tailnet devices.

Also on 2026-09-27, nginx began sending `X-CF-Edge-IP $realip_remote_addr` to the app, for
application traffic and for the Grafana `auth_request` subrequest. The application's
Cloudflare-origin check has preferred that header since 2026-09-19.

## Drift expectations

These must stay true. Each line is a read-only check.

1. **Only nginx, sshd and Tailscale listen off loopback.**
   `ssh <prod-host> 'ss -ltunH | awk "{print \$1, \$5}" | grep -vE " (127\.|\[::1\])"'`
   lists TCP and UDP listeners off loopback. It should show only nginx's `:80` and
   `:443`, sshd's `:22`, and Tailscale's own listeners. A new service goes on `127.0.0.1`
   unless something off-host genuinely needs it, and then that need is written in the
   operator's private infrastructure record and summarised here.
2. **The cloud firewall admits only Cloudflare to 80 and 443.** Its source list should
   equal Cloudflare's published ranges. Cloudflare changes them rarely but does change
   them. Compare `doctl compute firewall get <cloudflare-firewall-id>` against
   `https://www.cloudflare.com/ips-v4` and `ips-v6`. nginx's `set_real_ip_from` list must
   track the same ranges, or real-client IPs and rate limiting go wrong.

   **Fixed on 2026-09-27.** nginx's list lacked `131.0.72.0/22` and `2c0f:f248::/32`,
   which the firewall admits. Visitors on those ranges were seen as the Cloudflare edge
   address and rate-limited as one client. Both ranges were added at 16:14 UTC (the prior
   file kept as a dated backup; `nginx -t`, then a reload). The list now equals
   Cloudflare's published ranges plus `100.64.0.0/10`, the Tailscale address block. That
   entry is deliberate: the file marks it as the admin access path. It lets a tailnet
   device set its apparent client address with `CF-Connecting-IP`, which is acceptable
   because only tailnet devices can do it.
3. **Public probes time out.** From a non-Cloudflare, non-tailnet address, every port
   including 443 on `<origin-ipv4>` should time out. A `refused` or an answer means the
   cloud firewall changed.
4. **The firewall stays attached to the production droplet.**
   `doctl compute firewall list-by-droplet <droplet-id>` should list `Cloudflare`. Check 3
   also catches a detachment from outside.

None of these checks runs automatically yet. The nginx configuration and these rules
are not in git, so the host, the DigitalOcean console and the operator's private
infrastructure record are the only record of them. This page is the reviewed public
description.

## Deferred

- **A host firewall.** It would add a layer only against the cloud firewall being
  changed or detached. With every non-web service on loopback it no longer guards any
  known exposure, so it is left as a later hardening decision.
- **Narrowing sshd's listen address to the Tailscale interface.** Low value while the
  cloud firewall blocks 22, and a mistake costs console access.
- **nginx configuration in git, with a drift check in the release workflow.** Proposed
  separately.
