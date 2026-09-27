# Production host network exposure

**Descriptive operations record, not a normative document.** Governing authority for
application admission is `DOM-OPS-001` (Cloudflare Access is the sole infrastructure
gate) and `SOP-DEP-002`. This page records how the production host is actually exposed,
what was changed on 2026-09-27, and what has to stay true.

Last verified: 2026-09-27, against host `app-server` (Tailscale name `cth`, public IPv4
`24.199.127.184`), app revision `26d1792b5`.

## Layers, outermost first

| Layer | What it admits | Where it is configured | In git? |
|---|---|---|---|
| Cloudflare proxy and Access | `app.classroomtokenhub.com` over HTTPS; Access policy while gated | Cloudflare dashboard | No |
| DigitalOcean cloud firewall `Cloudflare` | TCP 80 and 443 from Cloudflare's published ranges only; nothing else inbound | DigitalOcean console | No (rules recorded below) |
| Tailscale | Tailnet devices, including CI (`tag:ci`) for releases and SSH | Tailscale admin console | No |
| nginx | 80 → 301 to HTTPS; 443 → `127.0.0.1:8000` (app) and `127.0.0.1:3000` (Grafana, behind an `auth_request` to the app) | `/etc/nginx/sites-available/classroom`, `/etc/nginx/conf.d/*.conf` | No |
| Host firewall (`ufw`) | Inactive | — | — |

The cloud firewall is the only layer between the public internet and anything that
listens on a public interface, so the host keeps every non-web service off those
interfaces (next section).

## DigitalOcean cloud firewall

Read with `doctl compute firewall list -o json` on 2026-09-27.

**`Cloudflare`** (`6e7b042e-c075-4eb8-96c2-2504c4133c2e`, created 2025-11-27):

- Inbound TCP 80 and TCP 443 from 22 source ranges. They match Cloudflare's published
  list exactly (`https://www.cloudflare.com/ips-v4`, `/ips-v6`, fetched the same day):
  `103.21.244.0/22`, `103.22.200.0/22`, `103.31.4.0/22`, `104.16.0.0/13`, `104.24.0.0/14`,
  `108.162.192.0/18`, `131.0.72.0/22`, `141.101.64.0/18`, `162.158.0.0/15`,
  `172.64.0.0/13`, `173.245.48.0/20`, `188.114.96.0/20`, `190.93.240.0/20`,
  `197.234.240.0/22`, `198.41.128.0/17`, `2400:cb00::/32`, `2405:8100::/32`,
  `2405:b500::/32`, `2606:4700::/32`, `2803:f800::/32`, `2a06:98c0::/29`, `2c0f:f248::/32`.
- No other inbound rule, so SSH (22) and every other port are closed publicly.
- Outbound: all TCP, UDP and ICMP.

**`Local-Workstation`** (`57af9a74-…`): no inbound rules; outbound all.

**Attachment is not confirmed through the API.** The local `doctl` token is scoped to
firewall reads: the firewall listing shows `droplet_ids: []` and `tags: []`, and droplet
and account reads return 403. Behaviour matches the `Cloudflare` rule set exactly (see
the probe below: from a non-Cloudflare address, even 443 on the origin IP times out), but
which firewall is attached should be confirmed in the DigitalOcean console or with a
token that can read droplets.

Tailscale needs no inbound rule: it connects outbound and falls back to relays.

## Host listeners

After the 2026-09-27 change, `ss -ltnp` shows only these on a non-loopback address:

| Address | Process | Why it is not loopback |
|---|---|---|
| `0.0.0.0:80`, `0.0.0.0:443` | nginx | The public entry point |
| `0.0.0.0:22`, `[::]:22` | sshd | Reached over Tailscale; blocked publicly by the cloud firewall. Rebinding to the Tailscale address was not done: a mistake would need the DigitalOcean console to recover. |
| Tailscale addresses, UDP 41641 | tailscaled | Tailscale itself |

Everything else listens on `127.0.0.1`:

| Service | Address | Configured in |
|---|---|---|
| gunicorn (app) | `127.0.0.1:8000` | systemd unit `classroom-economy` |
| Grafana | `127.0.0.1:3000` | Grafana config |
| Prometheus | `127.0.0.1:9090` | `/etc/default/prometheus` (`--web.listen-address`) |
| node-exporter | `127.0.0.1:9100` | `/etc/default/prometheus-node-exporter` |
| process-exporter | `127.0.0.1:9256` | drop-in `/etc/systemd/system/process-exporter.service.d/listen-localhost.conf` |
| Loki | `127.0.0.1:3100` (HTTP), `127.0.0.1:9096` (gRPC) | `/etc/loki/config.yml` (`server.http_listen_address`, `grpc_listen_address`) |
| Promtail | `127.0.0.1:9080` (HTTP), `127.0.0.1:<random>` (gRPC) | `/etc/promtail/config.yml` |

