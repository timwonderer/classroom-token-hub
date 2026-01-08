#!/bin/bash
#
# Complete DigitalOcean Firewall Setup for Cloudflare + Pulsetic (pydo client)
#
# Usage:
#   ./setup-firewall-complete.sh create <droplet-id> [ssh-ip]
#   ./setup-firewall-complete.sh update <firewall-id>
#
# Requirements:
#   - python3
#   - pydo (pip install pydo)
#   - DigitalOcean token via DIGITALOCEAN_ACCESS_TOKEN or doctl config

set -e

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required."
    exit 1
fi

exec python3 "$SCRIPT_DIR/firewall_complete.py" "$@"
