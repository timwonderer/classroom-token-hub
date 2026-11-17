"""Offline checks covering the owner gate, evidence and failure-path cleanup wiring."""

import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

WORKFLOW = Path(__file__).resolve().parents[2] / ".github/workflows/staging-ephemeral.yml"


class WorkflowTests(unittest.TestCase):
    def test_allocation_requires_owner_confirmations_and_first_manual_dispatch(self):
        workflow = WORKFLOW.read_text()
        allocate = workflow.split("  allocate:\n", 1)[1].split("  install:\n", 1)[0]
        self.assertIn("on:\n  workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("push:", workflow)
        for fence in (
            "github.event.repository.default_branch",
            "github.actor == vars.CTH_STAGING_OWNER",
            "github.run_attempt == '1'",
            "inputs.previous_resources_gone && inputs.approve_run",
        ):
            self.assertIn(fence, allocate)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertEqual(allocate.count("digitalocean.py create"), 1)

    def test_failed_install_still_selects_exact_id_cleanup_without_guest_credentials(self):
        workflow = WORKFLOW.read_text()
        install, cleanup = workflow.split("  install:\n", 1)[1].split("  cleanup:\n", 1)
        self.assertIn("needs: [allocate, install, first_use]", cleanup)
        self.assertIn("if: always() && needs.allocate.result != 'skipped'", cleanup)
        self.assertNotIn("needs.install.result ==", cleanup)
        self.assertIn("STAGING_DROPLET_ID: ${{ needs.allocate.outputs.droplet_id }}", cleanup)
        self.assertIn("STAGING_MARKER: ${{ needs.allocate.outputs.marker }}", cleanup)
        self.assertIn("digitalocean.py cleanup", cleanup)
        self.assertNotIn("DO_STAGING_TOKEN", install)
        self.assertNotIn("STAGING_SSH_PRIVATE_KEY", cleanup)
        self.assertIn("controller/infra/staging/bootstrap.py", install)
        self.assertNotIn("infra/self-hosting/install.py", install)
        self.assertIn("ref: ${{ inputs.app_sha }}", install)

    def test_first_use_waits_for_success_and_either_decision_releases_cleanup(self):
        checkpoint, cleanup = WORKFLOW.read_text().split("  first_use:\n", 1)[1].split("  cleanup:\n", 1)
        self.assertIn("    needs: install\n", checkpoint)
        self.assertNotIn("    if:", checkpoint)  # Default success() skips the hold after install failure.
        self.assertIn("environment: cth-staging-first-use", checkpoint)
        self.assertIn("permissions: {}", checkpoint)
        self.assertNotIn("secrets.", checkpoint)
        self.assertIn("needs: [allocate, install, first_use]", cleanup)
        self.assertIn("if: always() && needs.allocate.result != 'skipped' && github.run_attempt == '1'\n", cleanup)

    def test_missing_or_ambiguous_receipt_refuses_before_delete_and_writes_safe_summary(self):
        workflow = WORKFLOW.read_text().split("      - name: Check for exact creation receipt", 1)[1]
        shell = textwrap.dedent(workflow.split("        run: |\n", 1)[1].split("      - uses:", 1)[0])
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary"
            for value in ("", "owner-secret-text", "0", "-1"):
                result = subprocess.run(
                    ["bash", "-euc", shell],
                    env=dict(
                        os.environ,
                        ID=value,
                        MARKER="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        GITHUB_STEP_SUMMARY=str(summary),
                    ),
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("No exact creation receipt", summary.read_text())
                self.assertNotIn("owner-secret-text", summary.read_text() + result.stderr)
            summary.unlink()
            result = subprocess.run(
                ["bash", "-euc", shell],
                env=dict(
                    os.environ,
                    ID="227",
                    MARKER="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    GITHUB_STEP_SUMMARY=str(summary),
                ),
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertFalse(summary.exists())