### What changed on 2026-09-27

Prometheus, both exporters, Loki and Promtail listened on every interface, and `ufw` is
inactive. The cloud firewall kept them off the public internet, but every tailnet
device could reach them, and any change to the cloud firewall would have exposed them.
Nothing outside the host used them. Prometheus scrapes `localhost`, Grafana reads
`localhost:9090` and `127.0.0.1:3100`, and Promtail pushes to `localhost:3100`. So all
five now bind to `127.0.0.1`. Scrape targets were left as `localhost:*` so existing
dashboard filters (`instance="localhost:9100"`) keep matching. Go's dialer tries `::1`
first and falls back to `127.0.0.1`.

The previous files are kept beside the edited ones as `*.bak-20260927T160657Z`. The
process-exporter change is a drop-in, so deleting it restores the unit's own
`--web.listen-address=:9256`.

**Verified after the change:**

- **Scrapes:** all four Prometheus targets (`cth_app`, `node`, `process`, `prometheus`) report `up` on the next 60-second scrape.
- **Ingest:** Loki kept ingesting (557 lines in the first minute).
- **Promtail:** its only error was `context canceled` from the old process shutting down during the restart.
- **Loki `/ready`:** returned 503 both before and after the change. That predates the change and is unrelated.

**Probed after the change** (from an off-host workstation, HTTP to each port):

| Port | From the public internet | From the tailnet |
|---|---|---|
| 9090, 9100, 9256, 3100, 9096, 9080, 3000, 8000 | timeout (filtered) | refused (nothing listening) |
| 443 | timeout (filtered; the workstation is not a Cloudflare address) | open |

The tailnet reaches nginx on 443 directly, without Cloudflare Access. That is how
operators and CI reach the origin (`SOP-DEP-002` §VI: host-local probes do not traverse
Access), and it is limited to tailnet devices.

Also on 2026-09-27, nginx began sending `X-CF-Edge-IP $realip_remote_addr` to the app, in
`location /` and the Grafana `auth_request` block (backup
`/etc/nginx/sites-available/classroom.bak-20260927T155606Z`). The application's
Cloudflare-origin check has preferred that header since 2026-09-19.

## Drift expectations

These must stay true. Each line is a read-only check.

1. **Only nginx, sshd and Tailscale listen off loopback.**
   `ssh cth 'ss -ltnH | awk "{print \$4}" | grep -vE "^(127\.|\[::1\])"'` should list
   only `:80`, `:443`, `:22` and Tailscale addresses. A new service goes on `127.0.0.1`
   unless something off-host genuinely needs it, and then that need is written here.
2. **The cloud firewall admits only Cloudflare to 80 and 443.** Its source list should
   equal Cloudflare's published ranges. Cloudflare changes them rarely but does change
   them. Compare `doctl compute firewall get 6e7b042e-c075-4eb8-96c2-2504c4133c2e`
   against `https://www.cloudflare.com/ips-v4` and `ips-v6`. nginx's
   `/etc/nginx/conf.d/cloudflare-realip.conf` (`set_real_ip_from`) must track the same
   list, or real-client IPs and rate limiting go wrong.

   **Fixed on 2026-09-27.** nginx's list lacked `131.0.72.0/22` and `2c0f:f248::/32`,
   which the firewall admits. Visitors on those ranges were seen as the Cloudflare edge
   address and rate-limited as one client. Both ranges were added at 16:14 UTC (backup
   `/root/cloudflare-realip.conf.bak-20260927T161412Z`; `nginx -t`, then a reload). The
   list now equals Cloudflare's published ranges plus `100.64.0.0/10`, the Tailscale
   address block. That entry is deliberate: the file marks it as the admin access path.
   It lets a tailnet device set its apparent client address with `CF-Connecting-IP`,
   which is acceptable because only tailnet devices can do it.
3. **Public probes time out.** From a non-Cloudflare, non-tailnet address, every port
   including 443 on `24.199.127.184` should time out. A `refused` or an answer means the
   cloud firewall changed.
4. **The firewall is attached to the production droplet.** Confirm in the console after
   any droplet or firewall change. The local token cannot see attachments (above).

None of these checks runs automatically yet. The nginx configuration and these rules
are not in git, so the host and the DigitalOcean console are the only record of them.
This page is the reviewed description.

## Deferred

- **`ufw`.** A host firewall would add a layer only against the cloud firewall being
  changed or detached. With every non-web service on loopback it no longer guards any
  known exposure, so it is left as a later hardening decision.
- **sshd bound to the Tailscale address only.** Low value while the cloud firewall
  blocks 22, and a mistake costs console access.
- **nginx configuration in git, with a drift check in the release workflow.** Proposed
  separately.
