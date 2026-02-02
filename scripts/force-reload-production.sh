#!/bin/bash
# Force reload production - clears caches and restarts services

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "❌ This script must be run as root or with sudo."
  exit 1
fi

echo "🔄 Force reloading production server..."

cd /root/classroom-economy

# Safety check: no dirty working tree
if [[ -n $(git status --porcelain) ]]; then
  echo "❌ Uncommitted changes found. Aborting to prevent data loss."
  git status
  exit 1
fi

echo "📥 Fetching latest code..."
git fetch origin main
git reset --hard origin/main

echo "🧹 Clearing Python bytecode cache..."
find . -name "*.pyc" -delete 2>/dev/null || true

echo "🧹 Clearing Jinja2 cache..."
rm -rf /tmp/__jinja2_* /var/tmp/__jinja2_* 2>/dev/null || true

echo "🔁 Reloading systemd daemon..."
systemctl daemon-reload

echo "🚀 Restarting gunicorn (systemd-managed)..."
systemctl restart gunicorn

echo "⏳ Giving gunicorn time to warm up..."
sleep 8

echo "📊 Gunicorn status:"
systemctl status gunicorn --no-pager || true

echo "✅ Force reload complete."