#!/usr/bin/env bash
# Local check of the Grafana auth redirect rule. Runs the tracked
# grafana-auth-redirect-map.conf and nginx-grafana.conf in a throwaway nginx,
# with stub_servers.py standing in for Flask's auth-check and for Grafana.
# Touches nothing outside a temporary directory.
#
#   infra/grafana-auth/test_harness.sh            # nginx from PATH
#   NGINX_BIN=/path/to/nginx infra/grafana-auth/test_harness.sh
#
# Needs nginx with http_auth_request_module and http_realip_module
# (Homebrew's and Ubuntu's builds have both), curl and python3.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NGINX_BIN="${NGINX_BIN:-nginx}"
# nginx reads $NGINX as a list of inherited sockets; never let it leak in.
unset NGINX
PORT="${PORT:-18480}"
AUTH_PORT="${AUTH_PORT:-18481}"
GRAFANA_PORT="${GRAFANA_PORT:-18482}"
WORK="$(mktemp -d)"
BASE="http://127.0.0.1:${PORT}"

cleanup() {
    [[ -f "$WORK/nginx.pid" ]] && kill "$(cat "$WORK/nginx.pid")" 2>/dev/null || true
    [[ -n "${STUB_PID:-}" ]] && kill "$STUB_PID" 2>/dev/null || true
    rm -rf "$WORK"
}
trap cleanup EXIT

mkdir -p "$WORK/logs"
# Point the production upstreams at the stubs; nothing else is changed.
sed -e "s#http://127.0.0.1:8000#http://127.0.0.1:${AUTH_PORT}#" \
    -e "s#http://127.0.0.1:3000#http://127.0.0.1:${GRAFANA_PORT}#" \
    "$HERE/nginx-grafana.conf" > "$WORK/grafana-locations.conf"

cat > "$WORK/nginx.conf" <<EOF
pid $WORK/nginx.pid;
error_log $WORK/logs/error.log;
events {}
http {
    access_log $WORK/logs/access.log;
    client_body_temp_path $WORK/body;
    proxy_temp_path $WORK/proxy;
    fastcgi_temp_path $WORK/fastcgi;
    uwsgi_temp_path $WORK/uwsgi;
    scgi_temp_path $WORK/scgi;
    include $HERE/grafana-auth-redirect-map.conf;
    server {
        listen 127.0.0.1:${PORT};
        server_name localhost;
        include $WORK/grafana-locations.conf;
        location / { return 404; }
    }
}
EOF

"$NGINX_BIN" -t -p "$WORK" -c "$WORK/nginx.conf"
python3 "$HERE/stub_servers.py" "$AUTH_PORT" "$GRAFANA_PORT" &
STUB_PID=$!
"$NGINX_BIN" -p "$WORK" -c "$WORK/nginx.conf"
for url in "$BASE/" "http://127.0.0.1:${AUTH_PORT}/" "http://127.0.0.1:${GRAFANA_PORT}/"; do
    for _ in $(seq 50); do
        curl -s -o /dev/null "$url" && break
        sleep 0.1
    done
done

FAILED=0
# check NAME EXPECTED_STATUS EXPECTED_LOCATION(or "-" for none) PATH [curl args...]
check() {
    local name="$1" want_status="$2" want_location="$3" path="$4"
    shift 4
    local headers status location
    headers="$(curl -s -o /dev/null -D - "$@" "$BASE$path")"
    status="$(printf '%s' "$headers" | head -1 | awk '{print $2}')"
    location="$(printf '%s' "$headers" | tr -d '\r' | awk 'tolower($1)=="location:"{print $2}')"
    [[ -z "$location" ]] && location="-"
    if [[ "$status" == "$want_status" && "$location" == "$want_location" ]]; then
        printf 'PASS  %-58s %s %s\n' "$name" "$status" "$location"
    else
        printf 'FAIL  %-58s got %s %s, want %s %s\n' "$name" "$status" "$location" "$want_status" "$want_location"
        FAILED=1
    fi
}

