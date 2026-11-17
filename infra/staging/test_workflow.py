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

    def test_first_use_and_closeout_have_no_provider_credentials(self):
        workflow = WORKFLOW.read_text()
        install, rest = workflow.split("  install:\n", 1)[1].split("  first_use:\n", 1)
        checkpoint, closeout = rest.split("  closeout:\n", 1)
        self.assertIn("controller/infra/staging/bootstrap.py", install)
        self.assertIn("    needs: install\n", checkpoint)
        self.assertIn("environment: cth-staging-first-use", checkpoint)
        self.assertIn("needs: [allocate, install, first_use]", closeout)
        self.assertIn("if: always()", closeout)
        self.assertIn("permissions: {}", closeout)
        self.assertNotIn("secrets.", closeout)
        self.assertNotIn("environment:", closeout)
        self.assertNotIn("DO_STAGING_TOKEN", install + rest)
        self.assertNotIn("digitalocean.py", closeout)

    def test_handoff_only_reports_valid_id_or_manual_reconciliation(self):
        shell = textwrap.dedent(WORKFLOW.read_text().split("  closeout:\n")[1].split("        run: |\n")[1])
        with tempfile.TemporaryDirectory() as directory:
            summary = Path(directory) / "summary"
            for value, expected in (("227", "destroy it manually"), ("untrusted", "Reconcile provider activity")):
                summary.write_text("")
                result = subprocess.run(
                    ["bash", "-euc", shell],
                    env=dict(os.environ, ID=value, INSTALL="failure", FIRST_USE="skipped",
                             GITHUB_STEP_SUMMARY=str(summary)), capture_output=True,
                )
                self.assertEqual(result.returncode, int(value == "untrusted"))
                self.assertIn(expected, summary.read_text())
                self.assertNotIn("untrusted", summary.read_text())
