#!/bin/bash
#
# Pulsetic-only DigitalOcean Firewall Setup (pydo client)
#
# Usage:
#   ./setup-pulsetic-firewall.sh create <droplet-id>
#   ./setup-pulsetic-firewall.sh update <firewall-id>
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

exec python3 "$SCRIPT_DIR/pulsetic_firewall.py" "$@"
