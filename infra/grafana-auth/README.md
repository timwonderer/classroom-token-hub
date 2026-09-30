# Grafana auth redirect: pages only

When `sysadmin.grafana_auth_check` refuses a request under `/sysadmin/grafana/`,
nginx used to answer every such request with `302 /sysadmin/login`. Grafana's
background `fetch` calls follow redirects, so a dashboard tab that outlived its
sysadmin session polled the full login page every 5 seconds (then 429s from the
200/hour limit) and never learned it was signed out.

Now only a page load is redirected; every other request gets a bare `401`. On a
401 Grafana pings `api/login/ping`, gets 401 again and reloads the window
(`public/app/core/services/backend_srv.ts` `loginPing()` →
`contextSrv.setLoggedOut()` → `window.location.reload()`, Grafana 13.2.2). The
reload is a page load, so it is redirected to the login page once and the tab
stops polling. The classification matches `_is_background_request()` in
`app/auth.py`.

The production nginx config is not in this repository. These files are the
reviewed copy of the Grafana part of it, like `infra/status/nginx-telemetry.conf`.

| File | Installs as |
|------|-------------|
| `grafana-auth-redirect-map.conf` | `/etc/nginx/conf.d/grafana_auth_redirect_map.conf` (new) |
| `nginx-grafana.conf` | the Grafana `location` blocks in `/etc/nginx/sites-available/classroom`; only `location @grafana_login_redirect` changes |

## Deploy

1. Install the map file first. The site file refuses to load without it
   (`unknown "grafana_auth_redirect_to_login" variable`).
2. Replace `location @grafana_login_redirect` in the site file with the one in
   `nginx-grafana.conf`.
3. `sudo nginx -t`, then `sudo systemctl reload nginx`.
4. Check: with no sysadmin session,
   `curl -si -H 'Sec-Fetch-Mode: cors' https://app.classroomtokenhub.com/sysadmin/grafana/api/login/ping`
   returns `401` with no `Location`, and the same with `-H 'Sec-Fetch-Mode: navigate' -H 'Accept: text/html'`
   returns `302` to `/sysadmin/login?next=...`.

Known interaction: today `GET /sysadmin/login` removes `user_id` from the
session. The one redirected reload of a stale Grafana tab therefore signs out a
teacher session held in the same browser (before this change the flood of
redirects hit the 200/hour limit, so those requests were mostly 429s instead).
Changing the login route is a separate application change.

Rollback: restore the previous `location @grafana_login_redirect` (a single
`return 302 /sysadmin/login?next=$request_uri;`) and reload. The map file is
harmless to leave in place.

## Test locally

`./test_harness.sh` (or `NGINX_BIN=/path/to/nginx ./test_harness.sh`) runs these
two files in a throwaway nginx against `stub_servers.py` and checks page loads,
fetch/XHR, websocket upgrades, browsers without Fetch Metadata, and authorized
requests. It exits non-zero on any failure.
