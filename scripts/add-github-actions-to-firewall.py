#!/usr/bin/env python3
"""
Add GitHub Actions IPs to DigitalOcean firewall for deployment access.

GitHub Actions uses dynamic IPs, so we fetch them from GitHub's API
and add them to the firewall to allow SSH access for deployments.

Usage:
    python3 scripts/add-github-actions-to-firewall.py <firewall-id>
"""

import ipaddress
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

# ANSI colors
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def run_command(cmd):
    """Run a command (argv list) and return success status.

    CodeQL py/command-line-injection (alerts #281, #282): this used to be
    ``subprocess.run(cmd, shell=True, ...)`` with ``cmd`` an f-string built
    from ``firewall_id`` (an operator-supplied CLI arg) and, at the call
    sites below, from each IP string in GitHub's own ``/meta`` API response.
    Neither is attacker-controlled in the way a request handler's input
    would be, but shell=True means any shell metacharacter in either value
    -- a malformed API response, a copy-pasted firewall id -- runs as a
    shell command rather than being rejected or passed through literally.
    An argv list goes straight to execve with no shell in between, so this
    has no shell-metacharacter interpretation left to exploit regardless of
    what ends up in the strings.
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except OSError as error:
        return False, str(error)
    return result.returncode == 0, result.stderr

def fetch_github_ips():
    """Fetch GitHub Actions IP ranges from GitHub API."""
    print(f"{BLUE}Fetching GitHub Actions IP ranges...{NC}")

    try:
        with urllib.request.urlopen('https://api.github.com/meta', timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))

        # GitHub Actions uses the 'actions' IP ranges
        actions_ips = data.get('actions', [])

        if not actions_ips:
            print(f"{YELLOW}Warning: No GitHub Actions IPs found, trying 'hooks' instead{NC}")
            actions_ips = data.get('hooks', [])

        return [str(ipaddress.ip_network(ip, strict=False)) for ip in actions_ips]
    except Exception as e:
        print(f"{RED}Error fetching GitHub IPs: {e}{NC}")
        return None

def main():
    if len(sys.argv) != 2:
        print(f"{RED}Error: Firewall ID required{NC}")
        print("\nUsage:")
        print(f"  python3 {sys.argv[0]} <firewall-id>")
        print("\nGet your firewall ID:")
        print("  doctl compute firewall list")
        sys.exit(1)

    firewall_id = sys.argv[1]
    if not re.fullmatch(r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', firewall_id):
        print(f"{RED}Error: Firewall ID must be a UUID{NC}")
        sys.exit(1)

    # Verify doctl is installed
    success, _ = run_command(['doctl', 'version'])
    if not success:
        print(f"{RED}Error: doctl is not installed{NC}")
        print("Install: https://docs.digitalocean.com/reference/doctl/how-to/install/")
        sys.exit(1)

    # Verify firewall exists
    success, error = run_command(['doctl', 'compute', 'firewall', 'get', firewall_id])
    if not success:
        print(f"{RED}Error: Firewall '{firewall_id}' not found{NC}")
        print("\nAvailable firewalls:")
        subprocess.run(['doctl', 'compute', 'firewall', 'list'])
        sys.exit(1)

    # Fetch GitHub IPs
    github_ips = fetch_github_ips()

    if not github_ips:
        print(f"{RED}Failed to fetch GitHub Actions IPs{NC}")
        sys.exit(1)

    print(f"{GREEN}Found {len(github_ips)} GitHub Actions IP ranges{NC}\n")

    added = 0
    skipped = 0
    failed = 0

    for ip in github_ips:
        print(f"Adding {ip} ... ", end='', flush=True)

        # Add rule for SSH (22) - GitHub Actions needs SSH for deployment
        cmd = [
            'doctl', 'compute', 'firewall', 'add-rules', firewall_id,
            '--inbound-rules', f'protocol:tcp,ports:22,address:{ip}',
        ]
        success, error = run_command(cmd)

        if success:
            print(f"{GREEN}✓{NC}")
            added += 1
        else:
            # Check if it already exists
            check_cmd = [
                'doctl', 'compute', 'firewall', 'get', firewall_id,
                '--format', 'InboundRules', '--no-header',
            ]
            result = subprocess.run(check_cmd, capture_output=True, text=True)

            # Remove /32 suffix for comparison if present
            ip_base = ip.replace('/32', '').replace('/128', '')

            if ip_base in result.stdout or ip in result.stdout:
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
        print(f"\n{GREEN}✓ GitHub Actions IPs successfully added to firewall!{NC}")
        print(f"\n{BLUE}Note: GitHub may update their IP ranges. Re-run this script{NC}")
        print(f"{BLUE}if deployments start failing.{NC}")

if __name__ == '__main__':
    main()
