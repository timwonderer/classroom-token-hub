#!/usr/bin/env python3
"""
Add all Pulsetic IPs to DigitalOcean firewall.

Usage:
    python3 scripts/add-uptimerobot.py <firewall-id>
"""

import json
import subprocess
import sys
from pathlib import Path

# ANSI colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color

def run_command(cmd):
    """Run a shell command and return success status."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode == 0, result.stderr

def main():
    if len(sys.argv) != 2:
        print(f"{RED}Error: Firewall ID required{NC}")
        print("\nUsage:")
        print(f"  python3 {sys.argv[0]} <firewall-id>")
        print("\nExample:")
        print(f"  python3 {sys.argv[0]} 954d0d9c-a8b2-4981-85ef-42982fc496a6")
        sys.exit(1)

    firewall_id = sys.argv[1]

    # Load IPs from JSON
    json_path = Path(__file__).parent / 'firewall-ips.json'

    if not json_path.exists():
        print(f"{RED}Error: firewall-ips.json not found at {json_path}{NC}")
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    pulsetic_ipv4 = data['pulsetic']['ipv4']
    pulsetic_ipv6 = data['pulsetic']['ipv6']
    pulsetic_ips = pulsetic_ipv4 + pulsetic_ipv6

    print(f"{GREEN}Adding {len(pulsetic_ips)} Pulsetic IPs to firewall: {firewall_id}{NC}\n")

    # Verify firewall exists
    success, error = run_command(f'doctl compute firewall get {firewall_id} > /dev/null 2>&1')
    if not success:
        print(f"{RED}Error: Firewall '{firewall_id}' not found{NC}")
        print("\nAvailable firewalls:")
        subprocess.run('doctl compute firewall list', shell=True)
        sys.exit(1)

    added = 0
    skipped = 0
    failed = 0

    for ip in pulsetic_ips:
        print(f"Adding {ip} ... ", end='', flush=True)

        cmd = f'doctl compute firewall add-rules {firewall_id} --inbound-rules "protocol:tcp,ports:443,address:{ip}"'
        success, error = run_command(cmd)

        if success:
            print(f"{GREEN}✓{NC}")
            added += 1
        else:
            # Check if already exists
            check_cmd = f'doctl compute firewall get {firewall_id} --format InboundRules --no-header'
            result = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)

            normalized_ip = ip.split('/')[0]
            if normalized_ip in result.stdout:
                print(f"{YELLOW}(already exists){NC}")
                skipped += 1
            else:
                print(f"{RED}✗ failed{NC}")
                if error:
                    print(f"  Error: {error.strip()}")
                failed += 1

    print()
    print(f"{GREEN}{'=' * 60}{NC}")
    print(f"{GREEN}Summary:{NC}")
    print(f"  Added:          {GREEN}{added}{NC}")
    print(f"  Already exists: {YELLOW}{skipped}{NC}")
    print(f"  Failed:         {RED}{failed}{NC}")
    print(f"{GREEN}{'=' * 60}{NC}")

    if failed > 0:
        print(f"\n{YELLOW}Warning: Some IPs failed to add. Check the output above.{NC}")
        sys.exit(1)
    else:
        print(f"\n{GREEN}✓ Pulsetic IPs successfully added to firewall!{NC}")

if __name__ == '__main__':
    main()
