#!/bin/bash
# Force reload production - clears all caches and restarts services

set -e

if [[ $EUID -ne 0 ]]; then
   echo "❌ This script must be run as root or with sudo."
   exit 1
# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Navigate to project directory (assuming this script is in a 'scripts' subdirectory)
sudo systemctl stop gunicorn
sleep 2 # Give it a moment to shut down gracefully
# Force kill any remaining processes
if pgrep gunicorn > /dev/null; then
    echo "Gunicorn processes still running, force killing them..."
    sudo pkill -9 gunicorn || true
fi

echo "🔄 Force reloading production server..."

# Navigate to project directory
cd ~/classroom-economy

# Kill all gunicorn workers
# Check for uncommitted changes before resetting
if [[ -n $(git status --porcelain) ]]; then
  echo "❌ Error: Uncommitted changes found in the working directory."
  echo "Aborting to prevent data loss. Please commit or stash changes first."
  git status
  exit 1
fi
git fetch origin main
git reset --hard origin/main

# Clear Python bytecode cache
echo "Clearing Python bytecode cache..."
# Wait for gunicorn to become active
echo "Waiting for gunicorn to start..."
for i in {1..10}; do
    if sudo systemctl is-active --quiet gunicorn; then
        echo "Gunicorn started successfully."
        break
    fi
    if [ "$i" -eq 10 ]; then
        echo "❌ Error: Gunicorn failed to start after 10 seconds."
        sudo systemctl status gunicorn --no-pager
        exit 1
    fi
    echo "Waiting... ($i/10)"
    sleep 1
done
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
