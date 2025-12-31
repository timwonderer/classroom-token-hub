#!/bin/bash
# Force reload production - clears all caches and restarts services

set -e

echo "🔄 Force reloading production server..."

# Navigate to project directory
cd ~/classroom-economy

# Kill all gunicorn workers
echo "Stopping all gunicorn processes..."
sudo pkill -9 gunicorn || true

# Clear Python bytecode cache
echo "Clearing Python bytecode cache..."
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Clear Jinja2 template cache
echo "Clearing Jinja2 template cache..."
rm -rf /tmp/__jinja2_* 2>/dev/null || true
rm -rf /var/tmp/__jinja2_* 2>/dev/null || true

# Ensure we're on latest main
echo "Pulling latest code..."
git fetch origin main
git reset --hard origin/main

# Reload systemd
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

# Start gunicorn fresh
echo "Starting gunicorn..."
sudo systemctl start gunicorn

# Wait a moment for startup
sleep 3

# Check status
echo "Checking gunicorn status..."
sudo systemctl status gunicorn --no-pager

echo "✅ Force reload complete!"
