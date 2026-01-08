#!/bin/bash
#
# Add Pulsetic IPs to DigitalOcean Firewall (pydo client)
#
# Usage:
#   ./add-pulsetic-to-firewall.sh <firewall-id>
#
# Requirements:
#   - python3
#   - pydo (pip install pydo)
#   - DigitalOcean token via DIGITALOCEAN_ACCESS_TOKEN or doctl config

set -e

if [ -z "$1" ]; then
    echo "Error: Firewall ID required"
    echo "Usage: $0 <firewall-id>"
    exit 1
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is required."
    exit 1
fi

exec python3 "$SCRIPT_DIR/pulsetic_firewall.py" update "$1"