LOGIN="$BASE/sysadmin/login?next=/sysadmin/grafana/d/abc?orgId=1&refresh=5s"
DASH="/sysadmin/grafana/d/abc?orgId=1&refresh=5s"
HTML="Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
JSON="Accept: application/json, text/plain, */*"

check "navigation (Sec-Fetch-Mode navigate, text/html)" 302 "$LOGIN" "$DASH" \
    -H "Sec-Fetch-Mode: navigate" -H "Sec-Fetch-Dest: document" -H "$HTML"
check "XHR api/ds/query (cors, json)" 401 - /sysadmin/grafana/api/ds/query \
    -X POST -H "Sec-Fetch-Mode: cors" -H "Sec-Fetch-Dest: empty" -H "$JSON" \
    -H "Content-Type: application/json" --data '{}'
check "XHR api/login/ping (cors, json)" 401 - /sysadmin/grafana/api/login/ping \
    -H "Sec-Fetch-Mode: cors" -H "Sec-Fetch-Dest: empty" -H "$JSON"
check "fetch no-cors" 401 - /sysadmin/grafana/api/annotations \
    -H "Sec-Fetch-Mode: no-cors" -H "$JSON"
check "same-origin fetch that accepts text/html" 401 - /sysadmin/grafana/public/x.html \
    -H "Sec-Fetch-Mode: same-origin" -H "$HTML"
check "script subresource (no-cors, */*)" 401 - /sysadmin/grafana/public/build/app.js \
    -H "Sec-Fetch-Mode: no-cors" -H "Sec-Fetch-Dest: script" -H "Accept: */*"
check "websocket upgrade (Sec-Fetch-Mode websocket)" 401 - /sysadmin/grafana/api/live/ws \
    -H "Sec-Fetch-Mode: websocket" -H "Upgrade: websocket" -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=="
check "websocket upgrade, no Fetch Metadata" 401 - /sysadmin/grafana/api/live/ws \
    -H "Upgrade: websocket" -H "Connection: Upgrade" \
    -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ=="
check "no Fetch Metadata, Accept text/html (older browser)" 302 "$LOGIN" "$DASH" -H "$HTML"
check "no Fetch Metadata, Accept */*" 401 - "$DASH" -H "Accept: */*"
check "no Fetch Metadata, no Accept" 401 - "$DASH" -H "Accept:"
check "Sec-Fetch-Mode is case-insensitive (NAVIGATE)" 302 "$LOGIN" "$DASH" \
    -H "Sec-Fetch-Mode: NAVIGATE" -H "$HTML"
check "authorized navigation is proxied to Grafana" 200 - "$DASH" \
    -H "Cookie: session=sysadmin" -H "Sec-Fetch-Mode: navigate" -H "$HTML"
check "authorized XHR is proxied to Grafana" 200 - /sysadmin/grafana/api/ds/query \
    -H "Cookie: session=sysadmin" -H "Sec-Fetch-Mode: cors" -H "$JSON"
check "auth-check is internal-only" 404 - /sysadmin/grafana/auth-check
check "bare mount point normalised" 302 "$BASE/sysadmin/grafana/" /sysadmin/grafana

body="$(curl -s -H 'Sec-Fetch-Mode: cors' "$BASE/sysadmin/grafana/api/ds/query")"
proxied="$(curl -s -H 'Cookie: session=sysadmin' -H 'Sec-Fetch-Mode: cors' "$BASE/sysadmin/grafana/api/ds/query")"
[[ "$body" == '{"message":"System admin session required"}' ]] \
    && echo "PASS  401 body is the JSON message" || { echo "FAIL  401 body: $body"; FAILED=1; }
[[ "$proxied" == "grafana /sysadmin/grafana/api/ds/query user=sysadmin_stub" ]] \
    && echo "PASS  proxied request carries X-WEBAUTH-USER" || { echo "FAIL  proxied: $proxied"; FAILED=1; }

exit "$FAILED"
